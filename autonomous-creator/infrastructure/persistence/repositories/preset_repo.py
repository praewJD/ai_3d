"""
Preset Repository Implementation

SQLAlchemy 기반 프리셋 저장소
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.preset import StylePreset
from core.domain.interfaces.repository import IPresetRepository
from ..models.orm_models import PresetModel


class PresetRepository(IPresetRepository):
    """
    스타일 프리셋 저장소 구현
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, preset: StylePreset) -> StylePreset:
        """프리셋 저장"""
        model = PresetModel.from_entity(preset)

        existing = await self.find_by_id(preset.id)
        if existing:
            await self.session.merge(model)
        else:
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def find_by_id(self, id: str) -> Optional[StylePreset]:
        """ID로 프리셋 조회"""
        result = await self.session.execute(
            select(PresetModel).where(PresetModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def find_by_name(self, name: str) -> Optional[StylePreset]:
        """이름으로 프리셋 조회"""
        result = await self.session.execute(
            select(PresetModel).where(PresetModel.name == name)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def find_all(self) -> List[StylePreset]:
        """모든 프리셋 조회"""
        result = await self.session.execute(
            select(PresetModel).order_by(PresetModel.created_at.desc())
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def find_defaults(self) -> List[StylePreset]:
        """기본 프리셋 목록 조회"""
        result = await self.session.execute(
            select(PresetModel)
            .where(PresetModel.is_default == True)
            .order_by(PresetModel.name)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def delete(self, id: str) -> bool:
        """프리셋 삭제"""
        model = await self.session.execute(
            select(PresetModel).where(PresetModel.id == id)
        )
        model = model.scalar_one_or_none()

        if model:
            # 기본 프리셋은 삭제 불가
            if model.is_default:
                return False

            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def initialize_defaults(self) -> int:
        """
        기본 프리셋 초기화

        Returns:
            생성된 프리셋 수
        """
        from core.domain.entities.preset import DEFAULT_PRESETS

        created_count = 0
        for preset in DEFAULT_PRESETS:
            existing = await self.find_by_name(preset.name)
            if not existing:
                preset.is_default = True
                await self.save(preset)
                created_count += 1

        return created_count
