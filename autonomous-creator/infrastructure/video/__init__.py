"""
Video Infrastructure Module
"""
from .video_factory import create_video_generator, get_video_generator_info, should_use_lipsync

# Optional imports (may fail if dependencies not installed)
try:
    from .svd_generator import SVDGenerator
except ImportError:
    SVDGenerator = None

try:
    from .moviepy_composer import MoviePyComposer
except ImportError:
    MoviePyComposer = None

try:
    from .hybrid_manager import HybridVideoManager
except ImportError:
    HybridVideoManager = None

__all__ = [
    "create_video_generator",
    "get_video_generator_info",
    "should_use_lipsync",
    "SVDGenerator",
    "MoviePyComposer",
    "HybridVideoManager",
]
