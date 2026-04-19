"""
TTS Infrastructure Module
"""
from .base import BaseTTSEngine
from .factory import TTSFactory
from .gpt_sovits import GPTSoVITSEngine
from .azure_tts import AzureTTSEngine
from .edge_tts import EdgeTTSEngine
from .f5_tts_thai import F5TTSThaiEngine
from .audio_antiforensics import AudioAntiForensics, StealthAudioProcessor
from .tts_config import (
    TTSModelConfig,
    TTS_MODELS,
    LANGUAGE_NAMES,
    LANGUAGE_NATIVE_NAMES,
    get_tts_config,
    get_language_name,
    get_language_native_name,
    is_tts_available,
    get_available_tts_languages,
)
from .tts_factory_bridge import create_tts_engine, get_tts_engine_info

__all__ = [
    "BaseTTSEngine",
    "TTSFactory",
    "GPTSoVITSEngine",
    "AzureTTSEngine",
    "EdgeTTSEngine",
    "F5TTSThaiEngine",
    "AudioAntiForensics",
    "StealthAudioProcessor",
    "TTSModelConfig",
    "TTS_MODELS",
    "LANGUAGE_NAMES",
    "LANGUAGE_NATIVE_NAMES",
    "get_tts_config",
    "get_language_name",
    "get_language_native_name",
    "is_tts_available",
    "get_available_tts_languages",
    "create_tts_engine",
    "get_tts_engine_info",
]
