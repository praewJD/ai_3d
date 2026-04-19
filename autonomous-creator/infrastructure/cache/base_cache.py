"""
Abstract cache interface defining the contract for cache implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar
import threading


class CacheStatus(Enum):
    """Status of a cache entry."""
    VALID = "valid"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get the age of this entry in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def touch(self) -> None:
        """Update access time and count."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Statistics for cache operations."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    expired_cleanups: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def record_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.misses += 1

    def record_eviction(self) -> None:
        """Record a cache eviction."""
        with self._lock:
            self.evictions += 1

    def record_cleanup(self, count: int = 1) -> None:
        """Record expired entry cleanup."""
        with self._lock:
            self.expired_cleanups += count

    def update_size(self, delta: int) -> None:
        """Update total cache size."""
        with self._lock:
            self.total_size_bytes += delta

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_percent": round(self.hit_rate, 2),
                "evictions": self.evictions,
                "total_size_bytes": self.total_size_bytes,
                "entry_count": self.entry_count,
                "expired_cleanups": self.expired_cleanups,
            }


T = TypeVar("T")


class BaseCache(ABC, Generic[T]):
    """
    Abstract base class for cache implementations.

    Defines the interface that all cache implementations must follow,
    supporting content-addressed storage with TTL and thread-safe operations.
    """

    def __init__(
        self,
        name: str,
        default_ttl_seconds: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
    ):
        """
        Initialize the cache.

        Args:
            name: Human-readable name for this cache
            default_ttl_seconds: Default time-to-live for entries (None = no expiry)
            max_size_bytes: Maximum cache size in bytes (None = unlimited)
        """
        self._name = name
        self._default_ttl_seconds = default_ttl_seconds
        self._max_size_bytes = max_size_bytes
        self._stats = CacheStats()
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        """Get the cache name."""
        return self._name

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """
        Retrieve a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: T,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl_seconds: Time-to-live override (uses default if None)
            metadata: Optional metadata to store with the entry

        Returns:
            True if stored successfully
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Remove an entry from the cache.

        Args:
            key: The cache key

        Returns:
            True if the entry was removed
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: The cache key

        Returns:
            True if the key exists and is not expired
        """
        pass

    @abstractmethod
    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """
        Get the full cache entry including metadata.

        Args:
            key: The cache key

        Returns:
            The cache entry or None if not found
        """
        pass

    @abstractmethod
    def keys(self) -> list[str]:
        """
        Get all cache keys.

        Returns:
            List of all keys in the cache
        """
        pass

    @abstractmethod
    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries removed
        """
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries removed
        """
        pass

    def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Get a value from cache, or compute and store it if not present.

        Args:
            key: The cache key
            factory: Function to create the value if not cached
            ttl_seconds: Time-to-live for new entries
            metadata: Optional metadata for new entries

        Returns:
            The cached or newly created value
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl_seconds, metadata)
        return value

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics as a dictionary.

        Returns:
            Dictionary with cache stats
        """
        stats_dict = self._stats.to_dict()
        stats_dict["cache_name"] = self._name
        stats_dict["default_ttl_seconds"] = self._default_ttl_seconds
        stats_dict["max_size_bytes"] = self._max_size_bytes
        return stats_dict

    def _calculate_ttl_expiry(
        self, ttl_seconds: Optional[int]
    ) -> Optional[datetime]:
        """Calculate expiry time based on TTL."""
        effective_ttl = ttl_seconds or self._default_ttl_seconds
        if effective_ttl is None:
            return None
        return datetime.utcnow() + timedelta(seconds=effective_ttl)


# Import timedelta at module level for _calculate_ttl_expiry
from datetime import timedelta
