"""
Render Engine - 캐릭터 일관성 렌더링 엔진

LoRA + IP-Adapter + Seed + ControlNet 동시 적용
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class RenderConfig:
    """렌더링 설정"""
    # 필수
    prompt: str
    negative_prompt: str
    seed: int

    # LoRA
    lora_path: str = ""
    lora_weight: float = 0.85

    # IP-Adapter
    reference_image: str = ""
    reference_strength: float = 0.7
    use_ip_adapter: bool = True

    # ControlNet
    controlnet_type: str = "pose"  # pose, depth, canny
    controlnet_image: str = ""
    controlnet_weight: float = 0.75

    # 이미지 크기
    width: int = 1024
    height: int = 1024

    # 생성 파라미터
    num_inference_steps: int = 28
    guidance_scale: float = 7.5


@dataclass
class RenderResult:
    """렌더링 결과"""
    image_path: str
    seed: int
    prompt: str
    generation_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RenderEngine:
    """
    캐릭터 일관성 렌더링 엔진

    4요소 동시 적용:
    1. LoRA - 캐릭터 학습
    2. IP-Adapter - 참조 이미지
    3. Seed - 고정
    4. ControlNet - Pose 가이드
    """

    # 필수 조건 체크
    REQUIRED_FOR_CONSISTENCY = ["lora", "ip_adapter", "seed"]

    def __init__(self, generator=None):
        """
        Args:
            generator: SD35Generator 또는 호환 이미지 생성기
        """
        self.generator = generator

    async def render(
        self,
        config: RenderConfig,
        validate_config: bool = True
    ) -> RenderResult:
        """
        씬 렌더링

        Args:
            config: 렌더링 설정
            validate_config: 설정 검증 여부

        Returns:
            RenderResult
        """
        if validate_config:
            self._validate_config(config)

        import time
        start_time = time.time()

        # 생성기 호출
        result = await self.generator.generate(
            prompt=config.prompt,
            negative_prompt=config.negative_prompt,
            seed=config.seed,
            width=config.width,
            height=config.height,
            num_inference_steps=config.num_inference_steps,
            guidance_scale=config.guidance_scale,

            # LoRA
            lora=config.lora_path if config.lora_path else None,
            lora_weight=config.lora_weight,

            # IP-Adapter
            reference_image=config.reference_image if config.use_ip_adapter else None,
            reference_strength=config.reference_strength,
            use_ip_adapter=config.use_ip_adapter,

            # ControlNet
            controlnet={
                "type": config.controlnet_type,
                "image": config.controlnet_image,
                "weight": config.controlnet_weight
            } if config.controlnet_image else None
        )

        generation_time = time.time() - start_time

        return RenderResult(
            image_path=result if isinstance(result, str) else result.image_path,
            seed=config.seed,
            prompt=config.prompt,
            generation_time=generation_time,
            metadata={
                "lora": config.lora_path,
                "reference": config.reference_image,
                "controlnet": config.controlnet_type
            }
        )

    async def render_scene(
        self,
        scene: Dict[str, Any],
        character_id: str,
        identity_engine,
        prompt_compiler,
        output_dir: str = "outputs/renders"
    ) -> RenderResult:
        """
        씬 렌더링 (통합 인터페이스)

        Args:
            scene: 씬 데이터
            character_id: 캐릭터 ID
            identity_engine: CharacterIdentityEngine
            prompt_compiler: PromptCompiler
            output_dir: 출력 디렉토리
        """
        # 1. 캐릭터 정체성 조회
        identity_config = identity_engine.get_render_config(character_id)

        # 2. 프롬프트 컴파일 (77토큰 최적화)
        prompt = prompt_compiler.compile(
            scene_description=scene.get("description", ""),
            character_tokens=identity_config["core_tokens"],
            style=scene.get("style", "disney_3d"),
            emotion=scene.get("emotion"),
            camera=scene.get("camera")
        )

        # 3. 렌더링 설정 생성
        config = RenderConfig(
            prompt=prompt,
            negative_prompt=identity_config["negative_prompt"],
            seed=identity_config["seed"],

            # LoRA
            lora_path=identity_config["lora"],
            lora_weight=identity_config["lora_weight"],

            # IP-Adapter
            reference_image=identity_config["reference_image"],
            reference_strength=identity_config["reference_strength"],
            use_ip_adapter=True,

            # ControlNet
            controlnet_type="pose",
            controlnet_image=scene.get("pose_image", ""),
            controlnet_weight=identity_config["controlnet_weight"]
        )

        # 4. 렌더링
        result = await self.render(config)

        logger.info(f"Rendered scene: {scene.get('id')} with character {character_id}")

        return result

    async def render_batch(
        self,
        scenes: List[Dict[str, Any]],
        character_id: str,
        identity_engine,
        prompt_compiler,
        output_dir: str = "outputs/renders"
    ) -> List[RenderResult]:
        """
        여러 씬 일괄 렌더링
        """
        results = []

        for i, scene in enumerate(scenes):
            logger.info(f"Rendering scene {i+1}/{len(scenes)}")

            result = await self.render_scene(
                scene=scene,
                character_id=character_id,
                identity_engine=identity_engine,
                prompt_compiler=prompt_compiler,
                output_dir=output_dir
            )
            results.append(result)

        return results

    def _validate_config(self, config: RenderConfig):
        """설정 검증"""
        errors = []

        # 프롬프트 토큰 체크
        token_count = len(config.prompt.split()) * 1.3
        if token_count > 77:
            errors.append(f"Prompt exceeds 77 tokens: {token_count:.0f}")

        # 필수 요소 체크 (경고만)
        if not config.lora_path:
            logger.warning("No LoRA specified - character consistency may be reduced")

        if not config.reference_image:
            logger.warning("No reference image - IP-Adapter disabled")

        if config.seed < 0:
            logger.warning("Negative seed - using random")

        if errors:
            for err in errors:
                logger.error(err)
            raise ValueError(f"Render config validation failed: {errors}")
