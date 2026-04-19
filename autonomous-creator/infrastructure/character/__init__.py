"""
Character Module - 캐릭터 관리

Disney 3D 스타일 캐릭터 생성 및 관리
"""
from .character_library import (
    CharacterLibrary,
    get_character_library
)
from .character_generator import (
    CharacterGenerator,
    get_character_generator,
    DISNEY_3D_TEMPLATES,
    HAIR_STYLES,
    OUTFIT_TEMPLATES,
    ANIMAL_TEMPLATES
)

__all__ = [
    # Library
    "CharacterLibrary",
    "get_character_library",
    # Generator
    "CharacterGenerator",
    "get_character_generator",
    # Templates
    "DISNEY_3D_TEMPLATES",
    "HAIR_STYLES",
    "OUTFIT_TEMPLATES",
    "ANIMAL_TEMPLATES",
]
