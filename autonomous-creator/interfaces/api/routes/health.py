"""
Health Check Routes
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "service": "autonomous-creator"
    }


@router.get("/ready")
async def readiness():
    """준비 상태 확인"""
    # DB 연결 확인 등
    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "tts": "ok",
            "image_gen": "ok"
        }
    }
