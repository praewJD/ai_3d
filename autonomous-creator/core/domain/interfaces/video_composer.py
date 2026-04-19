"""
Video Composer Interface

영상 합성 엔진 추상화
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from ..entities.video import Video, VideoSegment


class IVideoComposer(ABC):
    """
    영상 합성 인터페이스

    이미지 + 오디오 → 영상 변환
    """

    @abstractmethod
    async def compose(
        self,
        segments: List[VideoSegment],
        output_path: str,
        resolution: Tuple[int, int] = (1080, 1920),
        fps: int = 30
    ) -> Video:
        """
        세그먼트들을 영상으로 합성

        Args:
            segments: 비디오 세그먼트 목록
            output_path: 출력 파일 경로
            resolution: 해상도 (width, height)
            fps: 프레임 레이트

        Returns:
            생성된 Video 객체

        Raises:
            VideoCompositionError: 합성 실패 시
        """
        pass

    @abstractmethod
    async def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        """
        영상에 오디오 추가

        Args:
            video_path: 영상 파일 경로
            audio_path: 오디오 파일 경로
            output_path: 출력 파일 경로

        Returns:
            생성된 영상 파일 경로
        """
        pass

    @abstractmethod
    async def apply_ken_burns(
        self,
        image_path: str,
        duration: float,
        output_path: str,
        zoom_direction: str = "in"
    ) -> str:
        """
        Ken Burns 효과 적용 (이미지 → 비디오)

        Args:
            image_path: 이미지 파일 경로
            duration: 지속 시간 (초)
            output_path: 출력 파일 경로
            zoom_direction: 줌 방향 ("in", "out", "left", "right")

        Returns:
            생성된 비디오 클립 경로
        """
        pass

    @abstractmethod
    async def concatenate(
        self,
        video_paths: List[str],
        output_path: str,
        transition: Optional[str] = None
    ) -> str:
        """
        여러 영상 연결

        Args:
            video_paths: 영상 파일 경로 목록
            output_path: 출력 파일 경로
            transition: 전환 효과 ("fade", "crossfade", None)

        Returns:
            생성된 영상 파일 경로
        """
        pass


class ISVDGenerator(ABC):
    """
    Stable Video Diffusion 인터페이스
    """

    @abstractmethod
    async def generate_video(
        self,
        image_path: str,
        output_path: str,
        num_frames: int = 25,
        fps: int = 8,
        motion_bucket_id: int = 127
    ) -> str:
        """
        이미지에서 비디오 생성

        Args:
            image_path: 입력 이미지 경로
            output_path: 출력 비디오 경로
            num_frames: 프레임 수
            fps: 프레임 레이트
            motion_bucket_id: 모션 강도 (1-255)

        Returns:
            생성된 비디오 파일 경로
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        SVD 사용 가능 여부 (VRAM 확인)

        Returns:
            사용 가능 여부
        """
        pass
