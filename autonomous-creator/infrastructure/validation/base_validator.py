"""
Base Validator - 검증 기본 클래스

모든 검증기가 상속받아야 하는 추상 클래스
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path
import asyncio
import logging

from .quality_metrics import ValidationResult


logger = logging.getLogger(__name__)


class BaseValidator(ABC):
    """
    검증기 기본 클래스

    모든 품질 검증기가 구현해야 하는 인터페이스
    """

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: 엄격 모드 (더 높은 기준 적용)
        """
        self.strict_mode = strict_mode

    @abstractmethod
    async def validate(self, source: str) -> ValidationResult:
        """
        검증 실행

        Args:
            source: 검증할 파일 경로 또는 URL

        Returns:
            ValidationResult: 검증 결과
        """
        pass

    @abstractmethod
    async def validate_batch(
        self,
        sources: list[str]
    ) -> list[ValidationResult]:
        """
        일괄 검증

        Args:
            sources: 검증할 파일 경로 목록

        Returns:
            검증 결과 목록
        """
        pass

    async def check_exists(self, path: str) -> bool:
        """파일 존재 확인"""
        return Path(path).exists()

    async def get_file_size(self, path: str) -> int:
        """파일 크기 확인 (bytes)"""
        return Path(path).stat().st_size

    def _log_result(self, source: str, result: ValidationResult):
        """결과 로깅"""
        if result.is_valid:
            logger.info(f"✓ Validation passed: {source}")
        else:
            logger.warning(f"✗ Validation failed: {source}")
            for issue in result.metrics.issues:
                logger.warning(f"  - {issue}")
