"""
SQLAlchemy ORM Models

데이터베이스 테이블 매핑
"""
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    JSON,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
import json

# Base는 database.py에서 import
from ..database import Base


class StoryModel(Base):
    """
    스토리 테이블
    """
    __tablename__ = "stories"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(JSON, default=list)  # List[str]
    language = Column(String(10), default="ko")
    video_mode = Column(String(20), default="ai_images")

    # 스크립트 (JSON)
    script = Column(JSON, nullable=True)

    # 스타일 프리셋
    style_preset_id = Column(String(50), ForeignKey("presets.id"), nullable=True)

    # 메타데이터
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계
    preset = relationship("PresetModel", back_populates="stories")
    tasks = relationship("TaskModel", back_populates="story", cascade="all, delete-orphan")

    def to_entity(self) -> "Story":
        """엔티티로 변환"""
        from core.domain.entities.story import Story, Script, Scene, Language, VideoMode

        script_entity = None
        if self.script:
            scenes = [
                Scene(**s) for s in self.script.get("scenes", [])
            ]
            script_entity = Script(
                scenes=scenes,
                total_duration=self.script.get("total_duration", 0),
                language=Language(self.script.get("language", "ko"))
            )

        return Story(
            id=self.id,
            title=self.title,
            content=self.content,
            keywords=self.keywords or [],
            language=Language(self.language),
            video_mode=VideoMode(self.video_mode),
            script=script_entity,
            style_preset_id=self.style_preset_id,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_entity(cls, story: "Story") -> "StoryModel":
        """엔티티에서 생성"""
        script_data = None
        if story.script:
            script_data = {
                "scenes": [s.model_dump() for s in story.script.scenes],
                "total_duration": story.script.total_duration,
                "language": story.script.language.value
            }

        return cls(
            id=story.id,
            title=story.title,
            content=story.content,
            keywords=story.keywords,
            language=story.language.value,
            video_mode=story.video_mode.value,
            script=script_data,
            style_preset_id=story.style_preset_id,
            created_at=story.created_at,
            updated_at=story.updated_at
        )


class PresetModel(Base):
    """
    스타일 프리셋 테이블
    """
    __tablename__ = "presets"

    id = Column(String(50), primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, default="")

    # 프롬프트
    base_prompt = Column(Text, default="")
    negative_prompt = Column(Text, default="ugly, blurry, low quality")

    # SD 파라미터
    seed = Column(Integer, default=-1)
    cfg_scale = Column(Float, default=7.5)
    steps = Column(Integer, default=30)
    sampler = Column(String(50), default="dpmpp_2m")

    # IP-Adapter
    ip_adapter_ref = Column(String(500), nullable=True)
    ip_adapter_scale = Column(Float, default=0.8)

    # LoRA
    lora_weights = Column(String(500), nullable=True)
    lora_scale = Column(Float, default=1.0)

    # 추가 설정
    extra_params = Column(JSON, default=dict)

    # 메타데이터
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계
    stories = relationship("StoryModel", back_populates="preset")

    def to_entity(self) -> "StylePreset":
        """엔티티로 변환"""
        from core.domain.entities.preset import StylePreset

        return StylePreset(
            id=self.id,
            name=self.name,
            description=self.description,
            base_prompt=self.base_prompt,
            negative_prompt=self.negative_prompt,
            seed=self.seed,
            cfg_scale=self.cfg_scale,
            steps=self.steps,
            sampler=self.sampler,
            ip_adapter_ref=self.ip_adapter_ref,
            ip_adapter_scale=self.ip_adapter_scale,
            lora_weights=self.lora_weights,
            lora_scale=self.lora_scale,
            extra_params=self.extra_params or {},
            is_default=self.is_default,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_entity(cls, preset: "StylePreset") -> "PresetModel":
        """엔티티에서 생성"""
        return cls(
            id=preset.id,
            name=preset.name,
            description=preset.description,
            base_prompt=preset.base_prompt,
            negative_prompt=preset.negative_prompt,
            seed=preset.seed,
            cfg_scale=preset.cfg_scale,
            steps=preset.steps,
            sampler=preset.sampler,
            ip_adapter_ref=preset.ip_adapter_ref,
            ip_adapter_scale=preset.ip_adapter_scale,
            lora_weights=preset.lora_weights,
            lora_scale=preset.lora_scale,
            extra_params=preset.extra_params,
            is_default=preset.is_default,
            created_at=preset.created_at,
            updated_at=preset.updated_at
        )


class TaskModel(Base):
    """
    작업 테이블
    """
    __tablename__ = "tasks"

    id = Column(String(50), primary_key=True)
    story_id = Column(String(50), ForeignKey("stories.id"), nullable=False)

    # 상태
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    current_step = Column(String(50), default="초기화")

    # 에러
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)

    # 출력
    output_paths = Column(JSON, default=list)

    # 시간
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 관계
    story = relationship("StoryModel", back_populates="tasks")

    def to_entity(self) -> "GenerationTask":
        """엔티티로 변환"""
        from core.domain.entities.task import GenerationTask, TaskStatus

        return GenerationTask(
            id=self.id,
            story_id=self.story_id,
            status=TaskStatus(self.status),
            progress=self.progress,
            current_step=self.current_step,
            error_message=self.error_message,
            error_stack=self.error_stack,
            output_paths=self.output_paths or [],
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at
        )

    @classmethod
    def from_entity(cls, task: "GenerationTask") -> "TaskModel":
        """엔티티에서 생성"""
        return cls(
            id=task.id,
            story_id=task.story_id,
            status=task.status.value,
            progress=task.progress,
            current_step=task.current_step.value,
            error_message=task.error_message,
            error_stack=task.error_stack,
            output_paths=task.output_paths,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at
        )
