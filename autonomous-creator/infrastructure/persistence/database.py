"""
Database Configuration

SQLAlchemy 비동기 설정
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os

# 기본 DB 경로
DEFAULT_DB_PATH = "data/autonomous_creator.db"

# Base 클래스
Base = declarative_base()


class Database:
    """
    데이터베이스 연결 관리
    """

    def __init__(self, db_url: str | None = None):
        if db_url is None:
            # SQLite 기본값
            os.makedirs("data", exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"

        self.db_url = db_url
        self.engine = create_async_engine(
            db_url,
            echo=False,  # SQL 로깅 (개발 시 True)
            future=True
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """테이블 생성"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """테이블 삭제 (개발용)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """세션 제너레이터"""
        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        """연결 종료"""
        await self.engine.dispose()


# 전역 인스턴스
_db: Database | None = None


async def get_database() -> Database:
    """데이터베이스 인스턴스 반환"""
    global _db
    if _db is None:
        _db = Database()
        await _db.create_tables()
    return _db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성 주입용 세션 제너레이터"""
    db = await get_database()
    async for session in db.get_session():
        yield session
