"""
Cache system for generated assets.

Provides content-addressed caching for images, videos, audio, and prompts
to avoid regenerating identical content.
"""

from .base_cache import BaseCache, CacheEntry, CacheStats
from .file_cache import FileCache
from .cache_key import CacheKeyGenerator, CacheKey
from .cache_manager import CacheManager, CacheType

__all__ = [
    "BaseCache",
    "CacheEntry",
    "CacheStats",
    "FileCache",
    "CacheKeyGenerator",
    "CacheKey",
    "CacheManager",
    "CacheType",
]
