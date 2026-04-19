"""
VideoGenerator - 이미지 기반 영상 생성

Luma Dream Machine API 연동
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class VideoGenerationResult:
    """영상 생성 결과"""
    success: bool
    scene_id: str
    video_path: Optional[Path] = None
    prompt_used: str = ""
    duration_seconds: float = 5.0
    generation_time_ms: int = 0
    api_cost_usd: float = 0.0
    error_message: str = ""


class VideoGenerator:
    """
    영상 생성기

    - 이미지 → 영상 변환
    - Luma Dream Machine API 사용
    - 비동기 처리, 재시도 로직
    """

    # 비용 (초당)
    COST_PER_SECOND = {
        "kling-2.6": 0.05,
        "ray-3.14": 0.03,
        "veo-3": 0.06,
    }

    def __init__(
        self,
        api_key: str = None,
        output_dir: str = "outputs/videos",
        default_model: str = "kling-2.6"
    ):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_model = default_model
        self._client = None

    @property
    def client(self):
        """Luma 클라이언트 지연 초기화"""
        if self._client is None:
            from infrastructure.api.providers.video.luma import LumaProvider
            self._client = LumaProvider(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        image_path: Path,
        prompt: str,
        scene_id: str,
        model: str = None,
        duration: int = 5
    ) -> VideoGenerationResult:
        """
        단일 영상 생성

        Args:
            image_path: 입력 이미지 경로
            prompt: 영상 프롬프트
            scene_id: 장면 ID
            model: 모델 (kling-2.6, ray-3.14, veo-3)
            duration: 영상 길이 (초)

        Returns:
            VideoGenerationResult
        """
        start_time = datetime.now()
        model = model or self.default_model

        try:
            if not image_path.exists():
                return VideoGenerationResult(
                    success=False,
                    scene_id=scene_id,
                    error_message=f"Image not found: {image_path}"
                )

            logger.info(f"Generating video for scene {scene_id}...")

            # Luma API 호출
            result = await self.client.generate_video(
                image_path=str(image_path),
                prompt=prompt,
                model=model,
                duration=duration
            )

            if not result.success:
                return VideoGenerationResult(
                    success=False,
                    scene_id=scene_id,
                    error_message=result.error_message
                )

            # 영상 저장
            video_path = await self._save_video(
                result.video_data,
                scene_id
            )

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            cost = self.COST_PER_SECOND.get(model, 0.05) * duration

            return VideoGenerationResult(
                success=True,
                scene_id=scene_id,
                video_path=video_path,
                prompt_used=prompt,
                duration_seconds=duration,
                generation_time_ms=int(elapsed),
                api_cost_usd=cost
            )

        except Exception as e:
            logger.exception(f"Video generation failed for scene {scene_id}")
            return VideoGenerationResult(
                success=False,
                scene_id=scene_id,
                error_message=str(e)
            )

    async def generate_batch(
        self,
        scenes: List[Dict[str, Any]],
        image_paths: Dict[str, Path],
        max_concurrent: int = 2
    ) -> List[VideoGenerationResult]:
        """
        여러 영상 병렬 생성

        Args:
            scenes: 장면 정보 목록
            image_paths: 장면 ID → 이미지 경로 맵
            max_concurrent: 최대 동시 실행 수

        Returns:
            생성 결과 목록
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(scene: Dict[str, Any]):
            async with semaphore:
                scene_id = scene["scene_id"]
                image_path = image_paths.get(scene_id)

                if not image_path:
                    return VideoGenerationResult(
                        success=False,
                        scene_id=scene_id,
                        error_message="Image path not found"
                    )

                return await self.generate(
                    image_path=image_path,
                    prompt=scene.get("video_prompt", ""),
                    scene_id=scene_id
                )

        tasks = [generate_with_semaphore(s) for s in scenes]
        results = await asyncio.gather(*tasks)

        return list(results)

    async def _save_video(self, video_data: bytes, scene_id: str) -> Path:
        """영상 저장"""
        filename = f"{scene_id}.mp4"
        path = self.output_dir / filename

        with open(path, 'wb') as f:
            f.write(video_data)

        logger.info(f"Video saved: {path}")
        return path

    async def generate_with_params(
        self,
        image_path: Path,
        prompt: str,
        scene_id: str,
        camera_motion: str = "",
        motion_intensity: str = "moderate",
        **kwargs
    ) -> VideoGenerationResult:
        """
        상세 파라미터로 영상 생성

        Args:
            image_path: 입력 이미지
            prompt: 프롬프트
            scene_id: 장면 ID
            camera_motion: 카메라 모션
            motion_intensity: 모션 강도
        """
        # 프롬프트에 카메라 모션 추가
        full_prompt = prompt
        if camera_motion:
            full_prompt = f"{prompt}, {camera_motion}"

        return await self.generate(
            image_path=image_path,
            prompt=full_prompt,
            scene_id=scene_id,
            **kwargs
        )


# 싱글톤
_generator: Optional[VideoGenerator] = None


def get_video_generator(api_key: str = None) -> VideoGenerator:
    """영상 생성기 싱글톤"""
    global _generator
    if _generator is None or api_key:
        _generator = VideoGenerator(api_key=api_key)
    return _generator
