"""
Style Preset Asset - 스타일 프리셋 관리

스타일 프리셋 저장, 조회, 검색
"""
import json
import asyncio
import aiofiles
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class StylePresetAsset:
    """
    스타일 프리셋 데이터 클래스

    이미지/영상의 시각적 스타일을 정의하고 재사용
    """
    id: str
    name: str
    description: str

    # 기본 프롬프트
    base_prompt: str = ""
    negative_prompt: str = "ugly, blurry, low quality, distorted, watermark"

    # 스타일 타입
    style_type: str = "disney_3d"  # disney_3d, realistic, anime, watercolor, pixel_art

    # SD 파라미터
    seed: int = -1
    cfg_scale: float = 7.5
    steps: int = 30
    sampler: str = "dpmpp_2m"

    # IP-Adapter 설정
    ip_adapter_ref: Optional[str] = None
    ip_adapter_scale: float = 0.8

    # LoRA 설정
    lora_weights: Optional[str] = None
    lora_scale: float = 1.0

    # 조명 설정
    lighting_type: str = "soft"  # natural, studio, dramatic, soft, harsh, neon

    # 컬러 팔레트
    color_palette: str = "vibrant_warm"  # vibrant_warm, muted_cool, pastel, dark_moody

    # 렌더링 설정
    rendering_type: str = "cel_shaded"  # standard, cinematic, flat, cel_shaded, painterly

    # 추가 파라미터
    extra_params: Dict[str, Any] = field(default_factory=dict)

    # 메타데이터
    is_default: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 사용 통계
    usage_count: int = 0
    last_used_at: Optional[str] = None

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now().isoformat()

    def increment_usage(self) -> None:
        """사용 횟수 증가"""
        self.usage_count += 1
        self.last_used_at = datetime.now().isoformat()

    def to_full_prompt(self, scene_description: str = "") -> str:
        """전체 프롬프트 생성"""
        parts = []

        # 스타일 타입별 프롬프트
        style_prompts = {
            "disney_3d": (
                "Disney 3D animation style, Pixar quality, "
                "soft global illumination, expressive characters, "
                "stylized proportions, vibrant colors, "
                "smooth cel shading, high quality 3D render"
            ),
            "realistic": (
                "photorealistic, cinematic lighting, "
                "film grain, real world textures, "
                "natural skin tones, detailed environment, "
                "8K resolution, professional photography"
            ),
            "anime": (
                "anime style, Japanese animation, "
                "clean linework, cel shading, "
                "expressive eyes, stylized hair, "
                "vibrant colors, high quality illustration"
            ),
            "watercolor": (
                "watercolor painting style, "
                "soft edges, flowing colors, "
                "artistic, dreamy atmosphere, "
                "traditional media look"
            ),
            "pixel_art": (
                "pixel art style, retro game aesthetic, "
                "limited color palette, crisp pixels, "
                "16-bit style, nostalgic feel"
            ),
        }

        parts.append(style_prompts.get(self.style_type, style_prompts["disney_3d"]))

        # 조명
        lighting_prompts = {
            "natural": "natural daylight, soft shadows",
            "studio": "studio lighting, professional setup",
            "dramatic": "dramatic lighting, high contrast, shadows",
            "soft": "soft diffused lighting, gentle shadows",
            "harsh": "harsh direct lighting, strong shadows",
            "neon": "neon lights, cyberpunk atmosphere, colorful glow",
        }
        parts.append(lighting_prompts.get(self.lighting_type, ""))

        # 컬러 팔레트
        color_prompts = {
            "vibrant_warm": "vibrant warm colors, saturated reds oranges yellows",
            "muted_cool": "muted cool colors, desaturated blues greens",
            "pastel": "pastel colors, soft pinks blues lavenders",
            "dark_moody": "dark moody colors, deep shadows, low key",
        }
        parts.append(color_prompts.get(self.color_palette, ""))

        # 기본 프롬프트
        if self.base_prompt:
            parts.append(self.base_prompt)

        # 장면 설명
        if scene_description:
            parts.append(scene_description)

        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StylePresetAsset":
        """딕셔너리에서 생성"""
        return cls(**data)


class StylePresetManager:
    """
    스타일 프리셋 관리자

    프리셋 CRUD, 검색, 기본 프리셋 관리
    """

    def __init__(self, base_path: str = "data/assets/styles"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시
        self._cache: Dict[str, StylePresetAsset] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """지연 로드"""
        if not self._loaded:
            await self.load_all()
            self._loaded = True

    def _get_asset_path(self, preset_id: str) -> Path:
        """에셋 JSON 경로"""
        return self.base_path / f"{preset_id}.json"

    @staticmethod
    def generate_id(name: str) -> str:
        """이름 기반 ID 생성"""
        base = f"style_{name}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(base.encode()).hexdigest()[:12]

    # ============================================================
    # CRUD Operations
    # ============================================================

    async def save(self, preset: StylePresetAsset) -> StylePresetAsset:
        """프리셋 저장"""
        preset.update_timestamp()

        file_path = self._get_asset_path(preset.id)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(preset.to_dict(), ensure_ascii=False, indent=2))

        self._cache[preset.id] = preset

        logger.info(f"Style preset saved: {preset.name} ({preset.id})")
        return preset

    async def get(self, preset_id: str) -> Optional[StylePresetAsset]:
        """프리셋 조회"""
        if preset_id in self._cache:
            return self._cache[preset_id]

        file_path = self._get_asset_path(preset_id)
        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            preset = StylePresetAsset.from_dict(data)
            self._cache[preset_id] = preset
            return preset

    async def delete(self, preset_id: str) -> bool:
        """프리셋 삭제"""
        file_path = self._get_asset_path(preset_id)
        if not file_path.exists():
            return False

        file_path.unlink()

        if preset_id in self._cache:
            del self._cache[preset_id]

        logger.info(f"Style preset deleted: {preset_id}")
        return True

    async def load_all(self) -> List[StylePresetAsset]:
        """모든 프리셋 로드"""
        presets = []

        for file_path in self.base_path.glob("*.json"):
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    preset = StylePresetAsset.from_dict(data)
                    presets.append(preset)
                    self._cache[preset.id] = preset
            except Exception as e:
                logger.error(f"Failed to load preset {file_path}: {e}")

        logger.info(f"Loaded {len(presets)} style presets")
        return presets

    async def list_all(self) -> List[StylePresetAsset]:
        """모든 프리셋 목록"""
        await self._ensure_loaded()
        return list(self._cache.values())

    # ============================================================
    # Search Operations
    # ============================================================

    async def search(
        self,
        query: str = None,
        style_type: str = None,
        tags: List[str] = None,
        is_default: bool = None,
        limit: int = 50
    ) -> List[StylePresetAsset]:
        """프리셋 검색"""
        await self._ensure_loaded()

        results = list(self._cache.values())

        # 텍스트 검색
        if query:
            query_lower = query.lower()
            results = [
                p for p in results
                if query_lower in p.name.lower()
                or query_lower in p.description.lower()
            ]

        # 스타일 타입 필터
        if style_type:
            results = [p for p in results if p.style_type == style_type]

        # 기본 프리셋 필터
        if is_default is not None:
            results = [p for p in results if p.is_default == is_default]

        # 태그 필터
        if tags:
            results = [
                p for p in results
                if any(tag in p.tags for tag in tags)
            ]

        return results[:limit]

    async def get_by_type(self, style_type: str) -> List[StylePresetAsset]:
        """타입별 프리셋 목록"""
        await self._ensure_loaded()
        return [p for p in self._cache.values() if p.style_type == style_type]

    async def get_default(self) -> Optional[StylePresetAsset]:
        """기본 프리셋 조회"""
        await self._ensure_loaded()
        for preset in self._cache.values():
            if preset.is_default:
                return preset
        return None

    async def set_default(self, preset_id: str) -> bool:
        """기본 프리셋 설정"""
        preset = await self.get(preset_id)
        if not preset:
            return False

        # 기존 기본 프리셋 해제
        for p in self._cache.values():
            if p.is_default:
                p.is_default = False
                await self.save(p)

        # 새 기본 프리셋 설정
        preset.is_default = True
        await self.save(preset)

        return True

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        await self._ensure_loaded()

        presets = list(self._cache.values())

        return {
            "total": len(presets),
            "default_count": len([p for p in presets if p.is_default]),
            "total_usage": sum(p.usage_count for p in presets),
            "by_style_type": self._count_by_field(presets, "style_type"),
            "by_lighting": self._count_by_field(presets, "lighting_type"),
            "by_color_palette": self._count_by_field(presets, "color_palette"),
        }

    def _count_by_field(
        self,
        presets: List[StylePresetAsset],
        field: str
    ) -> Dict[str, int]:
        """필드별 카운트"""
        counts: Dict[str, int] = {}
        for preset in presets:
            value = getattr(preset, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts


# ============================================================
# 사전 정의된 스타일 프리셋
# ============================================================

DEFAULT_STYLE_PRESETS = [
    StylePresetAsset(
        id="default_disney_3d",
        name="Disney 3D Default",
        description="3D 애니메이션 기본 스타일 - Pixar 퀄리티",
        style_type="disney_3d",
        base_prompt="3D anime style, Pixar quality, smooth cel shading, beautiful lighting, clean renders, Disney animation quality",
        negative_prompt="realistic photo, live action, western cartoon, rough lines, low poly, ugly 3d, bad shading, plastic look, blurry, low quality",
        cfg_scale=7.5,
        steps=30,
        lighting_type="soft",
        color_palette="vibrant_warm",
        rendering_type="cel_shaded",
        is_default=True,
        tags=["3d", "disney", "animation", "default"]
    ),
    StylePresetAsset(
        id="default_disney_dramatic",
        name="Disney 3D Dramatic",
        description="드라마틱한 3D 애니메이션 - 시네마틱 조명",
        style_type="disney_3d",
        base_prompt="3D anime style, dramatic cinematic lighting, volumetric light, epic atmosphere, Pixar quality, smooth shading",
        negative_prompt="realistic photo, flat lighting, boring, low quality, rough",
        cfg_scale=8.0,
        steps=35,
        lighting_type="dramatic",
        color_palette="vibrant_warm",
        rendering_type="cinematic",
        tags=["3d", "disney", "dramatic", "cinematic"]
    ),
    StylePresetAsset(
        id="default_disney_soft",
        name="Disney 3D Soft",
        description="부드러운 3D 애니메이션 - 따뜻한 분위기",
        style_type="disney_3d",
        base_prompt="3D anime style, soft studio lighting, gentle shadows, warm colors, peaceful atmosphere, Pixar quality",
        negative_prompt="realistic photo, harsh lighting, dark, gritty, rough",
        cfg_scale=7.0,
        steps=30,
        lighting_type="soft",
        color_palette="pastel",
        rendering_type="cel_shaded",
        tags=["3d", "disney", "soft", "warm"]
    ),
    StylePresetAsset(
        id="default_anime",
        name="2D Anime Classic",
        description="클래식 2D 애니메이션 스타일",
        style_type="anime",
        base_prompt="anime style, 2D animation, hand drawn aesthetic, vibrant colors, detailed illustration, clean lines",
        negative_prompt="3D, realistic, photo, cgi, western style, rough lines",
        cfg_scale=7.5,
        steps=30,
        lighting_type="natural",
        color_palette="vibrant_warm",
        rendering_type="flat",
        tags=["2d", "anime", "classic", "japanese"]
    ),
    StylePresetAsset(
        id="default_realistic",
        name="Realistic Cinematic",
        description="실사 같은 시네마틱 스타일",
        style_type="realistic",
        base_prompt="photorealistic, cinematic lighting, film grain, real world textures, natural skin tones, detailed environment, 8K resolution, professional photography",
        negative_prompt="anime, cartoon, 3d, stylized, painting, drawing",
        cfg_scale=8.0,
        steps=40,
        lighting_type="dramatic",
        color_palette="muted_cool",
        rendering_type="photorealistic",
        tags=["realistic", "cinematic", "photo"]
    ),
    StylePresetAsset(
        id="default_fantasy",
        name="Fantasy Magical",
        description="판타지 마법 같은 분위기",
        style_type="disney_3d",
        base_prompt="3D anime style, magical atmosphere, glowing effects, ethereal lighting, fantasy world, Pixar quality, sparkles",
        negative_prompt="realistic photo, modern, mundane, boring, low quality",
        cfg_scale=7.5,
        steps=35,
        lighting_type="dramatic",
        color_palette="pastel",
        rendering_type="cel_shaded",
        tags=["fantasy", "magical", "ethereal"]
    ),
    StylePresetAsset(
        id="default_cyberpunk",
        name="Cyberpunk Neon",
        description="사이버펑크 네온 조명",
        style_type="realistic",
        base_prompt="3D anime style, neon lights, cyberpunk atmosphere, glowing effects, futuristic, Pixar quality, rain reflections",
        negative_prompt="realistic photo, daylight, natural, old fashioned, low quality",
        cfg_scale=8.0,
        steps=35,
        lighting_type="neon",
        color_palette="dark_moody",
        rendering_type="cinematic",
        tags=["cyberpunk", "neon", "futuristic"]
    ),
]


async def initialize_default_presets(manager: StylePresetManager) -> None:
    """기본 프리셋 초기화"""
    for preset in DEFAULT_STYLE_PRESETS:
        existing = await manager.get(preset.id)
        if not existing:
            await manager.save(preset)
            logger.info(f"Initialized default preset: {preset.name}")
