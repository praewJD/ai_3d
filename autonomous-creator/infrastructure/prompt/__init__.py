# -*- coding: utf-8 -*-
"""
Prompt Module - 프롬프트 생성

구성요소:
- CharacterTemplate: 캐릭터 템플릿
- LocationDB: 장소 데이터베이스
- PromptBuilder: 템플릿 기반 프롬프트 빌더
- PromptGenerator: AI 기반 프롬프트 생성기
- PromptOrchestrator: SceneGraph → 프롬프트 변환
- PromptCompiler: CLIP 77토큰 최적화 컴파일러 (NEW!)
"""
from .character_template import CharacterTemplate
from .location_db import LocationDB, LocationData
from .prompt_builder import PromptBuilder, ScenePrompt
from .prompt_generator import (
    PromptGenerator,
    PromptEnhancer,
    PromptType,
    GeneratedPrompts
)
from .prompt_orchestrator import (
    PromptOrchestrator,
    ImagePromptBundle,
    VideoPromptBundle,
    TTSInput,
    MotionIntensity,
    get_prompt_orchestrator,
    DISNEY_3D_PREFIX,
    CAMERA_ANGLE_PROMPTS,
    ACTION_PROMPTS,
    MOOD_VISUAL_MAP,
)
from .prompt_compiler import (
    PromptCompiler,
    truncate_to_77_tokens,
)

__all__ = [
    'CharacterTemplate',
    'LocationDB',
    'LocationData',
    'PromptBuilder',
    'ScenePrompt',
    # AI 기반 생성
    'PromptGenerator',
    'PromptEnhancer',
    'PromptType',
    'GeneratedPrompts',
    # PromptOrchestrator
    'PromptOrchestrator',
    'ImagePromptBundle',
    'VideoPromptBundle',
    'TTSInput',
    'MotionIntensity',
    'get_prompt_orchestrator',
    'DISNEY_3D_PREFIX',
    'CAMERA_ANGLE_PROMPTS',
    'ACTION_PROMPTS',
    'MOOD_VISUAL_MAP',
    # PromptCompiler (NEW!)
    'PromptCompiler',
    'truncate_to_77_tokens',
]
