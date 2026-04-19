"""
Story Domain Entity

스토리 및 관련 데이터 모델 정의
"""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from datetime import datetime
import uuid


class Language(str, Enum):
    """지원 언어"""
    KO = "ko"  # 한국어
    TH = "th"  # 태국어
    EN = "en"  # 영어
    JA = "ja"  # 일본어
    ZH = "zh"  # 중국어


class VideoMode(str, Enum):
    """영상 생성 모드"""
    AI_IMAGES = "ai_images"      # AI 이미지 시퀀스
    STOCK = "stock"              # 스톡 영상
    HYBRID = "hybrid"            # AI 이미지 + 스톡 영상
    SVD = "svd"                  # Stable Video Diffusion


class Scene(BaseModel):
    """개별 장면"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = Field(..., description="장면 설명")
    narration: str = Field(..., description="내레이션 텍스트")
    image_prompt: str = Field(..., description="이미지 생성 프롬프트")
    duration: float = Field(default=3.0, ge=1.0, le=30.0, description="장면 지속 시간(초)")
    order: int = Field(default=0, ge=0, description="장면 순서")

    # 비디오 관련
    use_svd: bool = Field(default=False, description="SVD로 비디오 생성 여부")
    motion_type: str = Field(default="medium", description="SVD 모션 타입")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "scene_001",
                "description": "숲속 입구 장면",
                "narration": "어둠이 내리앉는 숲속으로 한 소년이 걸어들어갑니다.",
                "image_prompt": "dark forest entrance, mysterious atmosphere, anime style",
                "duration": 4.0,
                "order": 0,
                "use_svd": True,
                "motion_type": "medium"
            }
        }


class Script(BaseModel):
    """완성된 스크립트 (장면 모음)"""
    scenes: List[Scene] = Field(default_factory=list, description="장면 목록")
    total_duration: float = Field(default=0.0, ge=0, description="총 재생 시간(초)")
    language: Language = Field(default=Language.KO, description="스크립트 언어")

    def calculate_total_duration(self) -> float:
        """총 재생 시간 계산"""
        self.total_duration = sum(scene.duration for scene in self.scenes)
        return self.total_duration

    class Config:
        json_schema_extra = {
            "example": {
                "scenes": [
                    {
                        "id": "scene_001",
                        "description": "오프닝",
                        "narration": "옛날 옛적에...",
                        "image_prompt": "fantasy kingdom, sunset",
                        "duration": 3.0,
                        "order": 0
                    }
                ],
                "total_duration": 30.0,
                "language": "ko"
            }
        }


class Story(BaseModel):
    """스토리 (최상위 엔티티)"""
    id: str = Field(default_factory=lambda: f"story_{uuid.uuid4().hex[:12]}")
    title: str = Field(..., min_length=1, max_length=200, description="스토리 제목")
    content: str = Field(..., min_length=10, description="스토리 내용")
    keywords: List[str] = Field(default_factory=list, description="키워드 목록")
    language: Language = Field(default=Language.KO, description="스토리 언어")
    video_mode: VideoMode = Field(default=VideoMode.AI_IMAGES, description="영상 생성 모드")

    # 생성된 스크립트
    script: Optional[Script] = Field(default=None, description="생성된 스크립트")

    # 스타일 프리셋
    style_preset_id: Optional[str] = Field(default=None, description="적용할 스타일 프리셋 ID")

    # 메타데이터
    created_at: datetime = Field(default_factory=datetime.now, description="생성 일시")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 일시")

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now()

    class Config:
        json_schema_extra = {
            "example": {
                "id": "story_abc123def456",
                "title": "마법의 숲의 비밀",
                "content": "어떤 소년이 마법의 숲에서 비밀을 발견하는 이야기입니다...",
                "keywords": ["모험", "마법", "성장"],
                "language": "ko",
                "video_mode": "ai_images",
                "style_preset_id": "cute-anime-v1",
                "created_at": "2026-03-29T10:00:00",
                "updated_at": "2026-03-29T10:00:00"
            }
        }
