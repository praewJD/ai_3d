"""
Task Domain Entity

영상 생성 작업 상태 관리
"""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    """작업 상태"""
    PENDING = "pending"           # 대기 중
    QUEUED = "queued"             # 큐에 등록됨
    PROCESSING = "processing"     # 처리 중
    COMPLETED = "completed"       # 완료
    FAILED = "failed"             # 실패
    CANCELLED = "cancelled"       # 취소됨


class TaskStep(str, Enum):
    """작업 단계"""
    INIT = "초기화"
    SCRIPT_GENERATION = "스크립트 생성 중"
    AUDIO_GENERATION = "음성 생성 중"
    IMAGE_GENERATION = "이미지 생성 중"
    VIDEO_GENERATION = "비디오 생성 중"
    COMPOSITION = "영상 합성 중"
    FINALIZING = "마무리 중"
    COMPLETED = "완료"


class GenerationTask(BaseModel):
    """
    영상 생성 작업

    전체 파이프라인 실행 상태 추적
    """
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    story_id: str = Field(..., description="연결된 Story ID")

    # 상태
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="작업 상태")
    progress: int = Field(default=0, ge=0, le=100, description="진행률 (0-100)")
    current_step: TaskStep = Field(default=TaskStep.INIT, description="현재 단계")

    # 에러 정보
    error_message: Optional[str] = Field(default=None, description="에러 메시지")
    error_stack: Optional[str] = Field(default=None, description="에러 스택 트레이스")

    # 생성된 리소스 경로
    output_paths: List[str] = Field(
        default_factory=list,
        description="생성된 파일 경로 목록"
    )

    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.now, description="생성 일시")
    started_at: Optional[datetime] = Field(default=None, description="시작 일시")
    completed_at: Optional[datetime] = Field(default=None, description="완료 일시")

    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self.status == TaskStatus.PROCESSING

    @property
    def is_finished(self) -> bool:
        """완료 여부 (성공/실패/취소)"""
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED
        ]

    @property
    def duration_seconds(self) -> Optional[float]:
        """실행 시간 (초)"""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def start(self) -> None:
        """작업 시작"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now()
        self.current_step = TaskStep.SCRIPT_GENERATION

    def complete(self) -> None:
        """작업 완료"""
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.current_step = TaskStep.COMPLETED
        self.completed_at = datetime.now()

    def fail(self, error: str, stack: Optional[str] = None) -> None:
        """작업 실패"""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.error_stack = stack
        self.completed_at = datetime.now()

    def update_progress(self, progress: int, step: Optional[TaskStep] = None) -> None:
        """진행 상태 업데이트"""
        self.progress = min(100, max(0, progress))
        if step:
            self.current_step = step

    class Config:
        json_schema_extra = {
            "example": {
                "id": "task_xyz789abc123",
                "story_id": "story_abc123def456",
                "status": "processing",
                "progress": 60,
                "current_step": "이미지 생성 중",
                "error_message": None,
                "output_paths": [
                    "outputs/audio/scene_001.wav",
                    "outputs/images/scene_001.png"
                ],
                "created_at": "2026-03-29T10:00:00",
                "started_at": "2026-03-29T10:00:05",
                "completed_at": None
            }
        }
