"""
TTS 언어 설정 - 언어별 TTS 모델 매핑

언어 설정에 따라 로드할 TTS 모델을 분기합니다.
새 언어 추가 시 이 파일에 모델 매핑만 추가하면 됩니다.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TTSModelConfig:
    """언어별 TTS 모델 설정"""
    language: str           # 언어 코드 (ko, th, vi 등)
    model_name: str         # HuggingFace 모델명 또는 로컬 경로
    model_type: str         # "f5tts" | "gpt_sovits" | "azure" | "coqui"
    sample_rate: int        # 샘플링 레이트
    language_code: str      # TTS 모델 내부 언어 코드
    speaker: str = ""       # 기본 화자 (필요시)
    device: str = ""        # "cuda" | "cpu" | "" (자동)


# ═══════════════════════════════════════════════════════════════
# 언어별 TTS 모델 매핑
# 새 언어 추가: 이 딕셔너리에 항목만 추가
# ═══════════════════════════════════════════════════════════════
TTS_MODELS: Dict[str, TTSModelConfig] = {
    "ko": TTSModelConfig(
        language="ko",
        model_name="SWivid/F5-TTS",
        model_type="f5tts",
        sample_rate=24000,
        language_code="ko",
        speaker="default",
    ),
    "th": TTSModelConfig(
        language="th",
        model_name="VIZINTZOR/F5-TTS-THAI",
        model_type="f5tts",
        sample_rate=24000,
        language_code="th",
        speaker="default",
    ),
    "vi": TTSModelConfig(
        language="vi",
        model_name="",  # TODO: 베트남어 TTS 모델
        model_type="f5tts",
        sample_rate=24000,
        language_code="vi",
        speaker="default",
    ),
    "en": TTSModelConfig(
        language="en",
        model_name="SWivid/F5-TTS",
        model_type="f5tts",
        sample_rate=24000,
        language_code="en",
        speaker="default",
    ),
    "ja": TTSModelConfig(
        language="ja",
        model_name="",  # TODO: 일본어 TTS 모델
        model_type="f5tts",
        sample_rate=24000,
        language_code="ja",
        speaker="default",
    ),
    "zh": TTSModelConfig(
        language="zh",
        model_name="",  # TODO: 중국어 TTS 모델
        model_type="f5tts",
        sample_rate=24000,
        language_code="zh",
        speaker="default",
    ),
}


# ═══════════════════════════════════════════════════════════════
# 언어 메타데이터 (컴파일러에서 사용)
# ═══════════════════════════════════════════════════════════════
LANGUAGE_NAMES: Dict[str, str] = {
    "ko": "Korean",
    "th": "Thai",
    "vi": "Vietnamese",
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
}

LANGUAGE_NATIVE_NAMES: Dict[str, str] = {
    "ko": "한국어",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
}


def get_tts_config(language: str) -> Optional[TTSModelConfig]:
    """언어 코드로 TTS 모델 설정 조회"""
    return TTS_MODELS.get(language)


def get_language_name(language: str) -> str:
    """언어 코드 → 영어명"""
    return LANGUAGE_NAMES.get(language, language)


def get_language_native_name(language: str) -> str:
    """언어 코드 → 원어명"""
    return LANGUAGE_NATIVE_NAMES.get(language, language)


def is_tts_available(language: str) -> bool:
    """해당 언어의 TTS 모델이 설정되어 있는지 확인"""
    config = TTS_MODELS.get(language)
    return config is not None and bool(config.model_name)


def get_available_tts_languages() -> list:
    """TTS가 가능한 언어 목록 반환"""
    return [lang for lang, cfg in TTS_MODELS.items() if cfg.model_name]
