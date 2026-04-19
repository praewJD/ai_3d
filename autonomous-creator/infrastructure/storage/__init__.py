"""
Storage Module - 실행 결과 저장 및 캐싱

파일 기반 저장소 (나중에 DB로 교체 가능)
"""
from .execution_log import (
    # Data classes
    RunResult,
    SceneOutput,
    CacheEntry,

    # Interface
    IProjectRepository,

    # Implementation
    FileProjectRepository,
    ExecutionLogger,

    # Convenience
    get_execution_logger,
)

__all__ = [
    # Data classes
    "RunResult",
    "SceneOutput",
    "CacheEntry",

    # Interface
    "IProjectRepository",

    # Implementation
    "FileProjectRepository",
    "ExecutionLogger",

    # Convenience
    "get_execution_logger",
]
