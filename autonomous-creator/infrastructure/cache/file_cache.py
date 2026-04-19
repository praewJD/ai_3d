"""
File-based cache implementation with content-addressed storage.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import hashlib
import shutil

from .base_cache import BaseCache, CacheEntry, CacheStats


class FileCache(BaseCache[Union[bytes, str, Dict[str, Any]]]):
    """
    File-based cache implementation.

    Stores cached content as files with metadata in a sidecar JSON file.
    Supports binary and text content with content-addressed storage.
    """

    # File extensions for different content types
    META_EXTENSION = ".meta.json"
    DATA_EXTENSION = ".data"

    def __init__(
        self,
        cache_dir: str,
        name: str = "file_cache",
        default_ttl_seconds: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        create_dirs: bool = True,
    ):
        """
        Initialize the file cache.

        Args:
            cache_dir: Directory to store cache files
            name: Human-readable name for this cache
            default_ttl_seconds: Default TTL for entries
            max_size_bytes: Maximum total cache size
            create_dirs: Whether to create cache directories
        """
        super().__init__(name, default_ttl_seconds, max_size_bytes)

        self._cache_dir = Path(cache_dir)

        if create_dirs:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Index file for fast lookups
        self._index_file = self._cache_dir / "cache_index.json"
        self._index_lock = threading.RLock()
        self._index: Dict[str, Dict[str, Any]] = {}

        # Load existing index
        self._load_index()

    @property
    def cache_dir(self) -> Path:
        """Get the cache directory path."""
        return self._cache_dir

    def get(self, key: str) -> Optional[Union[bytes, str, Dict[str, Any]]]:
        """
        Retrieve a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found/expired
        """
        with self._lock:
            entry = self.get_entry(key)

            if entry is None:
                self._stats.record_miss()
                return None

            if entry.is_expired:
                self.delete(key)
                self._stats.record_miss()
                return None

            # Load the actual data
            data = self._load_data(key, entry.metadata.get("content_type"))

            if data is not None:
                entry.touch()
                self._save_entry(entry)
                self._stats.record_hit()

            return data

    def set(
        self,
        key: str,
        value: Union[bytes, str, Dict[str, Any]],
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store a value in the cache.

        Args:
            key: The cache key
            value: The value to cache (bytes, string, or dict)
            ttl_seconds: Time-to-live override
            metadata: Optional metadata

        Returns:
            True if stored successfully
        """
        with self._lock:
            try:
                # Determine content type and size
                content_type, size_bytes, serialized = self._serialize_value(value)

                # Check if we need to evict entries
                if self._max_size_bytes:
                    self._ensure_space(size_bytes)

                # Create cache entry
                now = datetime.utcnow()
                expires_at = self._calculate_ttl_expiry(ttl_seconds)

                entry = CacheEntry(
                    key=key,
                    value=None,  # Data stored separately
                    created_at=now,
                    expires_at=expires_at,
                    access_count=0,
                    last_accessed=now,
                    size_bytes=size_bytes,
                    metadata={
                        **(metadata or {}),
                        "content_type": content_type,
                    },
                )

                # Save data and metadata
                self._save_data(key, serialized, content_type)
                self._save_entry(entry)
                self._update_index(key, entry)

                # Update stats
                self._stats.update_size(size_bytes)
                self._stats.entry_count += 1

                return True

            except Exception as e:
                print(f"Error setting cache entry: {e}")
                return False

    def delete(self, key: str) -> bool:
        """
        Remove an entry from the cache.

        Args:
            key: The cache key

        Returns:
            True if the entry was removed
        """
        with self._lock:
            entry = self.get_entry(key)
            if entry is None:
                return False

            # Remove files
            data_path = self._get_data_path(key)
            meta_path = self._get_meta_path(key)

            try:
                if data_path.exists():
                    data_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()

                # Update index
                self._remove_from_index(key)

                # Update stats
                self._stats.update_size(-entry.size_bytes)
                self._stats.entry_count -= 1
                self._stats.record_eviction()

                return True

            except Exception as e:
                print(f"Error deleting cache entry: {e}")
                return False

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: The cache key

        Returns:
            True if the key exists and is not expired
        """
        entry = self.get_entry(key)
        if entry is None:
            return False
        return not entry.is_expired

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """
        Get the full cache entry including metadata.

        Args:
            key: The cache key

        Returns:
            The cache entry or None if not found
        """
        meta_path = self._get_meta_path(key)

        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return CacheEntry(
                key=data["key"],
                value=None,
                created_at=datetime.fromisoformat(data["created_at"]),
                expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
                access_count=data.get("access_count", 0),
                last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
                size_bytes=data.get("size_bytes", 0),
                metadata=data.get("metadata", {}),
            )

        except Exception as e:
            print(f"Error loading cache entry: {e}")
            return None

    def keys(self) -> List[str]:
        """
        Get all cache keys.

        Returns:
            List of all keys in the cache
        """
        with self._index_lock:
            return list(self._index.keys())

    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            count = 0

            for key in list(self._index.keys()):
                if self.delete(key):
                    count += 1

            # Clear index
            self._index.clear()
            self._save_index()

            # Reset stats
            self._stats.total_size_bytes = 0
            self._stats.entry_count = 0

            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            count = 0
            expired_keys = []

            for key in list(self._index.keys()):
                entry = self.get_entry(key)
                if entry and entry.is_expired:
                    expired_keys.append(key)

            for key in expired_keys:
                if self.delete(key):
                    count += 1

            self._stats.record_cleanup(count)
            return count

    def get_file_path(self, key: str) -> Optional[Path]:
        """
        Get the file path for a cached item.

        Args:
            key: The cache key

        Returns:
            Path to the cached file or None if not found
        """
        if not self.exists(key):
            return None
        return self._get_data_path(key)

    def store_file(
        self,
        key: str,
        source_path: str,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store a file in the cache by copying it.

        Args:
            key: The cache key
            source_path: Path to the source file
            ttl_seconds: Time-to-live
            metadata: Optional metadata

        Returns:
            True if stored successfully
        """
        source = Path(source_path)
        if not source.exists():
            return False

        with open(source, "rb") as f:
            data = f.read()

        file_metadata = {
            **(metadata or {}),
            "original_filename": source.name,
        }

        return self.set(key, data, ttl_seconds, file_metadata)

    def _get_data_path(self, key: str) -> Path:
        """Get the path for cached data file."""
        safe_key = self._safe_key(key)
        return self._cache_dir / f"{safe_key}{self.DATA_EXTENSION}"

    def _get_meta_path(self, key: str) -> Path:
        """Get the path for metadata file."""
        safe_key = self._safe_key(key)
        return self._cache_dir / f"{safe_key}{self.META_EXTENSION}"

    def _safe_key(self, key: str) -> str:
        """Convert key to a safe filename."""
        # Use hash of key for safe filename
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _serialize_value(
        self, value: Union[bytes, str, Dict[str, Any]]
    ) -> tuple[str, int, Union[bytes, str]]:
        """
        Serialize value and determine content type and size.

        Returns:
            Tuple of (content_type, size_bytes, serialized_data)
        """
        if isinstance(value, bytes):
            return "binary", len(value), value
        elif isinstance(value, str):
            encoded = value.encode("utf-8")
            return "text", len(encoded), encoded
        elif isinstance(value, dict):
            serialized = json.dumps(value, separators=(",", ":"))
            encoded = serialized.encode("utf-8")
            return "json", len(encoded), encoded
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    def _save_data(self, key: str, data: Union[bytes, str], content_type: str) -> None:
        """Save data to file."""
        data_path = self._get_data_path(key)

        mode = "wb" if isinstance(data, bytes) else "w"
        encoding = None if isinstance(data, bytes) else "utf-8"

        with open(data_path, mode, encoding=encoding) as f:
            f.write(data)

    def _load_data(
        self, key: str, content_type: Optional[str]
    ) -> Optional[Union[bytes, str, Dict[str, Any]]]:
        """Load data from file."""
        data_path = self._get_data_path(key)

        if not data_path.exists():
            return None

        try:
            if content_type == "binary":
                with open(data_path, "rb") as f:
                    return f.read()
            elif content_type == "json":
                with open(data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                with open(data_path, "r", encoding="utf-8") as f:
                    return f.read()

        except Exception as e:
            print(f"Error loading cached data: {e}")
            return None

    def _save_entry(self, entry: CacheEntry) -> None:
        """Save entry metadata to file."""
        meta_path = self._get_meta_path(entry.key)

        data = {
            "key": entry.key,
            "created_at": entry.created_at.isoformat(),
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            "access_count": entry.access_count,
            "last_accessed": entry.last_accessed.isoformat() if entry.last_accessed else None,
            "size_bytes": entry.size_bytes,
            "metadata": entry.metadata,
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _update_index(self, key: str, entry: CacheEntry) -> None:
        """Update the index with entry info."""
        with self._index_lock:
            self._index[key] = {
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "size_bytes": entry.size_bytes,
            }
            self._save_index()

    def _remove_from_index(self, key: str) -> None:
        """Remove key from index."""
        with self._index_lock:
            if key in self._index:
                del self._index[key]
                self._save_index()

    def _load_index(self) -> None:
        """Load index from file."""
        with self._index_lock:
            if self._index_file.exists():
                try:
                    with open(self._index_file, "r", encoding="utf-8") as f:
                        self._index = json.load(f)
                    self._stats.entry_count = len(self._index)
                except Exception:
                    self._index = {}

    def _save_index(self) -> None:
        """Save index to file."""
        with self._index_lock:
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2)

    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure enough space by evicting old entries if needed."""
        if self._max_size_bytes is None:
            return

        current_size = self._stats.total_size_bytes

        while current_size + required_bytes > self._max_size_bytes:
            # Find oldest entry to evict
            oldest_key = None
            oldest_time = None

            for key, info in self._index.items():
                created = datetime.fromisoformat(info["created_at"])
                if oldest_time is None or created < oldest_time:
                    oldest_time = created
                    oldest_key = key

            if oldest_key is None:
                break

            entry = self.get_entry(oldest_key)
            if entry and self.delete(oldest_key):
                current_size -= entry.size_bytes
            else:
                break

    def get_total_size(self) -> int:
        """Get total size of cache in bytes."""
        total = 0
        for entry in self._cache_dir.glob(f"*{self.DATA_EXTENSION}"):
            total += entry.stat().st_size
        return total

    def rebuild_index(self) -> int:
        """
        Rebuild index from existing cache files.

        Returns:
            Number of entries indexed
        """
        with self._lock:
            self._index.clear()
            count = 0

            for meta_file in self._cache_dir.glob(f"*{self.META_EXTENSION}"):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    key = data["key"]
                    self._index[key] = {
                        "created_at": data["created_at"],
                        "expires_at": data.get("expires_at"),
                        "size_bytes": data.get("size_bytes", 0),
                    }
                    count += 1

                except Exception:
                    continue

            self._save_index()
            self._stats.entry_count = count
            return count
