"""
Location Asset - 장소 에셋 관리

장소 저장, 조회, 검색, 배경 이미지 관리
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
class LocationAsset:
    """
    장소 에셋 데이터 클래스

    장면의 배경/환경 정보를 관리
    """
    id: str
    name: str
    description: str

    # 이미지 경로
    reference_image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None

    # 장소 유형
    location_type: str = "interior"  # interior, exterior, fantasy, abstract

    # 시간대/날씨 설정
    time_of_day: str = "day"  # day, night, dawn, dusk, golden_hour
    weather: str = "clear"  # clear, cloudy, rainy, snowy, foggy

    # 조명 특성
    lighting_type: str = "natural"  # natural, studio, dramatic, soft, neon

    # 스타일 프롬프트
    style_prompt: str = ""  # 장소 스타일용 프롬프트
    negative_prompt: str = ""  # 제외할 요소

    # 색상 팔레트
    color_palette: List[str] = field(default_factory=list)
    # 예: ["warm", "vibrant", "blue_tones"]

    # 환경 특성
    environment_tags: List[str] = field(default_factory=list)
    # 예: ["urban", "modern", "cozy", "spacious"]

    # 메타데이터
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

    def to_prompt_segment(self) -> str:
        """프롬프트용 문자열 변환"""
        parts = [self.description]

        # 장소 유형
        if self.location_type == "exterior":
            parts.append("outdoor scene")
        elif self.location_type == "interior":
            parts.append("indoor scene")
        elif self.location_type == "fantasy":
            parts.append("fantasy environment")

        # 시간대
        time_prompts = {
            "day": "daytime, bright natural light",
            "night": "nighttime, moonlight",
            "dawn": "dawn, early morning light",
            "dusk": "dusk, evening light",
            "golden_hour": "golden hour, warm sunset light",
        }
        parts.append(time_prompts.get(self.time_of_day, ""))

        # 날씨
        weather_prompts = {
            "clear": "clear sky",
            "cloudy": "cloudy overcast",
            "rainy": "rain, wet surfaces",
            "snowy": "snow, winter atmosphere",
            "foggy": "foggy, misty atmosphere",
        }
        parts.append(weather_prompts.get(self.weather, ""))

        # 조명
        parts.append(f"{self.lighting_type} lighting")

        # 환경 태그
        if self.environment_tags:
            parts.append(', '.join(self.environment_tags))

        # 스타일 프롬프트
        if self.style_prompt:
            parts.append(self.style_prompt)

        return ', '.join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationAsset":
        """딕셔너리에서 생성"""
        return cls(**data)


class LocationAssetManager:
    """
    장소 에셋 관리자

    장소 CRUD, 검색, 이미지 관리
    """

    def __init__(self, base_path: str = "data/assets/locations"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시
        self._cache: Dict[str, LocationAsset] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """지연 로드"""
        if not self._loaded:
            await self.load_all()
            self._loaded = True

    def _get_asset_path(self, location_id: str) -> Path:
        """에셋 JSON 경로"""
        return self.base_path / f"{location_id}.json"

    def _get_image_dir(self, location_id: str) -> Path:
        """이미지 디렉토리 경로"""
        img_dir = self.base_path / location_id / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        return img_dir

    @staticmethod
    def generate_id(name: str) -> str:
        """이름 기반 ID 생성"""
        base = f"loc_{name}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(base.encode()).hexdigest()[:12]

    # ============================================================
    # CRUD Operations
    # ============================================================

    async def save(self, location: LocationAsset) -> LocationAsset:
        """장소 저장"""
        location.update_timestamp()

        file_path = self._get_asset_path(location.id)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(location.to_dict(), ensure_ascii=False, indent=2))

        self._cache[location.id] = location

        logger.info(f"Location saved: {location.name} ({location.id})")
        return location

    async def get(self, location_id: str) -> Optional[LocationAsset]:
        """장소 조회"""
        if location_id in self._cache:
            return self._cache[location_id]

        file_path = self._get_asset_path(location_id)
        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            location = LocationAsset.from_dict(data)
            self._cache[location_id] = location
            return location

    async def delete(self, location_id: str) -> bool:
        """장소 삭제"""
        file_path = self._get_asset_path(location_id)
        if not file_path.exists():
            return False

        file_path.unlink()

        # 이미지 디렉토리도 삭제
        img_dir = self.base_path / location_id
        if img_dir.exists():
            import shutil
            shutil.rmtree(img_dir)

        if location_id in self._cache:
            del self._cache[location_id]

        logger.info(f"Location deleted: {location_id}")
        return True

    async def load_all(self) -> List[LocationAsset]:
        """모든 장소 로드"""
        locations = []

        for file_path in self.base_path.glob("*.json"):
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    location = LocationAsset.from_dict(data)
                    locations.append(location)
                    self._cache[location.id] = location
            except Exception as e:
                logger.error(f"Failed to load location {file_path}: {e}")

        logger.info(f"Loaded {len(locations)} locations")
        return locations

    async def list_all(self) -> List[LocationAsset]:
        """모든 장소 목록"""
        await self._ensure_loaded()
        return list(self._cache.values())

    # ============================================================
    # Search Operations
    # ============================================================

    async def search(
        self,
        query: str = None,
        location_type: str = None,
        time_of_day: str = None,
        tags: List[str] = None,
        limit: int = 50
    ) -> List[LocationAsset]:
        """장소 검색"""
        await self._ensure_loaded()

        results = list(self._cache.values())

        # 텍스트 검색
        if query:
            query_lower = query.lower()
            results = [
                loc for loc in results
                if query_lower in loc.name.lower()
                or query_lower in loc.description.lower()
            ]

        # 타입 필터
        if location_type:
            results = [loc for loc in results if loc.location_type == location_type]

        # 시간대 필터
        if time_of_day:
            results = [loc for loc in results if loc.time_of_day == time_of_day]

        # 태그 필터
        if tags:
            results = [
                loc for loc in results
                if any(tag in loc.tags for tag in tags)
            ]

        return results[:limit]

    async def get_by_type(self, location_type: str) -> List[LocationAsset]:
        """타입별 장소 목록"""
        await self._ensure_loaded()
        return [loc for loc in self._cache.values() if loc.location_type == location_type]

    async def get_by_time(self, time_of_day: str) -> List[LocationAsset]:
        """시간대별 장소 목록"""
        await self._ensure_loaded()
        return [loc for loc in self._cache.values() if loc.time_of_day == time_of_day]

    # ============================================================
    # Reference Image Management
    # ============================================================

    async def set_reference_image(
        self,
        location_id: str,
        image_path: str
    ) -> bool:
        """참조 이미지 설정"""
        location = await self.get(location_id)
        if not location:
            return False

        img_dir = self._get_image_dir(location_id)
        src_path = Path(image_path)

        if not src_path.exists():
            logger.error(f"Image not found: {image_path}")
            return False

        import shutil
        dest_path = img_dir / f"reference{src_path.suffix}"
        shutil.copy2(src_path, dest_path)

        location.reference_image_path = str(dest_path)
        await self.save(location)

        return True

    async def get_reference_image(
        self,
        location_id: str
    ) -> Optional[str]:
        """참조 이미지 경로 조회"""
        location = await self.get(location_id)
        if location and location.reference_image_path:
            if Path(location.reference_image_path).exists():
                return location.reference_image_path
        return None

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        await self._ensure_loaded()

        locs = list(self._cache.values())

        return {
            "total": len(locs),
            "with_reference_images": len([
                loc for loc in locs if loc.reference_image_path
            ]),
            "total_usage": sum(loc.usage_count for loc in locs),
            "by_type": self._count_by_field(locs, "location_type"),
            "by_time": self._count_by_field(locs, "time_of_day"),
            "by_weather": self._count_by_field(locs, "weather"),
        }

    def _count_by_field(
        self,
        locations: List[LocationAsset],
        field: str
    ) -> Dict[str, int]:
        """필드별 카운트"""
        counts: Dict[str, int] = {}
        for loc in locations:
            value = getattr(loc, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts


# ============================================================
# 사전 정의된 장소 템플릿
# ============================================================

LOCATION_TEMPLATES = {
    "modern_apartment": LocationAsset(
        id="template_modern_apartment",
        name="Modern Apartment",
        description="A stylish modern apartment with large windows and minimalist furniture",
        location_type="interior",
        time_of_day="day",
        weather="clear",
        lighting_type="natural",
        style_prompt="modern interior design, clean lines, minimalist furniture, large windows",
        environment_tags=["urban", "modern", "cozy"],
        tags=["interior", "home", "modern"]
    ),
    "coffee_shop": LocationAsset(
        id="template_coffee_shop",
        name="Cozy Coffee Shop",
        description="A warm and inviting coffee shop with wooden furniture and soft lighting",
        location_type="interior",
        time_of_day="day",
        weather="clear",
        lighting_type="soft",
        style_prompt="cozy cafe interior, wooden tables, warm atmosphere, soft ambient lighting",
        environment_tags=["urban", "cozy", "casual"],
        tags=["interior", "cafe", "social"]
    ),
    "city_street_night": LocationAsset(
        id="template_city_street_night",
        name="City Street at Night",
        description="A bustling city street illuminated by neon lights and street lamps",
        location_type="exterior",
        time_of_day="night",
        weather="clear",
        lighting_type="neon",
        style_prompt="city street at night, neon lights, urban atmosphere, wet pavement reflections",
        environment_tags=["urban", "nightlife", "modern"],
        tags=["exterior", "urban", "night"]
    ),
    "forest_path": LocationAsset(
        id="template_forest_path",
        name="Forest Path",
        description="A peaceful path winding through a lush green forest",
        location_type="exterior",
        time_of_day="day",
        weather="clear",
        lighting_type="natural",
        style_prompt="forest path, sunlight filtering through trees, nature, peaceful",
        environment_tags=["nature", "peaceful", "outdoor"],
        tags=["exterior", "nature", "forest"]
    ),
    "fantasy_castle": LocationAsset(
        id="template_fantasy_castle",
        name="Fantasy Castle",
        description="A magnificent fantasy castle with tall towers and magical atmosphere",
        location_type="fantasy",
        time_of_day="dusk",
        weather="clear",
        lighting_type="dramatic",
        style_prompt="fantasy castle, magical atmosphere, tall towers, dramatic sky",
        environment_tags=["fantasy", "magical", "grand"],
        tags=["fantasy", "castle", "medieval"]
    ),
}
