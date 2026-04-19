"""
Application Settings

Pydantic Settings 기반 설정 관리
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    애플리케이션 설정

    환경 변수 또는 .env 파일에서 로드
    """

    # App
    app_name: str = "Autonomous Creator"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/autonomous_creator.db",
        description="데이터베이스 연결 URL"
    )

    # Paths
    output_dir: str = "outputs"
    models_dir: str = "models"

    # TTS Settings
    gpt_sovits_url: str = "http://localhost:9872"
    azure_tts_key: Optional[str] = None
    azure_tts_region: str = "southeastasia"

    # AI Settings
    sd_model: str = "stabilityai/stable-diffusion-3.5-medium"
    sd_device: str = "cuda"
    sd_low_vram: bool = False  # 6-8GB VRAM 모드

    # Claude API
    claude_api_key: Optional[str] = None

    # Video Settings
    video_resolution: tuple[int, int] = (1080, 1920)  # 9:16
    video_fps: int = 30
    video_quality: str = "fhd"

    # SVD Settings
    svd_enabled: bool = True
    svd_model: str = "stabilityai/stable-video-diffusion-img2vid-xt-1-1"
    svd_vram_required: int = 12  # GB

    # [신규] IP-Adapter Settings
    ip_adapter_enabled: bool = True
    ip_adapter_model_path: str = "models/ip-adapter"
    ip_adapter_strength: float = 0.8
    ip_adapter_num_tokens: int = 16

    # [신규] Character Cache Settings
    character_cache_dir: str = "data/character_cache"
    character_cache_enabled: bool = True

    # [신규] Location DB Settings
    location_db_dir: str = "data/locations"

    # [신규] Claude API (LLM 추출용)
    anthropic_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 필드 무시

    @property
    def is_vertical_video(self) -> bool:
        """세로 영상 여부"""
        return self.video_resolution[0] < self.video_resolution[1]


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스 반환 (캐싱)

    Returns:
        Settings 인스턴스
    """
    return Settings()
