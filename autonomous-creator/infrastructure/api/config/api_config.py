"""
API Configuration - 모든 API 설정을 한 곳에서 관리

Pydantic Settings 기반으로 환경변수에서 자동 로드
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from enum import Enum


class VideoGenerationStrategy(str, Enum):
    """비디오 생성 전략"""
    ALL_API = "all_api"              # 모든 장면 API 사용 (최고 품질, 비용 최대)
    KEY_SCENES_API = "key_scenes"    # 핵심 장면만 API (균형, 추천)
    SMART_HYBRID = "smart_hybrid"    # 장면별 자동 판단 (지능형)
    LOCAL_FIRST = "local_first"      # 로컬 우선, 실패시 API (비용 최소)


class ArtStyle(str, Enum):
    """아트 스타일"""
    ANIME_2D = "anime_2d"           # 2D 애니메이션
    ANIME_3D = "anime_3d"           # 3D 애니메이션 (추천)
    REALISTIC = "realistic"          # 실사
    CARTOON = "cartoon"              # 카툰
    WATERCOLOR = "watercolor"        # 수채화
    OIL_PAINTING = "oil_painting"    # 유화


class APIConfig(BaseSettings):
    """
    통합 API 설정

    모든 외부 API 키와 설정을 중앙 관리
    """

    # ============================================================
    # LLM API
    # ============================================================
    claude_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic Claude API Key"
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude 모델"
    )
    claude_max_tokens: int = Field(default=4096)

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API Key"
    )
    openai_model: str = Field(default="gpt-4o")

    # GLM (Zhipu AI)
    glm_api_key: Optional[str] = Field(
        default=None,
        description="Zhipu AI GLM API Key"
    )
    glm_api_url: str = Field(
        default="https://api.z.ai/api/anthropic/v1/messages",
        description="GLM API URL (z.ai Anthropic 호환)"
    )
    glm_model: str = Field(
        default="glm-5",
        description="GLM 모델 (glm-5, glm-4, glm-4-flash, glm-4-plus)"
    )
    glm_max_tokens: int = Field(default=4096)

    # ============================================================
    # Video Generation API
    # ============================================================
    luma_api_key: Optional[str] = Field(
        default=None,
        description="Luma Dream Machine API Key"
    )
    luma_default_model: str = Field(
        default="kling-2.6",
        description="기본 비디오 모델 (kling-2.6, ray-3.14, veo-3)"
    )
    luma_default_resolution: str = Field(default="1080p")
    luma_default_duration: int = Field(default=5)

    runway_api_key: Optional[str] = Field(
        default=None,
        description="Runway API Key"
    )
    runway_default_model: str = Field(default="gen-3-alpha")

    kling_api_key: Optional[str] = Field(
        default=None,
        description="Kling AI API Key"
    )

    # ============================================================
    # 💰 비용 최적화 설정 (NEW)
    # ============================================================
    video_generation_strategy: VideoGenerationStrategy = Field(
        default=VideoGenerationStrategy.KEY_SCENES_API,
        description="비디오 생성 전략"
    )

    # 핵심 장면 비율 (KEY_SCENES_API 전략용)
    key_scene_ratio: float = Field(
        default=0.3,
        description="핵심 장면 비율 (0.0~1.0)"
    )

    # 월간 예산 제한
    monthly_budget_usd: Optional[float] = Field(
        default=100.0,
        description="월간 API 예산 (USD)"
    )

    # 자동 비용 절감
    auto_cost_saving: bool = Field(
        default=True,
        description="예산 초과 시 자동으로 로컬 전환"
    )

    # API 사용 임계값
    api_usage_warning_threshold: float = Field(
        default=0.8,
        description="API 사용량 경고 임계값 (80%)"
    )

    # ============================================================
    # 🎨 스타일 설정 (NEW)
    # ============================================================
    default_art_style: ArtStyle = Field(
        default=ArtStyle.ANIME_3D,
        description="기본 아트 스타일"
    )

    # 3D 애니메이션 세부 설정
    anime_3d_lighting: str = Field(
        default="soft_studio",
        description="3D 조명 스타일 (soft_studio, dramatic, outdoor, neon)"
    )
    anime_3d_render_quality: str = Field(
        default="high",
        description="렌더링 품질 (low, medium, high, ultra)"
    )
    anime_3d_shader: str = Field(
        default="cel_shaded",
        description="셰이더 스타일 (cel_shaded, toon, realistic_mix)"
    )

    # ============================================================
    # TTS API
    # ============================================================
    azure_tts_key: Optional[str] = Field(default=None)
    azure_tts_region: str = Field(default="southeastasia")

    elevenlabs_api_key: Optional[str] = Field(default=None)

    # ============================================================
    # Image Generation
    # ============================================================
    stability_api_key: Optional[str] = Field(
        default=None,
        description="Stability AI API Key (클라우드 사용시)"
    )

    # 이미지 생성 설정
    image_default_style_prefix: str = Field(
        default="3D anime style, Pixar quality, smooth shading",
        description="이미지 생성 기본 스타일 접두사"
    )
    image_negative_prompt: str = Field(
        default="realistic, photo, live action, western style, rough",
        description="네거티브 프롬프트"
    )

    # ============================================================
    # 공통 설정
    # ============================================================
    api_timeout: int = Field(default=120, description="API 요청 타임아웃 (초)")
    api_max_retries: int = Field(default=3, description="최대 재시도 횟수")
    api_retry_backoff: float = Field(default=2.0, description="재시도 backoff 배수")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60)
    rate_limit_per_second: int = Field(default=10)

    # ============================================================
    # 로컬 모델 설정
    # ============================================================
    use_local_models: bool = Field(
        default=True,
        description="로컬 모델 우선 사용"
    )
    sd_device: str = Field(default="cuda")
    sd_low_vram: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""  # 접두사 없음
        extra = "ignore"  # 정의되지 않은 필드 무시

    # ============================================================
    # 프로퍼티
    # ============================================================

    @property
    def has_luma(self) -> bool:
        """Luma API 사용 가능 여부"""
        return self.luma_api_key is not None

    @property
    def has_runway(self) -> bool:
        """Runway API 사용 가능 여부"""
        return self.runway_api_key is not None

    @property
    def has_claude(self) -> bool:
        """Claude API 사용 가능 여부"""
        return self.claude_api_key is not None

    @property
    def has_openai(self) -> bool:
        """OpenAI API 사용 가능 여부"""
        return self.openai_api_key is not None

    @property
    def has_glm(self) -> bool:
        """GLM (Zhipu AI) 사용 가능 여부"""
        return self.glm_api_key is not None

    def get_available_llm_providers(self) -> list[str]:
        """사용 가능한 LLM 프로바이더 목록"""
        providers = []
        if self.has_claude:
            providers.append("claude")
        if self.has_openai:
            providers.append("openai")
        if self.has_glm:
            providers.append("glm")
        return providers

    def get_recommended_llm_provider(self) -> str:
        """추천 LLM 프로바이더 (GLM 우선)"""
        if self.has_glm:
            return "glm"
        if self.has_claude:
            return "claude"
        if self.has_openai:
            return "openai"
        return "none"

    @property
    def is_3d_anime_style(self) -> bool:
        """3D 애니메이션 스타일 여부"""
        return self.default_art_style == ArtStyle.ANIME_3D

    def get_available_video_providers(self) -> list[str]:
        """사용 가능한 비디오 생성 프로바이더 목록"""
        providers = []
        if self.has_luma:
            providers.append("luma")
        if self.has_runway:
            providers.append("runway")
        if self.use_local_models:
            providers.append("local")
        return providers

    def get_recommended_video_provider(self) -> str:
        """추천 비디오 생성 프로바이더"""
        providers = self.get_available_video_providers()
        # Luma > Runway > Local 순서
        for p in ["luma", "runway", "local"]:
            if p in providers:
                return p
        return "local"

    def get_style_prompt_prefix(self) -> str:
        """스타일별 프롬프트 접두사 반환"""
        style_prefixes = {
            ArtStyle.ANIME_2D: "anime style, 2D animation, hand drawn aesthetic, vibrant colors",
            ArtStyle.ANIME_3D: "3D anime style, Pixar quality, smooth cel shading, beautiful lighting",
            ArtStyle.REALISTIC: "photorealistic, hyperrealistic, photography, 8k",
            ArtStyle.CARTOON: "cartoon style, bold lines, vibrant colors, exaggerated features",
            ArtStyle.WATERCOLOR: "watercolor painting, soft edges, artistic, traditional media",
            ArtStyle.OIL_PAINTING: "oil painting, classic art style, rich textures, painterly"
        }
        return style_prefixes.get(self.default_art_style, self.image_default_style_prefix)

    def get_negative_prompt(self) -> str:
        """스타일별 네거티브 프롬프트"""
        base_negative = self.image_negative_prompt
        style_negatives = {
            ArtStyle.ANIME_3D: "realistic, photo, live action, western cartoon, rough lines, low poly",
            ArtStyle.ANIME_2D: "3D, realistic, photo, cgi, western style",
            ArtStyle.REALISTIC: "anime, cartoon, illustration, drawing, sketch"
        }
        style_neg = style_negatives.get(self.default_art_style, "")
        return f"{base_negative}, {style_neg}" if style_neg else base_negative

    def estimate_monthly_cost(
        self,
        total_minutes: float,
        key_scene_ratio: float = None
    ) -> dict:
        """
        월간 예상 비용 계산

        Args:
            total_minutes: 총 영상 길이 (분)
            key_scene_ratio: 핵심 장면 비율

        Returns:
            비용 추정 딕셔너리
        """
        ratio = key_scene_ratio or self.key_scene_ratio

        # Luma Kling 1080p: 29 credits/초
        credits_per_second = 29
        seconds = total_minutes * 60

        # 전략별 계산
        if self.video_generation_strategy == VideoGenerationStrategy.ALL_API:
            api_seconds = seconds
        elif self.video_generation_strategy == VideoGenerationStrategy.KEY_SCENES_API:
            api_seconds = seconds * ratio
        elif self.video_generation_strategy == VideoGenerationStrategy.SMART_HYBRID:
            api_seconds = seconds * 0.4  # 약 40%만 API
        else:  # LOCAL_FIRST
            api_seconds = seconds * 0.1  # 10%만 API (실패시)

        total_credits = api_seconds * credits_per_second

        # Luma Pro 플랜: $90/월 = 약 9000 credits
        cost_usd = (total_credits / 9000) * 90

        return {
            "total_seconds": seconds,
            "api_seconds": api_seconds,
            "local_seconds": seconds - api_seconds,
            "total_credits": total_credits,
            "estimated_cost_usd": round(cost_usd, 2),
            "within_budget": cost_usd <= self.monthly_budget_usd if self.monthly_budget_usd else True,
            "strategy": self.video_generation_strategy.value
        }


@lru_cache()
def get_api_config() -> APIConfig:
    """API 설정 싱글톤"""
    return APIConfig()

