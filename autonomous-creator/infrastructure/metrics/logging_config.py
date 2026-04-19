"""Logging Configuration - 스토리 컴파일 로깅 설정"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import os


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/story_compiler.log",
    format_string: str = None
) -> logging.Logger:
    """로깅 설정

    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로
        format_string: 커스텀 포맷 문자열

    Returns:
        설정된 루트 로거
    """
    # .env에서 DEBUG 설정 확인
    debug = os.getenv("DEBUG", "false").lower() == "true"
    if debug:
        log_level = "DEBUG"

    # 로그 레벨 변환
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 기본 포맷
    if format_string is None:
        format_string = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    # 포맷터 생성
    formatter = logging.Formatter(
        fmt=format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 기존 핸들러 제거
    root_logger.handlers.clear()

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_file,
            encoding='utf-8',
            mode='a'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


class StoryLogger:
    """스토리 컴파일 전용 로거"""

    def __init__(self, story_id: str, log_file: str = None):
        self.story_id = story_id
        self.logger = logging.getLogger(f"story.{story_id}")
        self._stage_times: dict = {}

        # 스토리별 로그 파일
        if log_file:
            self._setup_story_file_handler(log_file)

    def _setup_story_file_handler(self, log_file: str):
        """스토리별 파일 핸들러 설정"""
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(
            log_file,
            encoding='utf-8',
            mode='a'
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [story:%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _log(self, level: int, message: str, *args):
        """내부 로그 메서드"""
        self.logger.log(level, f"[{self.story_id}] {message}", *args)

    def debug(self, message: str, *args):
        """디버그 로그"""
        self._log(logging.DEBUG, message, *args)

    def info(self, message: str, *args):
        """정보 로그"""
        self._log(logging.INFO, message, *args)

    def warning(self, message: str, *args):
        """경고 로그"""
        self._log(logging.WARNING, message, *args)

    def error(self, message: str, *args):
        """에러 로그"""
        self._log(logging.ERROR, message, *args)

    def stage_start(self, stage: str, details: str = None):
        """단계 시작 로그"""
        self._stage_times[stage] = datetime.now()
        msg = f"STAGE_START: {stage}"
        if details:
            msg += f" - {details}"
        self.info(msg)

    def stage_complete(self, stage: str, duration: float = None, details: str = None):
        """단계 완료 로그"""
        if stage in self._stage_times:
            elapsed = (datetime.now() - self._stage_times.pop(stage)).total_seconds()
            if duration is None:
                duration = elapsed

        msg = f"STAGE_COMPLETE: {stage}"
        if duration is not None:
            msg += f" (took {duration:.2f}s)"
        if details:
            msg += f" - {details}"
        self.info(msg)

    def stage_error(self, stage: str, error: str, details: str = None):
        """단계 에러 로그"""
        self._stage_times.pop(stage, None)
        msg = f"STAGE_ERROR: {stage} - {error}"
        if details:
            msg += f" | {details}"
        self.error(msg)

    def retry(self, stage: str, reason: str, attempt: int = None):
        """재시도 로그"""
        msg = f"RETRY: {stage} - {reason}"
        if attempt is not None:
            msg += f" (attempt {attempt})"
        self.warning(msg)

    def metric(self, metric_name: str, value):
        """메트릭 기록 로그"""
        self.info(f"METRIC: {metric_name} = {value}")

    def cost(self, amount: float, description: str = None):
        """비용 기록 로그"""
        msg = f"COST: ${amount:.4f}"
        if description:
            msg += f" - {description}"
        self.info(msg)
