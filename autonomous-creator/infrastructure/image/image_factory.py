"""
Image Generator Factory - 설정 기반 이미지 생성기 스위칭

config/api_config.py의 IMAGE_PROVIDER, IMAGE_LOCAL_MODEL, IMAGE_API_MODEL 설정에 따라
적절한 이미지 생성기를 반환합니다.

사용법:
    from infrastructure.image.image_factory import create_image_generator

    generator = await create_image_generator()  # 설정에 따라 자동 선택
    image = await generator.generate(prompt="...", preset=preset, output_path="out.png")
"""
import logging
from typing import Optional

from config.api_config import (
    IMAGE_PROVIDER, IMAGE_LOCAL_MODEL, IMAGE_API_MODEL,
    IMAGE_MODEL_CONFIGS, get_image_config,
)
from core.domain.interfaces.image_generator import IImageGenerator

logger = logging.getLogger(__name__)


async def create_image_generator(
    provider: str = None,
    model: str = None,
) -> Optional[IImageGenerator]:
    """
    설정에 따라 이미지 생성기를 생성

    Args:
        provider: "local" | "api" (None이면 설정값 사용)
        model: 모델명 (None이면 설정값 사용)

    Returns:
        IImageGenerator 인스턴스
    """
    _provider = provider or IMAGE_PROVIDER
    _model = model or (IMAGE_API_MODEL if _provider == "api" else IMAGE_LOCAL_MODEL)

    logger.info(f"Image Generator 생성: provider={_provider}, model={_model}")

    if _provider == "local":
        return await _create_local_generator(_model)
    elif _provider == "api":
        return await _create_api_generator(_model)
    else:
        logger.error(f"Unknown IMAGE_PROVIDER: {_provider}")
        return None


async def _create_local_generator(model: str) -> Optional[IImageGenerator]:
    """로컬 이미지 생성기 생성"""
    config = IMAGE_MODEL_CONFIGS.get(model, {})

    if model == "sdxl":
        from infrastructure.image.sdxl_generator import SDXLGenerator
        generator = SDXLGenerator()
        await generator.load_model()
        logger.info(f"SDXL Generator 로드 완료: {config.get('model_name')}")
        return generator

    elif model == "sd35":
        from infrastructure.image.sd35_generator import SD35Generator
        generator = SD35Generator()
        await generator.load_model()
        logger.info(f"SD35 Generator 로드 완료: {config.get('model_name')}")
        return generator

    else:
        logger.error(f"Unknown local image model: {model}")
        return None


async def _create_api_generator(model: str) -> Optional[IImageGenerator]:
    """API 기반 이미지 생성기 생성"""
    config = IMAGE_MODEL_CONFIGS.get(model, {})

    if model == "stability":
        import os
        api_key = os.getenv(config.get("api_key_env", "STABILITY_API_KEY"), "")
        if not api_key:
            logger.error("STABILITY_API_KEY가 설정되지 않았습니다")
            return None

        from infrastructure.api.providers.image.stability_sd35 import StabilitySD35Client
        client = StabilitySD35Client(api_key=api_key)
        logger.info("Stability API client 생성 완료")
        return client

    elif model == "dalle":
        import os
        api_key = os.getenv(config.get("api_key_env", "OPENAI_API_KEY"), "")
        if not api_key:
            logger.error("OPENAI_API_KEY가 설정되지 않았습니다")
            return None
        logger.warning("DALL-E 생성기는 아직 구현되지 않았습니다")
        return None

    else:
        logger.error(f"Unknown API image model: {model}")
        return None


def get_image_generator_info() -> dict:
    """현재 이미지 생성 설정 정보 반환"""
    return get_image_config()
