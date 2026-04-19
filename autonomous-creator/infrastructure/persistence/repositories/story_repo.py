"""
Story Repository Implementation

SQLAlchemy 기반 스토리 저장소
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.story import Story, Language
from core.domain.interfaces.repository import IStoryRepository
from ..models.orm_models import StoryModel


class StoryRepository(IStoryRepository):
    """
    스토리 저장소 구현
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, story: Story) -> Story:
        """스토리 저장"""
        model = StoryModel.from_entity(story)

        # 기존 스토리 확인
        existing = await self.find_by_id(story.id)
        if existing:
            # 업데이트
            model.updated_at = story.updated_at
            await self.session.merge(model)
        else:
            # 새로 생성
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def find_by_id(self, id: str) -> Optional[Story]:
        """ID로 스토리 조회"""
        result = await self.session.execute(
            select(StoryModel).where(StoryModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Story]:
        """모든 스토리 조회"""
        result = await self.session.execute(
            select(StoryModel)
            .order_by(StoryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def find_by_language(self, language: str) -> List[Story]:
        """언어별 스토리 조회"""
        result = await self.session.execute(
            select(StoryModel)
            .where(StoryModel.language == language)
            .order_by(StoryModel.created_at.desc())
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def delete(self, id: str) -> bool:
        """스토리 삭제"""
        model = await self.session.execute(
            select(StoryModel).where(StoryModel.id == id)
        )
        model = model.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[Story]:
        """키워드 검색"""
        result = await self.session.execute(
            select(StoryModel)
            .where(
                StoryModel.title.contains(query) |
                StoryModel.content.contains(query)
            )
            .limit(limit)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]
