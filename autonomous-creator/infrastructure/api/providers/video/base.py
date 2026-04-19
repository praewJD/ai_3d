"""
Video Provider Interface - 비디오 생성 API 추상화

모든 비디오 생성 API가 구현해야 하는 인터페이스
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import asyncio


class VideoGenerationStatus(str, Enum):
    """비디오 생성 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoResolution(str, Enum):
    """비디오 해상도"""
    SD_480P = "480p"
    HD_720P = "720p"
    FHD_1080P = "1080p"
    UHD_4K = "4k"


@dataclass
class VideoGenerationRequest:
    """비디오 생성 요청"""
    # 입력
    image_path: Optional[str] = None  # 이미지 투비디오용
    prompt: str = ""

    # 설정
    model: str = "default"
    resolution: VideoResolution = VideoResolution.FHD_1080P
    duration: int = 5  # 초
    fps: int = 30

    # 고급 설정
    negative_prompt: str = ""
    seed: Optional[int] = None
    guidance_scale: float = 7.5
    num_inference_steps: int = 25

    # 스타일
    style: str = "cinematic"
    motion_strength: float = 0.7  # 0~1

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "prompt": self.prompt,
            "model": self.model,
            "resolution": self.resolution.value,
            "duration": self.duration,
            "fps": self.fps,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "guidance_scale": self.guidance_scale,
            "num_inference_steps": self.num_inference_steps,
            "style": self.style,
            "motion_strength": self.motion_strength
        }


@dataclass
class VideoGenerationResult:
    """비디오 생성 결과"""
    # 상태
    id: str
    status: VideoGenerationStatus

    # 결과
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # 메타데이터
    duration: float = 0.0
    resolution: str = ""
    file_size: int = 0
    created_at: str = ""

    # 에러
    error_message: Optional[str] = None

    # 비용
    credits_used: int = 0
    cost_usd: float = 0.0

    @property
    def is_complete(self) -> bool:
        return self.status == VideoGenerationStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == VideoGenerationStatus.FAILED


class BaseVideoProvider(ABC):
    """
    비디오 생성 프로바이더 기본 클래스

    Luma, Runway, Kling 등 모든 비디오 API가 구현해야 함
    """

    # 프로바이더 정보
    PROVIDER_NAME: str = "base"
    SUPPORTED_MODELS: List[str] = []
    DEFAULT_MODEL: str = "default"

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    # ============================================================
    # 필수 구현 메서드
    # ============================================================

    @abstractmethod
    async def generate(
        self,
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """
        비디오 생성 요청

        Args:
            request: 생성 요청

        Returns:
            생성 결과 (비동기 상태일 수 있음)
        """
        pass

    @abstractmethod
    async def get_status(self, generation_id: str) -> VideoGenerationResult:
        """
        생성 상태 조회

        Args:
            generation_id: 생성 작업 ID

        Returns:
            현재 상태
        """
        pass

    @abstractmethod
    async def download(
        self,
        result: VideoGenerationResult,
        output_path: str
    ) -> str:
        """
        생성된 비디오 다운로드

        Args:
            result: 생성 결과
            output_path: 저장 경로

        Returns:
            저장된 파일 경로
        """
        pass

    # ============================================================
    # 편의 메서드
    # ============================================================

    async def generate_and_wait(
        self,
        request: VideoGenerationRequest,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> VideoGenerationResult:
        """
        비디오 생성 및 완료 대기

        Args:
            request: 생성 요청
            timeout: 최대 대기 시간 (초)
            poll_interval: 상태 확인 간격 (초)

        Returns:
            완료된 결과

        Raises:
            TimeoutError: 타임아웃
            RuntimeError: 생성 실패
        """
        # 생성 시작
        result = await self.generate(request)

        # 이미 완료됨
        if result.is_complete:
            return result

        # 완료 대기
        elapsed = 0
        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            result = await self.get_status(result.id)

            if result.is_complete:
                return result

            if result.is_failed:
                raise RuntimeError(f"Video generation failed: {result.error_message}")

        raise TimeoutError(f"Video generation timeout after {timeout}s")

    async def generate_from_image(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        model: str = None,
        duration: int = 5
    ) -> str:
        """
        이미지로부터 비디오 생성 (간편 메서드)

        Args:
            image_path: 입력 이미지 경로
            prompt: 프롬프트
            output_path: 출력 경로
            model: 모델 (선택)
            duration: 영상 길이 (초)

        Returns:
            생성된 비디오 경로
        """
        request = VideoGenerationRequest(
            image_path=image_path,
            prompt=prompt,
            model=model or self.DEFAULT_MODEL,
            duration=duration
        )

        result = await self.generate_and_wait(request)
        return await self.download(result, output_path)

    # ============================================================
    # 정보 메서드
    # ============================================================

    def get_supported_models(self) -> List[str]:
        """지원 모델 목록"""
        return self.SUPPORTED_MODELS

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """모델 정보"""
        return {
            "name": model,
            "provider": self.PROVIDER_NAME
        }

    async def estimate_cost(
        self,
        request: VideoGenerationRequest
    ) -> Dict[str, float]:
        """
        예상 비용 계산

        Args:
            request: 생성 요청

        Returns:
            예상 비용 정보
        """
        # 기본 구현 (오버라이드 권장)
        return {
            "credits": 0,
            "usd": 0.0
        }

    async def health_check(self) -> bool:
        """API 상태 확인"""
        try:
            # 기본 구현: 간단한 API 호출
            return True
        except:
            return False
