"""
FastAPI Web Application

웹 UI 메인 앱
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config.settings import get_settings
from interfaces.api.dependencies import get_db
from .routes import pipeline_router, stories_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    settings = get_settings()
    db = await get_db()
    print(f"Web UI started - {settings.app_name} v{settings.app_version}")

    yield

    await db.close()
    print("Web UI shutdown")


app = FastAPI(
    title="Autonomous Creator Web UI",
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

# 정적 파일 서빙
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# API 라우터 등록
app.include_router(stories_router, prefix="/api/stories", tags=["Stories"])
app.include_router(pipeline_router, prefix="/api/pipeline", tags=["Pipeline"])


@app.get("/")
async def root():
    """메인 페이지 서빙"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Web UI", "static_dir": str(STATIC_DIR)}


@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy"}


def run(host: str = "0.0.0.0", port: int = 8080, reload: bool = True):
    """개발 서버 실행"""
    uvicorn.run(
        "interfaces.web.app:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    run()
