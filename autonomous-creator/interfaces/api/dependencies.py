"""
FastAPI Dependencies

의존성 주입 컨테이너
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.database import get_database, get_session
from infrastructure.persistence.repositories.story_repo import StoryRepository
from infrastructure.persistence.repositories.preset_repo import PresetRepository
from infrastructure.persistence.repositories.task_repo import TaskRepository

from core.application.orchestrator import PipelineOrchestrator
from core.application.story_service import StoryApplicationService
from core.application.preset_service import PresetApplicationService


async def get_db():
    """데이터베이스 인스턴스"""
    return await get_database()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """DB 세션"""
    async for session in get_session():
        yield session


async def get_story_repo(session: AsyncSession = None) -> StoryRepository:
    """스토리 저장소"""
    if session is None:
        db = await get_database()
        async for s in db.get_session():
            return StoryRepository(s)
    return StoryRepository(session)


async def get_preset_repo(session: AsyncSession = None) -> PresetRepository:
    """프리셋 저장소"""
    if session is None:
        db = await get_database()
        async for s in db.get_session():
            return PresetRepository(s)
    return PresetRepository(session)


async def get_task_repo(session: AsyncSession = None) -> TaskRepository:
    """작업 저장소"""
    if session is None:
        db = await get_database()
        async for s in db.get_session():
            return TaskRepository(s)
    return TaskRepository(session)


async def get_story_service() -> StoryApplicationService:
    """스토리 서비스"""
    repo = await get_story_repo()
    return StoryApplicationService(repo)


async def get_preset_service() -> PresetApplicationService:
    """프리셋 서비스"""
    repo = await get_preset_repo()
    return PresetApplicationService(repo)


async def get_orchestrator() -> PipelineOrchestrator:
    """파이프라인 오케스트레이터"""
    story_repo = await get_story_repo()
    task_repo = await get_task_repo()
    return PipelineOrchestrator(story_repo, task_repo)
