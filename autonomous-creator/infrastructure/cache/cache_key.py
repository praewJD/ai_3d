"""
Cache key generation for content-addressed storage.
"""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional, Union
import json
import hashlib


@dataclass(frozen=True)
class CacheKey:
    """
    Immutable cache key with hash-based identifier.

    Supports content-addressed storage where identical inputs
    always produce the same key.
    """
    hash: str
    components: Dict[str, Any] = field(default_factory=dict)
    prefix: str = ""

    def __str__(self) -> str:
        """Get the full key string."""
        if self.prefix:
            return f"{self.prefix}:{self.hash}"
        return self.hash

    @property
    def short_hash(self) -> str:
        """Get a shortened version of the hash."""
        return self.hash[:12]

    def with_prefix(self, prefix: str) -> "CacheKey":
        """Create a new key with a different prefix."""
        return CacheKey(
            hash=self.hash,
            components=self.components,
            prefix=prefix,
        )


class CacheKeyGenerator:
    """
    Generates content-addressed cache keys based on input parameters.

    Keys are deterministic - the same inputs always produce the same key.
    Supports including model settings, seeds, and other parameters in the hash.
    """

    # Common prefixes for different cache types
    PREFIX_IMAGE = "img"
    PREFIX_VIDEO = "vid"
    PREFIX_AUDIO = "aud"
    PREFIX_PROMPT = "prm"
    PREFIX_METADATA = "meta"

    def __init__(self, default_prefix: str = ""):
        """
        Initialize the key generator.

        Args:
            default_prefix: Default prefix to use for all keys
        """
        self._default_prefix = default_prefix

    def generate(
        self,
        *args,
        prefix: Optional[str] = None,
        **kwargs,
    ) -> CacheKey:
        """
        Generate a cache key from arbitrary inputs.

        Args:
            *args: Positional arguments to include in hash
            prefix: Key prefix override
            **kwargs: Keyword arguments to include in hash

        Returns:
            A CacheKey object with hash and metadata
        """
        components = self._normalize_components(*args, **kwargs)
        content = self._serialize_components(components)
        hash_value = self._hash_content(content)

        return CacheKey(
            hash=hash_value,
            components=kwargs,
            prefix=prefix or self._default_prefix,
        )

    def generate_image_key(
        self,
        prompt: str,
        model: str,
        seed: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        negative_prompt: Optional[str] = None,
        **extra_params,
    ) -> CacheKey:
        """
        Generate a cache key for image generation.

        Args:
            prompt: The image generation prompt
            model: Model identifier
            seed: Random seed
            width: Image width
            height: Image height
            steps: Number of inference steps
            guidance_scale: Guidance scale parameter
            negative_prompt: Negative prompt
            **extra_params: Additional parameters

        Returns:
            Cache key for this image generation request
        """
        return self.generate(
            prompt=prompt,
            model=model,
            seed=seed,
            width=width,
            height=height,
            steps=steps,
            guidance_scale=guidance_scale,
            negative_prompt=negative_prompt,
            **extra_params,
            prefix=self.PREFIX_IMAGE,
        )

    def generate_video_key(
        self,
        prompt: str,
        model: str,
        seed: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        fps: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        source_image_key: Optional[str] = None,
        **extra_params,
    ) -> CacheKey:
        """
        Generate a cache key for video generation.

        Args:
            prompt: The video generation prompt
            model: Model identifier
            seed: Random seed
            duration_seconds: Video duration
            fps: Frames per second
            width: Video width
            height: Video height
            source_image_key: Key of source image if using image-to-video
            **extra_params: Additional parameters

        Returns:
            Cache key for this video generation request
        """
        return self.generate(
            prompt=prompt,
            model=model,
            seed=seed,
            duration_seconds=duration_seconds,
            fps=fps,
            width=width,
            height=height,
            source_image_key=source_image_key,
            **extra_params,
            prefix=self.PREFIX_VIDEO,
        )

    def generate_audio_key(
        self,
        text: str,
        voice: str,
        model: Optional[str] = None,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        language: Optional[str] = None,
        **extra_params,
    ) -> CacheKey:
        """
        Generate a cache key for TTS audio generation.

        Args:
            text: The text to synthesize
            voice: Voice identifier
            model: TTS model identifier
            speed: Speech speed
            pitch: Voice pitch
            language: Language code
            **extra_params: Additional parameters

        Returns:
            Cache key for this audio generation request
        """
        return self.generate(
            text=text,
            voice=voice,
            model=model,
            speed=speed,
            pitch=pitch,
            language=language,
            **extra_params,
            prefix=self.PREFIX_AUDIO,
        )

    def generate_prompt_key(
        self,
        source_content: str,
        prompt_type: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt_hash: Optional[str] = None,
        **extra_params,
    ) -> CacheKey:
        """
        Generate a cache key for AI-generated prompts.

        Args:
            source_content: The input content being processed
            prompt_type: Type of prompt being generated
            model: Model identifier
            temperature: Generation temperature
            max_tokens: Maximum tokens
            system_prompt_hash: Hash of system prompt used
            **extra_params: Additional parameters

        Returns:
            Cache key for this prompt generation request
        """
        return self.generate(
            source_content=source_content,
            prompt_type=prompt_type,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt_hash=system_prompt_hash,
            **extra_params,
            prefix=self.PREFIX_PROMPT,
        )

    def from_string(self, key_string: str) -> CacheKey:
        """
        Parse a cache key string back into a CacheKey object.

        Args:
            key_string: The key string to parse

        Returns:
            CacheKey object
        """
        if ":" in key_string:
            prefix, hash_value = key_string.split(":", 1)
            return CacheKey(hash=hash_value, prefix=prefix)
        return CacheKey(hash=key_string)

    def _normalize_components(self, *args, **kwargs) -> Dict[str, Any]:
        """Normalize all components into a single dictionary."""
        components = {}

        # Add positional args with index keys
        for i, arg in enumerate(args):
            components[f"_arg_{i}"] = self._normalize_value(arg)

        # Add keyword args
        for key, value in sorted(kwargs.items()):
            components[key] = self._normalize_value(value)

        return components

    def _normalize_value(self, value: Any) -> Any:
        """Normalize a value for consistent hashing."""
        if value is None:
            return None
        elif isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._normalize_value(v) for v in value]
        elif isinstance(value, dict):
            return {
                k: self._normalize_value(v)
                for k, v in sorted(value.items())
            }
        elif hasattr(value, "__dict__"):
            # Handle dataclasses and objects
            return self._normalize_value(vars(value))
        else:
            return str(value)

    def _serialize_components(self, components: Dict[str, Any]) -> str:
        """Serialize components to a string for hashing."""
        try:
            return json.dumps(
                components,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            return str(components)

    def _hash_content(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return sha256(content.encode("utf-8")).hexdigest()


def hash_file(filepath: str, chunk_size: int = 8192) -> str:
    """
    Generate a hash for a file's contents.

    Args:
        filepath: Path to the file
        chunk_size: Size of chunks to read at a time

    Returns:
        SHA-256 hash of the file contents
    """
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_bytes(data: bytes) -> str:
    """
    Generate a hash for bytes data.

    Args:
        data: Bytes to hash

    Returns:
        SHA-256 hash of the data
    """
    return hashlib.sha256(data).hexdigest()


def hash_string(text: str) -> str:
    """
    Generate a hash for a string.

    Args:
        text: String to hash

    Returns:
        SHA-256 hash of the string
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
