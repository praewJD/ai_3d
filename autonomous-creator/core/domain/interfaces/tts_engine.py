"""
TTS Engine Interface

음성 생성 엔진 추상화
"""
from abc import ABC, abstractmethod
from typing import Optional
from ..entities.audio import VoiceSettings


class ITTSEngine(ABC):
    """
    TTS 엔진 인터페이스

    모든 TTS 엔진이 구현해야 하는 추상 인터페이스
    """

    @abstractmethod
    async def generate(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """
        텍스트를 음성으로 변환

        Args:
            text: 변환할 텍스트
            voice: 음성 설정
            output_path: 출력 파일 경로

        Returns:
            생성된 오디오 파일 경로

        Raises:
            TTSError: TTS 생성 실패 시
        """
        pass

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """
        해당 언어 지원 여부

        Args:
            language: 언어 코드 (ko, th, en, ja, zh)

        Returns:
            지원 여부
        """
        pass

    @abstractmethod
    def get_engine_name(self) -> str:
        """
        엔진 이름 반환

        Returns:
            엔진 이름 (예: "GPT-SoVITS", "Azure-TTS", "Edge-TTS")
        """
        pass

    @abstractmethod
    async def get_available_voices(self, language: str) -> list[dict]:
        """
        해당 언어에서 사용 가능한 음성 목록

        Args:
            language: 언어 코드

        Returns:
            음성 정보 목록 [{"id": str, "name": str, "gender": str}]
        """
        pass

    async def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """
        예상 재생 시간 계산

        Args:
            text: 텍스트
            speed: 재생 속도

        Returns:
            예상 시간 (초)
        """
        # 기본 구현: 글자 수 기반 추정
        # 한글: 약 3.5자/초, 영어: 약 2.5단어/초
        char_count = len(text)
        base_duration = char_count / 3.5  # 기본 3.5자/초
        return base_duration / speed
