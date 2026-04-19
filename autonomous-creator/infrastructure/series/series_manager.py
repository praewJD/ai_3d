"""
Series Manager - 시리즈 관리

시리즈 생성, 조회, 프롬프트 컨텍스트 제공
"""
import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import aiofiles

from core.domain.entities.series.series import (
    Series,
    SeriesStatus,
    SeriesGenre,
    SeriesTarget
)

logger = logging.getLogger(__name__)


class SeriesManager:
    """
    시리즈 관리자

    기능:
    - 시리즈 CRUD
    - 현재 작업 중인 시리즈 추적
    - 시리즈별 프롬프트 컨텍스트 제공
    """

    DEFAULT_DATA_PATH = "data/series"

    def __init__(self, data_path: str = None):
        self.data_path = Path(data_path or self.DEFAULT_DATA_PATH)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시
        self._series: Dict[str, Series] = {}
        self._current_series_id: Optional[str] = None
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """지연 로드"""
        if not self._loaded:
            await self.load_all()
            self._loaded = True

    # ============================================================
    # CRUD
    # ============================================================

    async def create_series(
        self,
        name: str,
        description: str = "",
        genres: List[SeriesGenre] = None,
        art_style: str = None,
        **kwargs
    ) -> Series:
        """새 시리즈 생성"""
        series = Series(
            name=name,
            description=description,
            genres=genres or [],
            **kwargs
        )

        # 기본 아트 스타일 설정
        if art_style:
            series.art_style = art_style

        await self.save(series)
        logger.info(f"Series created: {name} ({series.id})")
        return series

    async def save(self, series: Series) -> Series:
        """시리즈 저장"""
        await self._ensure_loaded()

        file_path = self.data_path / f"{series.id}.json"
        series.update_timestamp()

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(series.model_dump_json(indent=2))

        self._series[series.id] = series
        return series

    async def load(self, series_id: str) -> Optional[Series]:
        """시리즈 로드"""
        if series_id in self._series:
            return self._series[series_id]

        file_path = self.data_path / f"{series_id}.json"
        if file_path.exists():
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
                series = Series(**data)
                self._series[series_id] = series
                return series

        return None

    async def delete(self, series_id: str) -> bool:
        """시리즈 삭제"""
        file_path = self.data_path / f"{series_id}.json"
        if file_path.exists():
            file_path.unlink()
            if series_id in self._series:
                del self._series[series_id]
            if self._current_series_id == series_id:
                self._current_series_id = None
            return True
        return False

    async def load_all(self) -> List[Series]:
        """모든 시리즈 로드"""
        series_list = []

        for file_path in self.data_path.glob("*.json"):
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    series = Series(**data)
                    series_list.append(series)
                    self._series[series.id] = series
            except Exception as e:
                logger.error(f"Failed to load series {file_path}: {e}")

        return series_list

    # ============================================================
    # 현재 시리즈 관리
    # ============================================================

    async def set_current_series(self, series_id: str) -> bool:
        """현재 작업 중인 시리즈 설정"""
        series = await self.load(series_id)
        if series:
            self._current_series_id = series_id
            logger.info(f"Current series set to: {series.name}")
            return True
        return False

    async def get_current_series(self) -> Optional[Series]:
        """현재 시리즈 조회"""
        if self._current_series_id:
            return await self.load(self._current_series_id)
        return None

    @property
    def current_series_id(self) -> Optional[str]:
        """현재 시리즈 ID"""
        return self._current_series_id

    # ============================================================
    # 프롬프트 컨텍스트
    # ============================================================

    async def get_prompt_context(
        self,
        series_id: str = None
    ) -> Dict[str, Any]:
        """
        프롬프트용 시리즈 컨텍스트

        Args:
            series_id: 시리즈 ID (없으면 현재 시리즈)

        Returns:
            프롬프트 컨텍스트
        """
        target_id = series_id or self._current_series_id
        if not target_id:
            return self._get_default_context()

        series = await self.load(target_id)
        if series:
            return series.to_prompt_context()

        return self._get_default_context()

    def _get_default_context(self) -> Dict[str, Any]:
        """기본 컨텍스트 (시리즈 없을 때)"""
        return {
            "series_id": None,
            "series_name": "Default",
            "art_style": "Disney 3D animation style, Pixar quality",
            "style_prefix": "Disney 3D animation style, Pixar quality, smooth cel shading",
            "negative_prompt": "realistic photo, live action, western cartoon",
            "world_setting": "",
            "time_period": "fantasy"
        }

    async def build_scene_prompt(
        self,
        scene_description: str,
        character_ids: List[str] = None,
        location_key: str = None,
        series_id: str = None
    ) -> str:
        """
        시리즈 컨텍스트가 포함된 장면 프롬프트 생성

        Args:
            scene_description: 장면 설명
            character_ids: 캐릭터 ID 목록
            location_key: 장소 키
            series_id: 시리즈 ID

        Returns:
            완성된 프롬프트
        """
        context = await self.get_prompt_context(series_id)

        parts = [context["style_prefix"]]

        # 장소
        if location_key:
            series = await self.load(series_id or self._current_series_id)
            if series and location_key in series.locations:
                parts.append(series.locations[location_key])
            parts.append(context["world_setting"])

        # 캐릭터 (별도 로드 필요)
        if character_ids:
            from infrastructure.character import get_character_library
            library = get_character_library()
            for char_id in character_ids:
                char = await library.load(char_id)
                if char:
                    parts.append(char.get_full_prompt(include_disney_style=False))

        # 장면 설명
        parts.append(scene_description)

        return ", ".join(parts)

    # ============================================================
    # 조회
    # ============================================================

    async def list_series(
        self,
        status: SeriesStatus = None
    ) -> List[Series]:
        """시리즈 목록"""
        await self._ensure_loaded()

        series_list = list(self._series.values())

        if status:
            series_list = [s for s in series_list if s.status == status]

        return series_list

    async def search(self, query: str) -> List[Series]:
        """시리즈 검색"""
        await self._ensure_loaded()

        query_lower = query.lower()
        return [
            s for s in self._series.values()
            if query_lower in s.name.lower()
            or query_lower in s.description.lower()
        ]

    async def get_stats(self) -> Dict[str, Any]:
        """통계"""
        await self._ensure_loaded()

        series_list = list(self._series.values())

        return {
            "total_series": len(series_list),
            "by_status": {
                status.value: len([s for s in series_list if s.status == status])
                for status in SeriesStatus
            },
            "current_series_id": self._current_series_id
        }


# ============================================================
# 싱글톤
# ============================================================

_manager_instance: Optional[SeriesManager] = None


def get_series_manager() -> SeriesManager:
    """시리즈 매니저 싱글톤"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SeriesManager()
    return _manager_instance
