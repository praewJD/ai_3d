# -*- coding: utf-8 -*-
"""
Image Generation Exceptions

이미지 생성 관련 예외 클래스
"""


class ImageGenerationError(Exception):
    """이미지 생성 기본 예외"""
    pass


class IPAdapterError(ImageGenerationError):
    """IP-Adapter 관련 오류"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class CharacterCacheError(ImageGenerationError):
    """캐릭터 캐시 관련 오류"""
    pass


class ReferenceImageError(ImageGenerationError):
    """기준 이미지 관련 오류"""
    pass
