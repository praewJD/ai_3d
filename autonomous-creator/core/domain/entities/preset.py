"""
Style Preset Domain Entity

영상 스타일 프리셋 정의
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class StylePreset(BaseModel):
    """
    스타일 프리셋

    영상의 시각적 스타일을 정의하고 재사용 가능하게 저장
    """
    id: str = Field(default_factory=lambda: f"preset_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., min_length=1, max_length=50, description="프리셋 이름")
    description: str = Field(default="", max_length=500, description="프리셋 설명")

    # 이미지 생성 프롬프트
    base_prompt: str = Field(
        default="",
        description="기본 프롬프트 (모든 이미지에 적용)"
    )
    negative_prompt: str = Field(
        default="ugly, blurry, low quality, distorted, watermark",
        description="네거티브 프롬프트"
    )

    # SD 파라미터
    seed: int = Field(default=-1, ge=-1, description="시드값 (-1 = 랜덤)")
    cfg_scale: float = Field(default=7.5, ge=1.0, le=20.0, description="CFG Scale")
    steps: int = Field(default=30, ge=10, le=50, description="Inference Steps")
    sampler: str = Field(default="dpmpp_2m", description="Sampler")

    # IP-Adapter 설정
    ip_adapter_ref: Optional[str] = Field(
        default=None,
        description="IP-Adapter 참조 이미지 경로"
    )
    ip_adapter_scale: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="IP-Adapter 영향도 (0=텍스트만, 1=이미지만)"
    )

    # LoRA 설정
    lora_weights: Optional[str] = Field(
        default=None,
        description="LoRA 가중치 파일 경로"
    )
    lora_scale: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="LoRA 강도"
    )

    # 추가 설정
    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="추가 파라미터 (확장용)"
    )

    # 메타데이터
    is_default: bool = Field(default=False, description="기본 프리셋 여부")
    created_at: datetime = Field(default_factory=datetime.now, description="생성 일시")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 일시")

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now()

    class Config:
        json_schema_extra = {
            "example": {
                "id": "preset_abc123",
                "name": "Cute Anime v1",
                "description": "귀여운 애니메이션 스타일",
                "base_prompt": "anime style, soft pastel colors, cute character, detailed",
                "negative_prompt": "realistic, photo, 3d render, ugly, blurry",
                "seed": 12345,
                "cfg_scale": 7.5,
                "steps": 30,
                "sampler": "dpmpp_2m",
                "ip_adapter_ref": "refs/character_001.png",
                "ip_adapter_scale": 0.8,
                "lora_weights": None,
                "lora_scale": 1.0,
                "extra_params": {},
                "is_default": False,
                "created_at": "2026-03-29T10:00:00",
                "updated_at": "2026-03-29T10:00:00"
            }
        }

    @classmethod
    def create_default(cls) -> "StylePreset":
        """기본 프리셋 생성 (3D 애니메이션 스타일)"""
        return cls(
            name="3D Anime Default",
            description="3D 애니메이션 기본 스타일 - Pixar 퀄리티",
            base_prompt="3D anime style, Pixar quality, smooth cel shading, beautiful lighting, clean renders, Disney animation quality",
            negative_prompt="realistic photo, live action, western cartoon, rough lines, low poly, ugly 3d, bad shading, plastic look, blurry, low quality",
            seed=-1,
            cfg_scale=7.5,
            steps=30,
            is_default=True
        )


# 사전 정의된 프리셋들
DEFAULT_PRESETS = [
    StylePreset(
        name="3D Anime Default",
        description="3D 애니메이션 기본 스타일 - Pixar 퀄리티",
        base_prompt="3D anime style, Pixar quality, smooth cel shading, beautiful lighting, clean renders, Disney animation quality",
        negative_prompt="realistic photo, live action, western cartoon, rough lines, low poly, ugly 3d, bad shading",
        cfg_scale=7.5,
        steps=30,
        is_default=True
    ),
    StylePreset(
        name="3D Anime Dramatic",
        description="드라마틱한 3D 애니메이션 - 시네마틱 조명",
        base_prompt="3D anime style, dramatic cinematic lighting, volumetric light, epic atmosphere, Pixar quality, smooth shading",
        negative_prompt="realistic photo, flat lighting, boring, low quality, rough",
        cfg_scale=8.0,
        steps=35
    ),
    StylePreset(
        name="3D Anime Soft",
        description="부드러운 3D 애니메이션 - 따뜻한 분위기",
        base_prompt="3D anime style, soft studio lighting, gentle shadows, warm colors, peaceful atmosphere, Pixar quality",
        negative_prompt="realistic photo, harsh lighting, dark, gritty, rough",
        cfg_scale=7.0,
        steps=30
    ),
    StylePreset(
        name="3D Anime Fantasy",
        description="판타지 3D 애니메이션 - 마법 같은 분위기",
        base_prompt="3D anime style, magical atmosphere, glowing effects, ethereal lighting, fantasy world, Pixar quality, sparkles",
        negative_prompt="realistic photo, modern, mundane, boring, low quality",
        cfg_scale=7.5,
        steps=35
    ),
    StylePreset(
        name="3D Anime Cyberpunk",
        description="사이버펑크 3D 애니메이션 - 네온 조명",
        base_prompt="3D anime style, neon lights, cyberpunk atmosphere, glowing effects, futuristic, Pixar quality, rain reflections",
        negative_prompt="realistic photo, daylight, natural, old fashioned, low quality",
        cfg_scale=8.0,
        steps=35
    ),
    StylePreset(
        name="2D Anime Classic",
        description="클래식 2D 애니메이션 스타일",
        base_prompt="anime style, 2D animation, hand drawn aesthetic, vibrant colors, detailed illustration, clean lines",
        negative_prompt="3D, realistic, photo, cgi, western style, rough lines",
        cfg_scale=7.5,
        steps=30
    ),
]
