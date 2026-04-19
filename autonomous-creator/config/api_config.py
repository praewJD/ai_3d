"""
API 설정 - 모든 API 키를 한 곳에서 관리

대본 생성: STORY_API_KEY 사용 (1차 컴파일, 2차 재시도 모두 동일 키)
비디오 생성: VIDEO_API_KEY 사용 (별도 키)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# 대본 생성 API
# UnifiedStoryCompiler, ShortDramaCompiler 공통 사용
# ═══════════════════════════════════════════════════════════════
STORY_API_KEY = os.getenv("STORY_API_KEY", "sk-cp-j62Q8G03YoHNLH188yvNcBV4poXXGOtW09fI_hSyUbL-nY4_T3Y_hVmq8sU-YYAD4McAcBxd6lT2SvA8kKpzifundy8uAQcshq1pJwKxnCtZFY0VT5OSRI8")
STORY_API_URL = os.getenv("STORY_API_URL", "https://api.minimax.io/anthropic/v1/messages")
STORY_MODEL = os.getenv("STORY_MODEL", "MiniMax-M2.7")
STORY_MAX_TOKENS = int(os.getenv("STORY_MAX_TOKENS", "4096"))

# ═══════════════════════════════════════════════════════════════
# 비디오 생성 API
# ═══════════════════════════════════════════════════════════════
VIDEO_API_KEY = os.getenv("VIDEO_API_KEY", "")
VIDEO_API_URL = os.getenv("VIDEO_API_URL", "")
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "")

# ═══════════════════════════════════════════════════════════════
# 이미지 생성 (로컬 SDXL)
# ═══════════════════════════════════════════════════════════════
SD_MODEL = os.getenv("SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
SD_DEVICE = os.getenv("SD_DEVICE", "cuda")
SD_LOW_VRAM = os.getenv("SD_LOW_VRAM", "true").lower() == "true"

# ═══════════════════════════════════════════════════════════════
# 다국어 설정
# STORY_LANGUAGES: 대본/영상 생성 타겟 언어 목록
# 쉼표로 구분 (예: "ko", "ko,th", "ko,th,vi")
# ═══════════════════════════════════════════════════════════════
STORY_LANGUAGES = [lang.strip() for lang in os.getenv("STORY_LANGUAGES", "ko").split(",") if lang.strip()]

# ═══════════════════════════════════════════════════════════════
# 모듈별 Provider/Model 설정
# Provider: "local" | "api" | "hybrid" (영상만)
# Model: Provider 내에서 사용할 구체적 모델명
# ═══════════════════════════════════════════════════════════════

# --- 이미지 생성 ---
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "local")  # "local" | "api"
IMAGE_LOCAL_MODEL = os.getenv("IMAGE_LOCAL_MODEL", "sdxl")  # "sdxl" | "sd35"
IMAGE_API_MODEL = os.getenv("IMAGE_API_MODEL", "stability")  # "stability" | "dalle"

# --- 영상 생성 ---
VIDEO_PROVIDER = os.getenv("VIDEO_PROVIDER", "hybrid")  # "local" | "api" | "hybrid"
VIDEO_LOCAL_MODEL = os.getenv("VIDEO_LOCAL_MODEL", "svd")  # "svd" | "framepack"
VIDEO_API_MODEL = os.getenv("VIDEO_API_MODEL", "luma")  # "luma" | "runway" | "kling"

# --- TTS ---
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "local")  # "local" | "api" | "auto"
TTS_LOCAL_MODEL = os.getenv("TTS_LOCAL_MODEL", "gpt_sovits")  # "gpt_sovits" | "f5tts" | "f5tts_thai"
TTS_API_MODEL = os.getenv("TTS_API_MODEL", "azure")  # "azure" | "edge"

# ═══════════════════════════════════════════════════════════════
# Pipeline 설정 (TTS / 립싱크)
# ═══════════════════════════════════════════════════════════════
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"
LIPSYNC_ENABLED = os.getenv("LIPSYNC_ENABLED", "true").lower() == "true"
LIPSYNC_MODE = os.getenv("LIPSYNC_MODE", "auto")  # auto | forced | disabled

# ═══════════════════════════════════════════════════════════════
# 모델별 세부 설정
# 새 모델 추가 시 해당 딕셔너리에 항목만 추가
# ═══════════════════════════════════════════════════════════════

IMAGE_MODEL_CONFIGS = {
    "sdxl": {
        "model_name": "stabilityai/stable-diffusion-xl-base-1.0",
        "device": SD_DEVICE,
        "low_vram": SD_LOW_VRAM,
        "default_steps": 25,
        "default_cfg": 7.5,
    },
    "sd35": {
        "model_name": "stabilityai/stable-diffusion-3.5-medium",
        "device": SD_DEVICE,
        "low_vram": SD_LOW_VRAM,
        "default_steps": 28,
        "default_cfg": 4.5,
    },
    "stability": {
        "api_key_env": "STABILITY_API_KEY",
        "model": "sd3.5-large",
        "default_steps": 30,
    },
    "dalle": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "dall-e-3",
        "size": "1024x1792",  # 9:16 세로
    },
}

VIDEO_MODEL_CONFIGS = {
    "svd": {
        "model_name": "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
        "device": SD_DEVICE,
        "vram_required": 12,
        "default_duration": 3,
        "default_fps": 8,
    },
    "framepack": {
        "model_name": "",
        "device": SD_DEVICE,
        "default_duration": 5,
        "default_fps": 16,
    },
    "luma": {
        "api_key_env": "LUMA_API_KEY",
        "model": "kling-2.6",
        "resolution": "1080p",
        "default_duration": 5,
    },
    "runway": {
        "api_key_env": "RUNWAY_API_KEY",
        "model": "gen-3-alpha",
        "default_duration": 5,
    },
    "kling": {
        "api_key_env": "KLING_API_KEY",
        "model": "kling-v2",
        "default_duration": 5,
    },
}

TTS_MODEL_CONFIGS = {
    "gpt_sovits": {
        "url": "http://localhost:9872",
        "languages": ["ko", "ja", "zh"],
        "sample_rate": 32000,
    },
    "f5tts": {
        "model_name": "SWivid/F5-TTS",
        "languages": ["ko", "en"],
        "sample_rate": 24000,
    },
    "f5tts_thai": {
        "model_name": "VIZINTZOR/F5-TTS-THAI",
        "languages": ["th"],
        "sample_rate": 24000,
    },
    "azure": {
        "api_key_env": "AZURE_TTS_KEY",
        "region_env": "AZURE_TTS_REGION",
        "languages": ["ko", "en", "ja", "zh", "th", "vi"],
        "sample_rate": 16000,
    },
    "edge": {
        "languages": ["en", "ko", "ja", "zh", "th"],
        "sample_rate": 24000,
    },
    "no_tts": {
        "languages": [],
        "sample_rate": 0,
        "description": "TTS 비활성화 - 오디오 없이 비디오만 생성",
    },
}


def get_image_config() -> dict:
    """현재 이미지 설정 반환"""
    if IMAGE_PROVIDER == "api":
        model = IMAGE_API_MODEL
    else:
        model = IMAGE_LOCAL_MODEL
    return {
        "provider": IMAGE_PROVIDER,
        "model": model,
        "config": IMAGE_MODEL_CONFIGS.get(model, {}),
    }


def get_video_config() -> dict:
    """현재 영상 설정 반환"""
    if VIDEO_PROVIDER == "api":
        model = VIDEO_API_MODEL
    elif VIDEO_PROVIDER == "hybrid":
        model = "hybrid"
    else:
        model = VIDEO_LOCAL_MODEL
    return {
        "provider": VIDEO_PROVIDER,
        "model": model,
        "config": VIDEO_MODEL_CONFIGS.get(model, {}),
        "api_model": VIDEO_API_MODEL,
        "local_model": VIDEO_LOCAL_MODEL,
    }


def get_tts_config_for(language: str) -> dict:
    """언어에 맞는 TTS 설정 반환"""
    from infrastructure.tts.tts_config import get_tts_config as _get_tts_lang_config

    # 언어별 TTS 모델 정보도 함께 반환
    lang_config = _get_tts_lang_config(language)
    return {
        "provider": TTS_PROVIDER,
        "model": TTS_LOCAL_MODEL if TTS_PROVIDER == "local" else TTS_API_MODEL,
        "config": TTS_MODEL_CONFIGS.get(
            TTS_LOCAL_MODEL if TTS_PROVIDER == "local" else TTS_API_MODEL, {}
        ),
        "language": language,
        "language_config": lang_config,
    }


def get_pipeline_config() -> dict:
    """파이프라인 실행 설정 반환"""
    if TTS_ENABLED:
        steps = ["image", "tts", "video"]
    else:
        steps = ["image", "video"]

    return {
        "tts_enabled": TTS_ENABLED,
        "lipsync_enabled": LIPSYNC_ENABLED,
        "lipsync_mode": LIPSYNC_MODE,
        "steps": steps,
        "video_needs_audio": TTS_ENABLED and LIPSYNC_ENABLED,
    }
