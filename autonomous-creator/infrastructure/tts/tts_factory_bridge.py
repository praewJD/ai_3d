"""
TTS Factory Bridge - config 설정과 기존 TTSFactory 연결

config/api_config.py의 TTS_PROVIDER, TTS_LOCAL_MODEL, TTS_API_MODEL 설정에 따라
기존 TTSFactory를 통해 적절한 TTS 엔진을 반환합니다.

사용법:
    from infrastructure.tts.tts_factory_bridge import create_tts_engine

    engine = create_tts_engine(language="ko")
    audio = await engine.generate(text="안녕하세요")
"""
import logging
from typing import Optional

from config.api_config import (
    TTS_PROVIDER, TTS_LOCAL_MODEL, TTS_API_MODEL,
    TTS_MODEL_CONFIGS,
)

logger = logging.getLogger(__name__)


def create_tts_engine(
    language: str = None,
    provider: str = None,
    model: str = None,
) -> Optional[object]:
    """
    설정에 따라 TTS 엔진 생성

    Args:
        language: 타겟 언어 (auto 모드에서 자동 선택에 사용)
        provider: "local" | "api" | "auto" (None이면 설정값 사용)
        model: 모델명 (None이면 설정값 사용)

    Returns:
        TTS 엔진 인스턴스
    """
    _provider = provider or TTS_PROVIDER
    _model = model or (TTS_API_MODEL if _provider == "api" else TTS_LOCAL_MODEL)

    logger.info(f"TTS Engine 생성: provider={_provider}, model={_model}, language={language}")

    try:
        from infrastructure.tts.factory import TTSFactory

        # auto 모드: 언어에 따라 자동 선택 (기존 TTSFactory 로직)
        if _provider == "auto" and language:
            engine = TTSFactory.create(language)
            logger.info(f"Auto TTS: language={language} → {engine.__class__.__name__}")
            return engine

        # 명시적 provider/model 지정
        if _provider == "local":
            return _create_local_engine(_model, language)
        elif _provider == "api":
            return _create_api_engine(_model, language)
        else:
            # 폴백: 기존 TTSFactory 사용
            if language:
                return TTSFactory.create(language)
            logger.warning("auto 모드이나 language가 없습니다. GPT-SoVITS 사용")
            return TTSFactory.create("ko")

    except Exception as e:
        logger.error(f"TTS Engine 생성 실패: {e}")
        return None


def _create_local_engine(model: str, language: str = None) -> Optional[object]:
    """로컬 TTS 엔진 생성"""
    config = TTS_MODEL_CONFIGS.get(model, {})
    supported_langs = config.get("languages", [])

    # 언어 체크
    if language and supported_langs and language not in supported_langs:
        logger.warning(f"{model}은 {language}를 지원하지 않습니다. 지원: {supported_langs}")

    if model == "gpt_sovits":
        try:
            from infrastructure.tts.gpt_sovits import GPTSoVITSEngine
            url = config.get("url", "http://localhost:9872")
            return GPTSoVITSEngine(base_url=url)
        except Exception as e:
            logger.error(f"GPT-SoVITS 엔진 생성 실패: {e}")
            return None

    elif model == "f5tts":
        try:
            from infrastructure.tts.base import BaseTTSEngine
            # F5-TTS (한국어/영어) - 기존 TTSFactory 사용
            from infrastructure.tts.factory import TTSFactory
            return TTSFactory.create(language or "ko")
        except Exception as e:
            logger.error(f"F5-TTS 엔진 생성 실패: {e}")
            return None

    elif model == "f5tts_thai":
        try:
            from infrastructure.tts.f5_tts_thai import F5TTSThaiEngine
            return F5TTSThaiEngine()
        except Exception as e:
            logger.error(f"F5-TTS-Thai 엔진 생성 실패: {e}")
            return None

    else:
        logger.error(f"Unknown local TTS model: {model}")
        return None


def _create_api_engine(model: str, language: str = None) -> Optional[object]:
    """API 기반 TTS 엔진 생성"""
    import os
    config = TTS_MODEL_CONFIGS.get(model, {})

    if model == "azure":
        api_key_env = config.get("api_key_env", "AZURE_TTS_KEY")
        region_env = config.get("region_env", "AZURE_TTS_REGION")
        api_key = os.getenv(api_key_env, "")
        region = os.getenv(region_env, "southeastasia")

        if not api_key:
            logger.error("AZURE_TTS_KEY가 설정되지 않았습니다")
            return None

        try:
            from infrastructure.tts.azure_tts import AzureTTSEngine
            return AzureTTSEngine(api_key=api_key, region=region)
        except Exception as e:
            logger.error(f"Azure TTS 엔진 생성 실패: {e}")
            return None

    elif model == "edge":
        try:
            from infrastructure.tts.edge_tts import EdgeTTSEngine
            return EdgeTTSEngine()
        except Exception as e:
            logger.error(f"Edge TTS 엔진 생성 실패: {e}")
            return None

    else:
        logger.error(f"Unknown API TTS model: {model}")
        return None


def get_tts_engine_info(language: str = None) -> dict:
    """현재 TTS 설정 정보 반환"""
    from config.api_config import get_tts_config_for
    return get_tts_config_for(language or "ko")
