"""
Asset Library - 메인 에셋 라이브러리

캐릭터, 장소, 스타일 프리셋 통합 관리
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from datetime import datetime

from .character_asset import CharacterAsset, CharacterAssetManager
from .location_asset import LocationAsset, LocationAssetManager
from .style_preset import StylePresetAsset, StylePresetManager, initialize_default_presets
from .thumbnail_generator import ThumbnailGenerator, get_thumbnail_generator


logger = logging.getLogger(__name__)


class AssetLibrary:
    """
    통합 에셋 라이브러리

    캐릭터, 장소, 스타일 프리셋을 하나의 인터페이스로 관리
    """

    def __init__(
        self,
        base_path: str = "data/assets",
        auto_generate_thumbnails: bool = True
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 하위 매니저 초기화
        self.characters = CharacterAssetManager(
            base_path=str(self.base_path / "characters")
        )
        self.locations = LocationAssetManager(
            base_path=str(self.base_path / "locations")
        )
        self.styles = StylePresetManager(
            base_path=str(self.base_path / "styles")
        )

        # 썸네일 생성기
        self.thumbnail_generator = get_thumbnail_generator()
        self.auto_generate_thumbnails = auto_generate_thumbnails

        self._initialized = False

    async def initialize(self, load_defaults: bool = True) -> None:
        """
        라이브러리 초기화

        Args:
            load_defaults: 기본 프리셋 로드 여부
        """
        if self._initialized:
            return

        # 모든 에셋 로드
        await asyncio.gather(
            self.characters.load_all(),
            self.locations.load_all(),
            self.styles.load_all()
        )

        # 기본 프리셋 초기화
        if load_defaults:
            await initialize_default_presets(self.styles)

        self._initialized = True
        logger.info("Asset library initialized")

    # ============================================================
    # Character Operations
    # ============================================================

    async def save_character(
        self,
        name: str,
        description: str,
        reference_image: str = None,
        appearance: Dict[str, Any] = None,
        personality: List[str] = None,
        powers: List[str] = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> CharacterAsset:
        """
        캐릭터 저장

        Args:
            name: 캐릭터 이름
            description: 캐릭터 설명
            reference_image: 참조 이미지 경로
            appearance: 외형 정보
            personality: 성격 특성
            powers: 능력
            tags: 태그
            metadata: 추가 메타데이터

        Returns:
            저장된 CharacterAsset
        """
        # ID 생성
        character_id = CharacterAssetManager.generate_id(name)

        # 캐릭터 생성
        character = CharacterAsset(
            id=character_id,
            name=name,
            description=description,
            appearance=appearance or {},
            personality=personality or [],
            powers=powers or [],
            tags=tags or [],
            metadata=metadata or {}
        )

        # 참조 이미지 처리
        if reference_image:
            await self.characters.set_reference_image(character_id, reference_image)

            # 썸네일 자동 생성
            if self.auto_generate_thumbnails:
                thumbnail_path = await self.thumbnail_generator.generate_for_character(
                    reference_image, character_id
                )
                if thumbnail_path:
                    character.thumbnail_path = thumbnail_path

        # 저장
        return await self.characters.save(character)

    async def get_character(self, character_id: str) -> Optional[CharacterAsset]:
        """캐릭터 조회"""
        character = await self.characters.get(character_id)
        if character:
            character.increment_usage()
            await self.characters.save(character)
        return character

    async def list_characters(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[CharacterAsset]:
        """캐릭터 목록"""
        all_characters = await self.characters.list_all()
        return all_characters[offset:offset + limit]

    async def search_characters(
        self,
        query: str = None,
        tags: List[str] = None,
        gender: str = None,
        age: str = None,
        limit: int = 50
    ) -> List[CharacterAsset]:
        """캐릭터 검색"""
        return await self.characters.search(
            query=query,
            tags=tags,
            gender=gender,
            age=age,
            limit=limit
        )

    async def delete_character(self, character_id: str) -> bool:
        """캐릭터 삭제"""
        # 썸네일도 삭제
        await self.thumbnail_generator.delete_thumbnail(character_id, "char")
        return await self.characters.delete(character_id)

    # ============================================================
    # Location Operations
    # ============================================================

    async def save_location(
        self,
        name: str,
        description: str,
        reference_image: str = None,
        location_type: str = "interior",
        time_of_day: str = "day",
        weather: str = "clear",
        lighting_type: str = "natural",
        style_prompt: str = "",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> LocationAsset:
        """
        장소 저장

        Args:
            name: 장소 이름
            description: 장소 설명
            reference_image: 참조 이미지 경로
            location_type: 장소 유형
            time_of_day: 시간대
            weather: 날씨
            lighting_type: 조명 유형
            style_prompt: 스타일 프롬프트
            tags: 태그
            metadata: 추가 메타데이터

        Returns:
            저장된 LocationAsset
        """
        # ID 생성
        location_id = LocationAssetManager.generate_id(name)

        # 장소 생성
        location = LocationAsset(
            id=location_id,
            name=name,
            description=description,
            location_type=location_type,
            time_of_day=time_of_day,
            weather=weather,
            lighting_type=lighting_type,
            style_prompt=style_prompt,
            tags=tags or [],
            metadata=metadata or {}
        )

        # 참조 이미지 처리
        if reference_image:
            await self.locations.set_reference_image(location_id, reference_image)

            # 썸네일 자동 생성
            if self.auto_generate_thumbnails:
                thumbnail_path = await self.thumbnail_generator.generate_for_location(
                    reference_image, location_id
                )
                if thumbnail_path:
                    location.thumbnail_path = thumbnail_path

        # 저장
        return await self.locations.save(location)

    async def get_location(self, location_id: str) -> Optional[LocationAsset]:
        """장소 조회"""
        location = await self.locations.get(location_id)
        if location:
            location.increment_usage()
            await self.locations.save(location)
        return location

    async def list_locations(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[LocationAsset]:
        """장소 목록"""
        all_locations = await self.locations.list_all()
        return all_locations[offset:offset + limit]

    async def search_locations(
        self,
        query: str = None,
        location_type: str = None,
        time_of_day: str = None,
        tags: List[str] = None,
        limit: int = 50
    ) -> List[LocationAsset]:
        """장소 검색"""
        return await self.locations.search(
            query=query,
            location_type=location_type,
            time_of_day=time_of_day,
            tags=tags,
            limit=limit
        )

    async def delete_location(self, location_id: str) -> bool:
        """장소 삭제"""
        await self.thumbnail_generator.delete_thumbnail(location_id, "loc")
        return await self.locations.delete(location_id)

    # ============================================================
    # Style Preset Operations
    # ============================================================

    async def save_style_preset(
        self,
        name: str,
        description: str,
        style_type: str = "disney_3d",
        base_prompt: str = "",
        negative_prompt: str = "",
        cfg_scale: float = 7.5,
        steps: int = 30,
        lighting_type: str = "soft",
        color_palette: str = "vibrant_warm",
        rendering_type: str = "cel_shaded",
        tags: List[str] = None,
        is_default: bool = False,
        metadata: Dict[str, Any] = None
    ) -> StylePresetAsset:
        """
        스타일 프리셋 저장

        Args:
            name: 프리셋 이름
            description: 프리셋 설명
            style_type: 스타일 타입
            base_prompt: 기본 프롬프트
            negative_prompt: 네거티브 프롬프트
            cfg_scale: CFG Scale
            steps: Inference Steps
            lighting_type: 조명 유형
            color_palette: 컬러 팔레트
            rendering_type: 렌더링 타입
            tags: 태그
            is_default: 기본 프리셋 여부
            metadata: 추가 메타데이터

        Returns:
            저장된 StylePresetAsset
        """
        # ID 생성
        preset_id = StylePresetManager.generate_id(name)

        # 기본 프리셋이면 다른 프리셋의 기본 설정 해제
        if is_default:
            current_default = await self.styles.get_default()
            if current_default:
                current_default.is_default = False
                await self.styles.save(current_default)

        # 프리셋 생성
        preset = StylePresetAsset(
            id=preset_id,
            name=name,
            description=description,
            style_type=style_type,
            base_prompt=base_prompt,
            negative_prompt=negative_prompt,
            cfg_scale=cfg_scale,
            steps=steps,
            lighting_type=lighting_type,
            color_palette=color_palette,
            rendering_type=rendering_type,
            tags=tags or [],
            is_default=is_default,
            metadata=metadata or {}
        )

        # 저장
        return await self.styles.save(preset)

    async def get_style_preset(self, preset_id: str) -> Optional[StylePresetAsset]:
        """스타일 프리셋 조회"""
        preset = await self.styles.get(preset_id)
        if preset:
            preset.increment_usage()
            await self.styles.save(preset)
        return preset

    async def get_default_style_preset(self) -> Optional[StylePresetAsset]:
        """기본 스타일 프리셋 조회"""
        return await self.styles.get_default()

    async def list_style_presets(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[StylePresetAsset]:
        """스타일 프리셋 목록"""
        all_presets = await self.styles.list_all()
        return all_presets[offset:offset + limit]

    async def search_style_presets(
        self,
        query: str = None,
        style_type: str = None,
        tags: List[str] = None,
        is_default: bool = None,
        limit: int = 50
    ) -> List[StylePresetAsset]:
        """스타일 프리셋 검색"""
        return await self.styles.search(
            query=query,
            style_type=style_type,
            tags=tags,
            is_default=is_default,
            limit=limit
        )

    async def delete_style_preset(self, preset_id: str) -> bool:
        """스타일 프리셋 삭제"""
        return await self.styles.delete(preset_id)

    # ============================================================
    # Batch Operations
    # ============================================================

    async def get_multiple_characters(
        self,
        character_ids: List[str]
    ) -> Dict[str, CharacterAsset]:
        """여러 캐릭터 일괄 조회"""
        results = {}
        for char_id in character_ids:
            char = await self.get_character(char_id)
            if char:
                results[char_id] = char
        return results

    async def get_multiple_locations(
        self,
        location_ids: List[str]
    ) -> Dict[str, LocationAsset]:
        """여러 장소 일괄 조회"""
        results = {}
        for loc_id in location_ids:
            loc = await self.get_location(loc_id)
            if loc:
                results[loc_id] = loc
        return results

    # ============================================================
    # Statistics & Export
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """라이브러리 통계"""
        char_stats = await self.characters.get_stats()
        loc_stats = await self.locations.get_stats()
        style_stats = await self.styles.get_stats()

        return {
            "characters": char_stats,
            "locations": loc_stats,
            "styles": style_stats,
            "total_assets": (
                char_stats.get("total", 0) +
                loc_stats.get("total", 0) +
                style_stats.get("total", 0)
            )
        }

    async def export_all(self) -> Dict[str, Any]:
        """모든 에셋 내보내기"""
        return {
            "characters": [c.to_dict() for c in await self.characters.list_all()],
            "locations": [l.to_dict() for l in await self.locations.list_all()],
            "styles": [s.to_dict() for s in await self.styles.list_all()],
            "exported_at": datetime.now().isoformat()
        }

    # ============================================================
    # Integration with Scene Graph
    # ============================================================

    async def get_character_identity_prompt(
        self,
        character_id: str
    ) -> Optional[str]:
        """
        SceneGraph CharacterIdentity 호환 프롬프트 생성

        Args:
            character_id: 캐릭터 ID

        Returns:
            일관성 유지용 프롬프트
        """
        character = await self.get_character(character_id)
        if not character:
            return None

        parts = [
            f"character named {character.name}",
            "same face, same appearance",
            "consistent character design"
        ]

        prompt_segment = character.to_prompt_segment()
        if prompt_segment:
            parts.append(prompt_segment)

        return ", ".join(parts)

    async def get_location_prompt(
        self,
        location_id: str
    ) -> Optional[str]:
        """
        장소 프롬프트 생성

        Args:
            location_id: 장소 ID

        Returns:
            장소 설명 프롬프트
        """
        location = await self.get_location(location_id)
        if not location:
            return None

        return location.to_prompt_segment()

    async def get_style_full_prompt(
        self,
        preset_id: str,
        scene_description: str = ""
    ) -> Optional[str]:
        """
        스타일 프리셋 전체 프롬프트 생성

        Args:
            preset_id: 프리셋 ID
            scene_description: 장면 설명

        Returns:
            전체 프롬프트
        """
        preset = await self.get_style_preset(preset_id)
        if not preset:
            return None

        return preset.to_full_prompt(scene_description)


# ============================================================
# Singleton
# ============================================================

_library_instance: Optional[AssetLibrary] = None


def get_asset_library() -> AssetLibrary:
    """에셋 라이브러리 싱글톤"""
    global _library_instance
    if _library_instance is None:
        _library_instance = AssetLibrary()
    return _library_instance


async def initialize_asset_library(load_defaults: bool = True) -> AssetLibrary:
    """에셋 라이브러리 초기화 및 반환"""
    library = get_asset_library()
    await library.initialize(load_defaults=load_defaults)
    return library
