"""
Central cache manager for coordinating multiple cache instances.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Generic
import threading
from collections import OrderedDict

from .base_cache import BaseCache, CacheEntry, CacheStats


class CacheType(Enum):
    """Types of cached content."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PROMPT = "prompt"


@dataclass
class CacheConfig:
    """Configuration for a cache instance."""
    cache_type: CacheType
    enabled: bool = True
    ttl_seconds: Optional[int] = None
    max_size_bytes: Optional[int] = None
    directory: Optional[str] = None


@dataclass
class ManagerStats:
    """Aggregated statistics for all caches."""
    total_hits: int = 0
    total_misses: int = 0
    total_evictions: int = 0
    total_size_bytes: int = 0
    total_entries: int = 0
    cache_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        """Calculate overall hit rate."""
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return (self.total_hits / total) * 100


class MemoryCache(BaseCache[Any]):
    """
    In-memory cache implementation for fast access to small items.

    Uses LRU (Least Recently Used) eviction when max_entries is reached.
    Thread-safe with fine-grained locking for better concurrency.
    """

    def __init__(
        self,
        name: str = "memory_cache",
        default_ttl_seconds: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        max_entries: Optional[int] = 1000,
    ):
        """
        Initialize the memory cache.

        Args:
            name: Human-readable name for this cache
            default_ttl_seconds: Default TTL for entries
            max_size_bytes: Maximum total size in bytes
            max_entries: Maximum number of entries (LRU eviction)
        """
        super().__init__(name, default_ttl_seconds, max_size_bytes)
        self._max_entries = max_entries
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._entry_locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        with self._lock:
            entry = self._entries.get(key)

            if entry is None:
                self._stats.record_miss()
                return None

            if entry.is_expired:
                self._remove_entry(key)
                self._stats.record_miss()
                return None

            # Move to end for LRU
            self._entries.move_to_end(key)
            entry.touch()
            self._stats.record_hit()

            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store a value in the cache."""
        with self._lock:
            # Calculate size
            size_bytes = self._estimate_size(value)

            # Check capacity
            if self._max_entries and len(self._entries) >= self._max_entries:
                self._evict_lru()

            if self._max_size_bytes:
                self._ensure_size(size_bytes)

            # Create entry
            now = datetime.utcnow()
            expires_at = self._calculate_ttl_expiry(ttl_seconds)

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                access_count=0,
                last_accessed=now,
                size_bytes=size_bytes,
                metadata=metadata or {},
            )

            # Remove old entry if exists
            if key in self._entries:
                old_entry = self._entries[key]
                self._stats.update_size(-old_entry.size_bytes)
                self._stats.entry_count -= 1

            # Add new entry
            self._entries[key] = entry
            self._entries.move_to_end(key)

            # Update stats
            self._stats.update_size(size_bytes)
            self._stats.entry_count += 1

            return True

    def delete(self, key: str) -> bool:
        """Remove an entry from the cache."""
        with self._lock:
            if key not in self._entries:
                return False

            self._remove_entry(key)
            self._stats.record_eviction()
            return True

    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._remove_entry(key)
                return False
            return True

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get the full cache entry including metadata."""
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.is_expired:
                self._remove_entry(key)
                return None
            return entry

    def keys(self) -> List[str]:
        """Get all cache keys."""
        with self._lock:
            return list(self._entries.keys())

    def clear(self) -> int:
        """Clear all entries from the cache."""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._stats.total_size_bytes = 0
            self._stats.entry_count = 0
            return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._entries.items()
                if entry.is_expired
            ]

            for key in expired_keys:
                self._remove_entry(key)

            self._stats.record_cleanup(len(expired_keys))
            return len(expired_keys)

    def _remove_entry(self, key: str) -> None:
        """Remove entry and update stats (assumes lock held)."""
        if key in self._entries:
            entry = self._entries.pop(key)
            self._stats.update_size(-entry.size_bytes)
            self._stats.entry_count -= 1

    def _evict_lru(self) -> None:
        """Evict least recently used entry (assumes lock held)."""
        if self._entries:
            oldest_key = next(iter(self._entries))
            self._remove_entry(oldest_key)
            self._stats.record_eviction()

    def _ensure_size(self, required_bytes: int) -> None:
        """Ensure enough size by evicting entries (assumes lock held)."""
        while (
            self._max_size_bytes is not None
            and self._stats.total_size_bytes + required_bytes > self._max_size_bytes
            and self._entries
        ):
            self._evict_lru()

    def _estimate_size(self, value: Any) -> int:
        """Estimate the size of a value in bytes."""
        if value is None:
            return 0
        elif isinstance(value, bytes):
            return len(value)
        elif isinstance(value, str):
            return len(value.encode('utf-8'))
        elif isinstance(value, (int, float)):
            return 8
        elif isinstance(value, (list, tuple, dict, set)):
            # Rough estimate for containers
            try:
                import sys
                return sys.getsizeof(value)
            except Exception:
                return 100
        else:
            return 100  # Default estimate


class CacheManager:
    """
    Central manager for coordinating multiple cache instances.

    Manages file-based and memory caches for different content types,
    providing a unified interface for cache operations.
    """

    # Default configurations for each cache type
    DEFAULT_CONFIGS = {
        CacheType.IMAGE: CacheConfig(
            cache_type=CacheType.IMAGE,
            ttl_seconds=3600 * 24 * 7,  # 7 days
            max_size_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
        ),
        CacheType.VIDEO: CacheConfig(
            cache_type=CacheType.VIDEO,
            ttl_seconds=3600 * 24 * 7,  # 7 days
            max_size_bytes=50 * 1024 * 1024 * 1024,  # 50 GB
        ),
        CacheType.AUDIO: CacheConfig(
            cache_type=CacheType.AUDIO,
            ttl_seconds=3600 * 24 * 30,  # 30 days
            max_size_bytes=5 * 1024 * 1024 * 1024,  # 5 GB
        ),
        CacheType.PROMPT: CacheConfig(
            cache_type=CacheType.PROMPT,
            ttl_seconds=3600 * 24 * 30,  # 30 days
            max_size_bytes=100 * 1024 * 1024,  # 100 MB
        ),
    }

    def __init__(
        self,
        base_cache_dir: str,
        configs: Optional[Dict[CacheType, CacheConfig]] = None,
        enable_memory_cache: bool = True,
        memory_cache_max_entries: int = 1000,
    ):
        """
        Initialize the cache manager.

        Args:
            base_cache_dir: Base directory for file caches
            configs: Custom configurations per cache type
            enable_memory_cache: Whether to use memory cache layer
            memory_cache_max_entries: Max entries in memory cache
        """
        self._base_dir = Path(base_cache_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

        self._configs = {**self.DEFAULT_CONFIGS, **(configs or {})}
        self._enable_memory_cache = enable_memory_cache

        self._file_caches: Dict[CacheType, Any] = {}  # FileCache instances
        self._memory_caches: Dict[CacheType, MemoryCache] = {}
        self._lock = threading.RLock()

        # Initialize caches
        self._initialize_caches(memory_cache_max_entries)

    def _initialize_caches(self, max_entries: int) -> None:
        """Initialize all cache instances."""
        from .file_cache import FileCache

        for cache_type in CacheType:
            config = self._configs[cache_type]

            if not config.enabled:
                continue

            # Create directory for this cache type
            cache_dir = config.directory or str(
                self._base_dir / cache_type.value
            )

            # Initialize file cache
            self._file_caches[cache_type] = FileCache(
                cache_dir=cache_dir,
                name=f"{cache_type.value}_file_cache",
                default_ttl_seconds=config.ttl_seconds,
                max_size_bytes=config.max_size_bytes,
            )

            # Initialize memory cache if enabled
            if self._enable_memory_cache:
                self._memory_caches[cache_type] = MemoryCache(
                    name=f"{cache_type.value}_memory_cache",
                    default_ttl_seconds=config.ttl_seconds,
                    max_entries=max_entries,
                )

    def get(
        self,
        cache_type: CacheType,
        key: str,
    ) -> Optional[Any]:
        """
        Get a value from cache (checks memory first, then file).

        Args:
            cache_type: Type of cache to query
            key: Cache key

        Returns:
            Cached value or None
        """
        with self._lock:
            # Check memory cache first
            if self._enable_memory_cache and cache_type in self._memory_caches:
                value = self._memory_caches[cache_type].get(key)
                if value is not None:
                    return value

            # Check file cache
            if cache_type in self._file_caches:
                value = self._file_caches[cache_type].get(key)
                if value is not None and self._enable_memory_cache:
                    # Promote to memory cache
                    self._memory_caches[cache_type].set(key, value)
                return value

            return None

    def set(
        self,
        cache_type: CacheType,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        memory_only: bool = False,
    ) -> bool:
        """
        Store a value in cache.

        Args:
            cache_type: Type of cache to use
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL override
            metadata: Optional metadata
            memory_only: If True, only store in memory cache

        Returns:
            True if stored successfully
        """
        with self._lock:
            success = True

            # Store in memory cache
            if self._enable_memory_cache and cache_type in self._memory_caches:
                if not self._memory_caches[cache_type].set(
                    key, value, ttl_seconds, metadata
                ):
                    success = False

            # Store in file cache
            if not memory_only and cache_type in self._file_caches:
                if not self._file_caches[cache_type].set(
                    key, value, ttl_seconds, metadata
                ):
                    success = False

            return success

    def delete(
        self,
        cache_type: CacheType,
        key: str,
    ) -> bool:
        """Delete an entry from all cache layers."""
        with self._lock:
            success = True

            if self._enable_memory_cache and cache_type in self._memory_caches:
                if not self._memory_caches[cache_type].delete(key):
                    success = False

            if cache_type in self._file_caches:
                if not self._file_caches[cache_type].delete(key):
                    success = False

            return success

    def exists(
        self,
        cache_type: CacheType,
        key: str,
    ) -> bool:
        """Check if a key exists in any cache layer."""
        with self._lock:
            if self._enable_memory_cache and cache_type in self._memory_caches:
                if self._memory_caches[cache_type].exists(key):
                    return True

            if cache_type in self._file_caches:
                return self._file_caches[cache_type].exists(key)

            return False

    def get_entry(
        self,
        cache_type: CacheType,
        key: str,
    ) -> Optional[CacheEntry]:
        """Get full cache entry with metadata."""
        with self._lock:
            # Prefer memory cache entry (more recent)
            if self._enable_memory_cache and cache_type in self._memory_caches:
                entry = self._memory_caches[cache_type].get_entry(key)
                if entry is not None:
                    return entry

            if cache_type in self._file_caches:
                return self._file_caches[cache_type].get_entry(key)

            return None

    def get_file_path(
        self,
        cache_type: CacheType,
        key: str,
    ) -> Optional[Path]:
        """Get file path for cached content (file cache only)."""
        if cache_type in self._file_caches:
            return self._file_caches[cache_type].get_file_path(key)
        return None

    def clear(
        self,
        cache_type: Optional[CacheType] = None,
    ) -> int:
        """
        Clear cache entries.

        Args:
            cache_type: Specific cache to clear, or None for all

        Returns:
            Total entries removed
        """
        with self._lock:
            total = 0

            cache_types = [cache_type] if cache_type else list(CacheType)

            for ct in cache_types:
                if self._enable_memory_cache and ct in self._memory_caches:
                    total += self._memory_caches[ct].clear()

                if ct in self._file_caches:
                    total += self._file_caches[ct].clear()

            return total

    def cleanup_expired(
        self,
        cache_type: Optional[CacheType] = None,
    ) -> int:
        """
        Clean up expired entries.

        Args:
            cache_type: Specific cache to clean, or None for all

        Returns:
            Total entries removed
        """
        with self._lock:
            total = 0

            cache_types = [cache_type] if cache_type else list(CacheType)

            for ct in cache_types:
                if self._enable_memory_cache and ct in self._memory_caches:
                    total += self._memory_caches[ct].cleanup_expired()

                if ct in self._file_caches:
                    total += self._file_caches[ct].cleanup_expired()

            return total

    def get_stats(self) -> ManagerStats:
        """Get aggregated statistics for all caches."""
        stats = ManagerStats()

        for cache_type in CacheType:
            cache_name = cache_type.value
            stats.cache_stats[cache_name] = {}

            # Memory cache stats
            if self._enable_memory_cache and cache_type in self._memory_caches:
                mem_stats = self._memory_caches[cache_type].get_stats()
                stats.cache_stats[cache_name]["memory"] = mem_stats
                stats.total_hits += self._memory_caches[cache_type].stats.hits
                stats.total_misses += self._memory_caches[cache_type].stats.misses
                stats.total_evictions += self._memory_caches[cache_type].stats.evictions
                stats.total_size_bytes += self._memory_caches[cache_type].stats.total_size_bytes
                stats.total_entries += self._memory_caches[cache_type].stats.entry_count

            # File cache stats
            if cache_type in self._file_caches:
                file_stats = self._file_caches[cache_type].get_stats()
                stats.cache_stats[cache_name]["file"] = file_stats
                # Only count file cache entries (avoid double counting hits)
                stats.total_size_bytes += self._file_caches[cache_type].stats.total_size_bytes
                stats.total_entries += self._file_caches[cache_type].stats.entry_count

        return stats

    def get_config(self, cache_type: CacheType) -> CacheConfig:
        """Get configuration for a cache type."""
        return self._configs.get(cache_type)

    def update_config(
        self,
        cache_type: CacheType,
        config: CacheConfig,
    ) -> None:
        """Update configuration for a cache type (requires reinitialization)."""
        self._configs[cache_type] = config

    def get_cache(
        self,
        cache_type: CacheType,
        layer: str = "file",
    ) -> Optional[BaseCache]:
        """
        Get the underlying cache instance.

        Args:
            cache_type: Type of cache
            layer: "file" or "memory"

        Returns:
            Cache instance or None
        """
        if layer == "memory":
            return self._memory_caches.get(cache_type)
        return self._file_caches.get(cache_type)

    def keys(
        self,
        cache_type: CacheType,
        layer: str = "all",
    ) -> List[str]:
        """
        Get all keys for a cache type.

        Args:
            cache_type: Type of cache
            layer: "file", "memory", or "all"

        Returns:
            List of keys
        """
        keys_set = set()

        if layer in ("all", "memory") and cache_type in self._memory_caches:
            keys_set.update(self._memory_caches[cache_type].keys())

        if layer in ("all", "file") and cache_type in self._file_caches:
            keys_set.update(self._file_caches[cache_type].keys())

        return list(keys_set)

    def start_cleanup_scheduler(
        self,
        interval_seconds: int = 3600,
    ) -> None:
        """
        Start periodic cleanup of expired entries.

        Args:
            interval_seconds: Cleanup interval in seconds
        """
        def cleanup_task():
            while True:
                import time
                time.sleep(interval_seconds)
                self.cleanup_expired()

        cleanup_thread = threading.Thread(
            target=cleanup_task,
            daemon=True,
            name="cache-cleanup",
        )
        cleanup_thread.start()

    def warm_cache(
        self,
        cache_type: CacheType,
        entries: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """
        Warm the cache with precomputed entries.

        Args:
            cache_type: Type of cache
            entries: Dictionary of key -> value pairs
            ttl_seconds: TTL for entries

        Returns:
            Number of entries added
        """
        count = 0
        for key, value in entries.items():
            if self.set(cache_type, key, value, ttl_seconds):
                count += 1
        return count
