"""
Character Entity Module
"""
from .character import (
    Character,
    CharacterType,
    CharacterRole,
    CharacterGender,
    CharacterAppearance,
    create_protagonist,
    create_animal_character
)

__all__ = [
    "Character",
    "CharacterType",
    "CharacterRole",
    "CharacterGender",
    "CharacterAppearance",
    "create_protagonist",
    "create_animal_character",
]
