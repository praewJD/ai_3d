"""
TTS Factory

언어에 따라 최적의 TTS 엔진 선택
"""
from typing import Dict, Type, Optional
from core.domain.interfaces.tts_engine import ITTSEngine
from core.domain.entities.audio import VoiceSettings
from .base import BaseTTSEngine
from .gpt_sovits import GPTSoVITSEngine
from .azure_tts import AzureTTSEngine
from .edge_tts import EdgeTTSEngine
from .f5_tts_thai import F5TTSThaiEngine

import logging

logger = logging.getLogger(__name__)


class TTSFactory:
    """
    TTS 엔진 팩토리

    언어에 따라 최적의 TTS 엔진을 자동 선택

    사용법:
        tts = TTSFactory.create("th", voice_settings)
        audio_path = await tts.generate(text, voice, output_path)
    """

    # 언어별 기본 엔진 매핑
    _engine_map: Dict[str, Type[BaseTTSEngine]] = {
        "ko": GPTSoVITSEngine,      # 한국어: GPT-SoVITS
        "ja": GPTSoVITSEngine,      # 일본어: GPT-SoVITS
        "zh": GPTSoVITSEngine,      # 중국어: GPT-SoVITS
        "th": F5TTSThaiEngine,      # 태국어: F5-TTS-THAI (Voice Cloning)
        "en": EdgeTTSEngine,        # 영어: Edge-TTS
    }

    # 엔진 인스턴스 캐시
    _instances: Dict[str, ITTSEngine] = {}

    @classmethod
    def create(
        cls,
        language: str,
        voice: Optional[VoiceSettings] = None
    ) -> ITTSEngine:
        """
        언어에 맞는 TTS 엔진 생성

        Args:
            language: 언어 코드 (ko, en, th, ja, zh)
            voice: 음성 설정 (선택)

        Returns:
            ITTSEngine 인스턴스
        """
        language = language.lower()

        # 언어별 엔진 선택
        if language in ["th", "thai"]:
            # Thai: F5-TTS-THAI (f5-tts-th 패키지 사용)
            return cls._create_or_get_instance(
                "th",
                voice,
                F5TTSThaiEngine
            )

        elif language in ["ko", "korean"]:
            # Korean: GPT-SoVITS
            return cls._create_or_get_instance(
                "ko",
                voice,
                GPTSoVITSEngine
            )

        elif language in ["ja", "japanese"]:
            # Japanese: GPT-SoVITS
            return cls._create_or_get_instance(
                "ja",
                voice,
                GPTSoVITSEngine
            )

        elif language in ["zh", "chinese"]:
            # Chinese: GPT-SoVITS
            return cls._create_or_get_instance(
                "zh",
                voice,
                GPTSoVITSEngine
            )

        elif language in ["en", "english"]:
            # English: Edge-TTS
            return cls._create_or_get_instance(
                "en",
                voice,
                EdgeTTSEngine
            )

        else:
            logger.warning(f"Unsupported language: {language}, falling back to Edge-TTS")
            return cls._create_or_get_instance(
                "en",
                voice,
                EdgeTTSEngine
            )

    @classmethod
    def _create_or_get_instance(
        cls,
        lang: str,
        voice: VoiceSettings | None,
        engine_class: Type[BaseTTSEngine]
    ) -> ITTSEngine:
        """인스턴스 생성 또는 캐시에서 반환"""
        cache_key = f"{lang}_{voice.speaker_id if voice and voice.speaker_id else 'default'}"
        if cache_key not in cls._instances:
            cls._instances[cache_key] = engine_class()
        return cls._instances[cache_key]

    @classmethod
    def register_engine(
        cls,
        language: str,
        engine_class: Type[BaseTTSEngine]
    ) -> None:
        """
        새 엔진 등록

        Args:
            language: 언어 코드
            engine_class: 엔진 클래스
        """
        cls._engine_map[language] = engine_class
        # 캐시 무효화
        cls._instances = {k: v for k, v in cls._instances.items()
                         if not k.startswith(f"{language}_")}

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """지원 언어 목록 반환"""
        return list(cls._engine_map.keys())

    @classmethod
    def get_engine_info(cls, language: str) -> dict:
        """엔진 정보 반환"""
        language = language.lower()

        engine_map = {
            "ko": {"name": "GPT-SoVITS", "type": "voice_cloning", "quality": "high"},
            "ja": {"name": "GPT-SoVITS", "type": "voice_cloning", "quality": "high"},
            "zh": {"name": "GPT-SoVITS", "type": "voice_cloning", "quality": "high"},
            "th": {"name": "F5-TTS-THAI", "type": "voice_cloning", "quality": "high"},
            "en": {"name": "Edge-TTS", "type": "neural", "quality": "high"},
        }

        return engine_map.get(language, {"name": "Unknown", "type": "unknown", "quality": "unknown"})

    @classmethod
    def clear_cache(cls) -> None:
        """엔진 캐시 삭제"""
        cls._instances.clear()
