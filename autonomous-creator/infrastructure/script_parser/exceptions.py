# -*- coding: utf-8 -*-
"""
Script Parser Exceptions

스크립트 파싱 관련 예외 클래스
"""


class ScriptParseError(Exception):
    """스크립트 파싱 기본 예외"""
    pass


class CharacterExtractionError(ScriptParseError):
    """캐릭터 추출 실패"""
    pass


class LLMExtractionError(ScriptParseError):
    """LLM 기반 추출 실패"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error
