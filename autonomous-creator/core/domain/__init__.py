"""
Domain Layer - Business Logic & Entities
"""
from .entities import (
    Story,
    Scene,
    Script,
    Video,
    VideoSegment,
    StylePreset,
    VoiceSettings,
    GenerationTask,
    TaskStatus,
    Language,
    VideoMode,
    VoiceGender,
)
from .interfaces import (
    ITTSEngine,
    IImageGenerator,
    IAIProvider,
    IVideoComposer,
    IStoryRepository,
    IPresetRepository,
    ITaskRepository,
)
from .usecases import (
    CreateStoryUseCase,
    GenerateVideoUseCase,
    ManagePresetUseCase,
    RecommendUseCase,
)

__all__ = [
    # Entities
    "Story",
    "Scene",
    "Script",
    "Video",
    "VideoSegment",
    "StylePreset",
    "VoiceSettings",
    "GenerationTask",
    "TaskStatus",
    "Language",
    "VideoMode",
    "VoiceGender",
    # Interfaces
    "ITTSEngine",
    "IImageGenerator",
    "IAIProvider",
    "IVideoComposer",
    "IStoryRepository",
    "IPresetRepository",
    "ITaskRepository",
    # Use Cases
    "CreateStoryUseCase",
    "GenerateVideoUseCase",
    "ManagePresetUseCase",
    "RecommendUseCase",
]
