"""
FastAPI Application Entry Point

autonomous-creator REST API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from config.settings import get_settings
from .routes import stories, presets, tasks, health
from .dependencies import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시
    settings = get_settings()
    db = await get_db()
    print(f"🚀 {settings.app_name} v{settings.app_version} started")

    yield

    # 종료 시
    await db.close()
    print("👋 Application shutdown")


app = FastAPI(
    title="Autonomous Creator API",
    description="AI-powered multi-language short video generation",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health.router, tags=["Health"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["Stories"])
app.include_router(presets.router, prefix="/api/v1/presets", tags=["Presets"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "name": "Autonomous Creator API",
        "version": "0.1.0",
        "docs": "/docs"
    }


def run():
    """개발 서버 실행"""
    uvicorn.run(
        "interfaces.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    run()
