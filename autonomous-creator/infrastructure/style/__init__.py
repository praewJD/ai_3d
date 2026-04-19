"""
Style Module - 스타일 관리

스타일을 데이터로 관리하고 규칙 기반 스위칭 지원
"""
from .style_manager import (
    StyleManager,
    StyleSwitchingStrategy,
    StyleSwitchResult,
    get_style_manager,
    create_disney_style,
    create_realistic_style,
    create_anime_style,
)

__all__ = [
    "StyleManager",
    "StyleSwitchingStrategy",
    "StyleSwitchResult",
    "get_style_manager",
    "create_disney_style",
    "create_realistic_style",
    "create_anime_style",
]
