"""
Task Repository Implementation

SQLAlchemy 기반 작업 저장소
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.task import GenerationTask, TaskStatus
from core.domain.interfaces.repository import ITaskRepository
from ..models.orm_models import TaskModel


class TaskRepository(ITaskRepository):
    """
    작업 저장소 구현
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, task: GenerationTask) -> GenerationTask:
        """작업 저장"""
        model = TaskModel.from_entity(task)

        existing = await self.find_by_id(task.id)
        if existing:
            await self.session.merge(model)
        else:
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def find_by_id(self, id: str) -> Optional[GenerationTask]:
        """ID로 작업 조회"""
        result = await self.session.execute(
            select(TaskModel).where(TaskModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def find_by_story_id(self, story_id: str) -> Optional[GenerationTask]:
        """스토리 ID로 작업 조회"""
        result = await self.session.execute(
            select(TaskModel)
            .where(TaskModel.story_id == story_id)
            .order_by(TaskModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def find_pending(self) -> List[GenerationTask]:
        """대기 중인 작업 목록"""
        result = await self.session.execute(
            select(TaskModel)
            .where(TaskModel.status == TaskStatus.PENDING.value)
            .order_by(TaskModel.created_at)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def find_running(self) -> List[GenerationTask]:
        """실행 중인 작업 목록"""
        result = await self.session.execute(
            select(TaskModel)
            .where(TaskModel.status == TaskStatus.PROCESSING.value)
            .order_by(TaskModel.started_at)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def find_recent(self, limit: int = 50) -> List[GenerationTask]:
        """최근 작업 목록"""
        result = await self.session.execute(
            select(TaskModel)
            .order_by(TaskModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def delete(self, id: str) -> bool:
        """작업 삭제"""
        model = await self.session.execute(
            select(TaskModel).where(TaskModel.id == id)
        )
        model = model.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def cleanup_old_tasks(
        self,
        days: int = 30
    ) -> int:
        """
        오래된 완료된 작업 정리

        Args:
            days: 보관 기간 (일)

        Returns:
            삭제된 작업 수
        """
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)

        # 완료된 작업 중 cutoff 이전 것들 삭제
        result = await self.session.execute(
            select(TaskModel)
            .where(
                TaskModel.status.in_([
                    TaskStatus.COMPLETED.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.CANCELLED.value
                ]),
                TaskModel.completed_at < cutoff
            )
        )
        models = result.scalars().all()

        count = 0
        for model in models:
            await self.session.delete(model)
            count += 1

        await self.session.commit()
        return count
