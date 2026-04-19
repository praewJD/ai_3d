"""
ImageGenerator - 이미지 생성 핵심 로직

SD 3.5 API 연동, 캐릭터 일관성, 실행 로그 통합
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio

from core.domain.entities.scene import SceneNode, SceneStyle, StyleType
from infrastructure.prompt import (
    PromptOrchestrator,
    ImagePromptBundle,
    get_prompt_orchestrator
)
from infrastructure.storage import ExecutionLogger, get_execution_logger
from .ip_adapter import IPAdapterManager, get_ip_adapter_manager

logger = logging.getLogger(__name__)


@dataclass
class ImageGenerationResult:
    """이미지 생성 결과"""
    success: bool
    scene_id: str
    image_path: Optional[Path] = None
    prompt_used: str = ""
    negative_prompt: str = ""
    seed: int = 0
    generation_time_ms: int = 0
    api_cost_usd: float = 0.0
    error_message: str = ""

    # 메타데이터
    style_type: str = ""
    aspect_ratio: str = "16:9"


class ImageGenerator:
    """
    이미지 생성기

    - PromptOrchestrator로 프롬프트 생성
    - IP-Adapter로 캐릭터 일관성 유지
    - Stability API로 이미지 생성
    - 실행 로그에 결과 기록
    """

    # 비용 (SD 3.5 Large 기준)
    COST_PER_IMAGE = 0.04  # USD

    def __init__(
        self,
        api_key: str = None,
        output_dir: str = "outputs/images",
        orchestrator: PromptOrchestrator = None,
        ip_adapter: IPAdapterManager = None,
        logger_instance: ExecutionLogger = None
    ):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.orchestrator = orchestrator or get_prompt_orchestrator()
        self.ip_adapter = ip_adapter or get_ip_adapter_manager()
        self.logger = logger_instance

        # API 클라이언트 (지연 초기화)
        self._client = None

    @property
    def client(self):
        """API 클라이언트 지연 초기화"""
        if self._client is None:
            from infrastructure.api.providers.image.stability_sd35 import StabilitySD35Client
            self._client = StabilitySD35Client(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        scene: SceneNode,
        style_override: SceneStyle = None,
        seed: int = -1,
        aspect_ratio: str = "16:9"
    ) -> ImageGenerationResult:
        """
        단일 장면 이미지 생성

        Args:
            scene: 장면 노드
            style_override: 스타일 오버라이드
            seed: 시드 (-1이면 랜덤)
            aspect_ratio: 비율

        Returns:
            ImageGenerationResult
        """
        start_time = datetime.now()
        scene_id = scene.scene_id

        try:
            # 1. 프롬프트 생성
            prompt_bundle = self.orchestrator.build_image_prompt(scene)

            # 2. IP-Adapter 적용
            if scene.characters:
                prompt_bundle.positive = self.ip_adapter.apply_to_prompt(
                    prompt_bundle.positive,
                    scene.characters
                )

            # 3. 스타일 오버라이드
            if style_override:
                prompt_bundle.positive = f"{style_override.to_prompt_segment()}, {prompt_bundle.positive}"

            # 4. API 호출
            logger.info(f"Generating image for scene: {scene_id}")

            result = await self.client.generate(
                prompt=prompt_bundle.positive,
                negative_prompt=prompt_bundle.negative,
                aspect_ratio=aspect_ratio,
                seed=seed
            )

            if not result.success:
                return ImageGenerationResult(
                    success=False,
                    scene_id=scene_id,
                    error_message=result.error_message
                )

            # 5. 이미지 저장
            image_path = self._save_image(
                result.image_data,
                scene_id,
                result.seed
            )

            # 6. 실행 시간 계산
            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            return ImageGenerationResult(
                success=True,
                scene_id=scene_id,
                image_path=image_path,
                prompt_used=prompt_bundle.positive,
                negative_prompt=prompt_bundle.negative,
                seed=result.seed,
                generation_time_ms=int(elapsed),
                api_cost_usd=self.COST_PER_IMAGE,
                style_type=scene.style.type.value if scene.style else "3d_disney",
                aspect_ratio=aspect_ratio
            )

        except Exception as e:
            logger.exception(f"Image generation failed for scene {scene_id}")
            return ImageGenerationResult(
                success=False,
                scene_id=scene_id,
                error_message=str(e)
            )

    async def generate_batch(
        self,
        scenes: List[SceneNode],
        max_concurrent: int = 3
    ) -> List[ImageGenerationResult]:
        """
        여러 장면 병렬 생성

        Args:
            scenes: 장면 목록
            max_concurrent: 최대 동시 실행 수

        Returns:
            생성 결과 목록
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(scene: SceneNode):
            async with semaphore:
                return await self.generate(scene)

        tasks = [generate_with_semaphore(scene) for scene in scenes]
        results = await asyncio.gather(*tasks)

        return list(results)

    def _save_image(
        self,
        image_data: bytes,
        scene_id: str,
        seed: int
    ) -> Path:
        """이미지 저장"""
        filename = f"{scene_id}_seed{seed}.png"
        path = self.output_dir / filename

        with open(path, 'wb') as f:
            f.write(image_data)

        logger.info(f"Image saved: {path}")
        return path

    async def generate_with_reference(
        self,
        scene: SceneNode,
        reference_image: Path,
        strength: float = 0.35
    ) -> ImageGenerationResult:
        """
        참조 이미지 기반 생성 (IP-Adapter 스타일)

        Args:
            scene: 장면 노드
            reference_image: 참조 이미지
            strength: 참조 이미지 영향도 (0.0-1.0)

        Returns:
            ImageGenerationResult
        """
        # IP-Adapter 파라미터와 함께 생성
        prompt_bundle = self.orchestrator.build_image_prompt(scene)

        result = await self.client.generate_with_reference(
            prompt=prompt_bundle.positive,
            negative_prompt=prompt_bundle.negative,
            reference_image=reference_image,
            strength=strength
        )

        if not result.success:
            return ImageGenerationResult(
                success=False,
                scene_id=scene.scene_id,
                error_message=result.error_message
            )

        image_path = self._save_image(
            result.image_data,
            scene.scene_id,
            result.seed
        )

        return ImageGenerationResult(
            success=True,
            scene_id=scene.scene_id,
            image_path=image_path,
            prompt_used=prompt_bundle.positive,
            seed=result.seed,
            api_cost_usd=self.COST_PER_IMAGE
        )


# 편의 함수
_generator: Optional[ImageGenerator] = None


def get_image_generator(api_key: str = None) -> ImageGenerator:
    """이미지 생성기 싱글톤"""
    global _generator
    if _generator is None:
        _generator = ImageGenerator(api_key=api_key)
    return _generator
