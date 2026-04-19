"""
Application Services Module
"""

# New v2 Pipeline (preferred)
from .end_to_end_pipeline import (
    EndToEndPipeline,
    PipelineConfig,
    PipelineResult,
    create_video
)

# Checkpoint
from .checkpoint_manager import (
    CheckpointManager,
    CheckpointState,
    PipelineStep
)

__all__ = [
    # New v2 (preferred)
    "EndToEndPipeline",
    "PipelineConfig",
    "PipelineResult",
    "create_video",
    # Checkpoint
    "CheckpointManager",
    "CheckpointState",
    "PipelineStep",
]


# Legacy imports (lazy loading to avoid dependency issues)
def __getattr__(name):
    """Lazy import for legacy components"""
    if name == "PipelineOrchestrator":
        from .orchestrator import PipelineOrchestrator
        return PipelineOrchestrator
    elif name == "StoryApplicationService":
        from .story_service import StoryApplicationService
        return StoryApplicationService
    elif name == "PresetApplicationService":
        from .preset_service import PresetApplicationService
        return PresetApplicationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
