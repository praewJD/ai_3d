"""
Domain Interfaces

추상화된 인터페이스 정의 (의존성 역전 원칙)
"""
from .tts_engine import ITTSEngine
from .image_generator import IImageGenerator
from .ai_provider import IAIProvider
from .video_composer import IVideoComposer
from .repository import IStoryRepository, IPresetRepository, ITaskRepository

__all__ = [
    "ITTSEngine",
    "IImageGenerator",
    "IAIProvider",
    "IVideoComposer",
    "IStoryRepository",
    "IPresetRepository",
    "ITaskRepository",
]
