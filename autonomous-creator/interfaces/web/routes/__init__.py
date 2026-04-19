"""
Web UI Routes
"""
from .pipeline import router as pipeline_router
from .stories import router as stories_router

__all__ = ["pipeline_router", "stories_router"]
