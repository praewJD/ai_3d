"""
Video Generator Factory - 설정 기반 영상 생성기 스위칭

config/api_config.py의 VIDEO_PROVIDER, VIDEO_LOCAL_MODEL, VIDEO_API_MODEL 설정에 따라
적절한 영상 생성기를 반환합니다.

사용법:
    from infrastructure.video.video_factory import create_video_generator
    generator = await create_video_generator()
    video = await generator.generate(...)
"""
import logging
from typing import Optional

from config.api_config import (
    VIDEO_PROVIDER, VIDEO_LOCAL_MODEL, VIDEO_API_MODEL,
    VIDEO_MODEL_CONFIGS, get_video_config,
)

logger = logging.getLogger(__name__)


async def create_video_generator(
    provider: str = None,
    model: str = None,
) -> Optional[object]:
    """
    설정에 따라 영상 생성기 생성

    Args:
        provider: "local" | "api" | "hybrid" (None이면 설정값 사용)
        model: 모델명 (None이면 설정값 사용)

    Returns:
        영상 생성기 인스턴스
    """
    _provider = provider or VIDEO_PROVIDER
    _model = model or (VIDEO_API_MODEL if _provider == "api" else VIDEO_LOCAL_MODEL)

    logger.info(f"Video Generator 생성: provider={_provider}, model={_model}")

    if _provider == "local":
        return await _create_local_generator(_model)
    elif _provider == "api":
        return await _create_api_generator(_model)
    elif _provider == "hybrid":
        return await _create_hybrid_generator()
    else:
        logger.error(f"Unknown VIDEO_PROVIDER: {_provider}")
        return None


async def _create_local_generator(model: str) -> Optional[object]:
    """로컬 영상 생성기 생성"""
    config = VIDEO_MODEL_CONFIGS.get(model, {})

    if model == "svd":
        try:
            from infrastructure.video.svd_generator import SVDGenerator
            generator = SVDGenerator()
            logger.info(f"SVD Generator 로드 완료: {config.get('model_name')}")
            return generator
        except Exception as e:
            logger.error(f"SVD Generator 로드 실패: {e}")
            return None

    elif model == "framepack":
        try:
            from infrastructure.video.framepack_generator import FramePackGenerator
            generator = FramePackGenerator()
            logger.info("FramePack Generator 로드 완료")
            return generator
        except Exception as e:
            logger.error(f"FramePack Generator 로드 실패: {e}")
            return None

    else:
        logger.error(f"Unknown local video model: {model}")
        return None


async def _create_api_generator(model: str) -> Optional[object]:
    """API 기반 영상 생성기 생성"""
    import os
    config = VIDEO_MODEL_CONFIGS.get(model, {})
    api_key_env = config.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "") if api_key_env else ""

    if model == "luma":
        if not api_key:
            logger.error("LUMA_API_KEY가 설정되지 않았습니다")
            return None
        try:
            from infrastructure.video.luma_adapter import LumaVideoAdapter, LumaAdapterConfig
            adapter_config = LumaAdapterConfig(
                api_key=api_key,
                model=config.get("model", "kling-2.6"),
                resolution=config.get("resolution", "1080p"),
                default_duration=config.get("default_duration", 5),
            )
            provider = LumaVideoAdapter(config=adapter_config)
            logger.info("Luma API Adapter 생성 완료")
            return provider
        except Exception as e:
            logger.error(f"Luma Adapter 생성 실패: {e}")
            return None

    elif model in ("runway", "kling"):
        if not api_key:
            logger.error(f"{api_key_env}가 설정되지 않았습니다")
            return None
        logger.warning(f"{model} Provider는 아직 구현되지 않았습니다")
        return None

    else:
        logger.error(f"Unknown API video model: {model}")
        return None


async def _create_hybrid_generator() -> Optional[object]:
    """하이브리드 영상 생성기 생성 (API + 로컬 자동 분기)"""
    try:
        from infrastructure.video.hybrid_manager import HybridVideoManager
        manager = HybridVideoManager()
        logger.info("Hybrid Video Manager 생성 완료")
        return manager
    except Exception as e:
        logger.error(f"Hybrid Video Manager 생성 실패: {e}")
        # 폴백: 로컬 생성기
        logger.info("폴백: 로컬 영상 생성기 사용")
        return await _create_local_generator(VIDEO_LOCAL_MODEL)


def should_use_lipsync() -> bool:
    """
    립싱크 사용 여부 확인

    TTS가 활성화되고 립싱크도 활성화된 경우에만 True 반환.
    비디오 생성 시 audio_path 전달 여부를 결정하는 데 사용합니다.
    """
    from config.api_config import get_pipeline_config
    config = get_pipeline_config()
    return config.get("video_needs_audio", False)


def get_video_generator_info() -> dict:
    """현재 영상 생성 설정 정보 반환"""
    return get_video_config()
