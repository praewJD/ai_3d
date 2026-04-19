"""
Scene Entity Module
"""
from .scene_graph import (
    # Main entities
    SceneGraph,
    SceneNode,
    DialogueLine,

    # Style (NEW!)
    SceneStyle,
    StyleType,
    LightingType,
    RenderingType,
    CharacterIdentity,

    # Enums
    CameraAngle,
    ActionType,
    Mood,
    Transition,

    # Constants
    STYLE_PROMPTS,
    LIGHTING_PROMPTS,
    COLOR_PALETTE_PROMPTS,
)

__all__ = [
    # Main entities
    "SceneGraph",
    "SceneNode",
    "DialogueLine",

    # Style
    "SceneStyle",
    "StyleType",
    "LightingType",
    "RenderingType",
    "CharacterIdentity",

    # Enums
    "CameraAngle",
    "ActionType",
    "Mood",
    "Transition",

    # Constants
    "STYLE_PROMPTS",
    "LIGHTING_PROMPTS",
    "COLOR_PALETTE_PROMPTS",
]
