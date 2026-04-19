"""
Base TTS Engine

모든 TTS 엔진의 기본 구현
"""
from abc import abstractmethod
from typing import Optional, List
from core.domain.interfaces.tts_engine import ITTSEngine
from core.domain.entities.audio import VoiceSettings


class BaseTTSEngine(ITTSEngine):
    """
    TTS 엔진 기본 클래스

    공통 기능을 제공하고 서브클래스에서 핵심 로직 구현
    """

    def __init__(self):
        self._is_initialized = False

    @abstractmethod
    async def _generate_audio(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """서브클래스에서 구현: 실제 오디오 생성"""
        pass

    async def generate(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """
        텍스트를 음성으로 변환 (템플릿 메서드)

        Args:
            text: 변환할 텍스트
            voice: 음성 설정
            output_path: 출력 파일 경로

        Returns:
            생성된 오디오 파일 경로
        """
        # 텍스트 전처리
        processed_text = self._preprocess_text(text)

        # 오디오 생성
        result = await self._generate_audio(processed_text, voice, output_path)

        # 후처리 (필요시)
        result = await self._postprocess_audio(result, voice)

        return result

    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리"""
        # 불필요한 공백 제거
        text = " ".join(text.split())
        return text

    async def _postprocess_audio(
        self,
        audio_path: str,
        voice: VoiceSettings
    ) -> str:
        """오디오 후처리 (필요시 오버라이드)"""
        return audio_path

    async def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """예상 재생 시간 계산"""
        char_count = len(text)
        base_duration = char_count / 3.5  # 기본 3.5자/초
        return base_duration / speed

    async def get_available_voices(self, language: str) -> list[dict]:
        """서브클래스에서 구현"""
        return []
