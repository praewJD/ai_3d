"""
Video Domain Entity

생성된 영상 관련 데이터 모델
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid


class VideoQuality(str, Enum):
    """영상 품질"""
    SD = "sd"       # 480p
    HD = "hd"       # 720p
    FHD = "fhd"     # 1080p (기본값)
    QHD = "qhd"     # 1440p
    UHD = "uhd"     # 2160p (4K)


class VideoSegment(BaseModel):
    """영상 세그먼트 (장면별)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    scene_id: str = Field(..., description="연결된 Scene ID")

    # 미디어 경로
    image_path: Optional[str] = Field(default=None, description="이미지 파일 경로")
    video_path: Optional[str] = Field(default=None, description="비디오 클립 경로 (SVD)")
    audio_path: Optional[str] = Field(default=None, description="오디오 파일 경로")

    # 영상 속성
    duration: float = Field(default=3.0, ge=0.5, le=60.0, description="지속 시간(초)")

    # 이펙트
    effects: List[str] = Field(default_factory=list, description="적용할 이펙트 목록")
    transition: Optional[str] = Field(default="fade", description="다음 장면 전환 효과")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "seg_001",
                "scene_id": "scene_001",
                "image_path": "outputs/images/scene_001.png",
                "video_path": "outputs/videos/scene_001_svd.mp4",
                "audio_path": "outputs/audio/scene_001.wav",
                "duration": 4.0,
                "effects": ["ken_burns_zoom", "color_enhance"],
                "transition": "fade"
            }
        }


class Video(BaseModel):
    """완성된 영상"""
    id: str = Field(default_factory=lambda: f"video_{uuid.uuid4().hex[:12]}")
    story_id: str = Field(..., description="연결된 Story ID")

    # 세그먼트
    segments: List[VideoSegment] = Field(default_factory=list, description="영상 세그먼트 목록")

    # 출력 정보
    output_path: Optional[str] = Field(default=None, description="최종 영상 파일 경로")
    thumbnail_path: Optional[str] = Field(default=None, description="썸네일 이미지 경로")

    # 영상 속성
    duration: float = Field(default=0.0, ge=0, description="총 재생 시간(초)")
    resolution: tuple[int, int] = Field(default=(1080, 1920), description="해상도 (width, height)")
    fps: int = Field(default=30, ge=24, le=60, description="프레임 레이트")
    quality: VideoQuality = Field(default=VideoQuality.FHD, description="영상 품질")

    # 메타데이터
    file_size: Optional[int] = Field(default=None, description="파일 크기 (bytes)")
    created_at: datetime = Field(default_factory=datetime.now, description="생성 일시")

    @property
    def aspect_ratio(self) -> str:
        """화면 비율 반환"""
        w, h = self.resolution
        return f"{w}:{h}"

    @property
    def is_vertical(self) -> bool:
        """세로 영상 여부 (쇼츠용)"""
        return self.resolution[0] < self.resolution[1]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "video_xyz789abc123",
                "story_id": "story_abc123def456",
                "segments": [],
                "output_path": "outputs/videos/final_20260329_100000.mp4",
                "duration": 30.0,
                "resolution": [1080, 1920],
                "fps": 30,
                "quality": "fhd",
                "created_at": "2026-03-29T10:05:00"
            }
        }
