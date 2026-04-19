"""
Image Generator Interface

이미지 생성 엔진 추상화
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from ..entities.preset import StylePreset


class IImageGenerator(ABC):
    """
    이미지 생성 엔진 인터페이스

    모든 이미지 생성 모델이 구현해야 하는 추상 인터페이스
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        preset: StylePreset,
        output_path: str,
        width: int = 576,
        height: int = 1024
    ) -> str:
        """
        프롬프트로 이미지 생성

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            output_path: 출력 파일 경로
            width: 이미지 너비 (기본 576, 9:16)
            height: 이미지 높이 (기본 1024, 9:16)

        Returns:
            생성된 이미지 파일 경로

        Raises:
            ImageGenerationError: 이미지 생성 실패 시
        """
        pass

    @abstractmethod
    async def generate_with_reference(
        self,
        prompt: str,
        preset: StylePreset,
        reference_image: str,
        output_path: str,
        scale: float = 0.8
    ) -> str:
        """
        참조 이미지 기반 생성 (IP-Adapter)

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            reference_image: 참조 이미지 경로
            output_path: 출력 파일 경로
            scale: IP-Adapter 스케일 (0~1)

        Returns:
            생성된 이미지 파일 경로
        """
        pass

    @abstractmethod
    async def generate_batch(
        self,
        prompts: List[str],
        preset: StylePreset,
        output_dir: str
    ) -> List[str]:
        """
        여러 이미지 일괄 생성

        Args:
            prompts: 프롬프트 목록
            preset: 스타일 프리셋
            output_dir: 출력 디렉토리

        Returns:
            생성된 이미지 파일 경로 목록
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        모델 이름 반환

        Returns:
            모델 이름 (예: "SD3.5-Medium", "SDXL")
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        모델 로드 여부

        Returns:
            로드 완료 여부
        """
        pass

    @abstractmethod
    async def load_model(self) -> None:
        """
        모델 로드

        모델이 로드되지 않은 경우 호출
        """
        pass

    @abstractmethod
    async def unload_model(self) -> None:
        """
        모델 언로드

        메모리 해제용
        """
        pass


class IStyleConsistencyManager(ABC):
    """
    스타일 일관성 관리 인터페이스
    """

    @abstractmethod
    async def generate_consistent_images(
        self,
        prompts: List[str],
        preset: StylePreset,
        output_dir: str
    ) -> List[str]:
        """
        일관된 스타일로 여러 이미지 생성

        Args:
            prompts: 장면별 프롬프트 목록
            preset: 스타일 프리셋
            output_dir: 출력 디렉토리

        Returns:
            생성된 이미지 경로 목록
        """
        pass

    @abstractmethod
    def set_reference_image(self, image_path: str) -> None:
        """
        참조 이미지 설정

        Args:
            image_path: 참조 이미지 경로
        """
        pass
