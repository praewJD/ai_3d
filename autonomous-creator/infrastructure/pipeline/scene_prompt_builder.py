# -*- coding: utf-8 -*-
"""
ScenePromptBuilder - StorySpec SceneSpec을 SDXL 이미지 프롬프트로 변환

SceneSpec의 시각 정보를 PromptCompiler를 통해 77토큰 제한 프롬프트로 컴파일합니다.
Face Authority 원칙에 따라 얼굴 묘사는 PromptCompiler가 자동 필터링합니다.
"""
from typing import List, Dict, Optional
import logging

from infrastructure.prompt.prompt_compiler import PromptCompiler
from infrastructure.story.story_spec import SceneSpec, CharacterSpec

logger = logging.getLogger(__name__)


# 카메라 앵글 → 프롬프트 용어 매핑
CAMERA_MAP: Dict[str, str] = {
    "close-up": "close-up shot",
    "medium_shot": "medium shot",
    "wide_shot": "wide establishing shot",
    "extreme_closeup": "extreme close-up",
    "low_angle": "low angle shot",
    "high_angle": "high angle shot",
    "bird_eye": "bird's eye view",
    "over_shoulder": "over the shoulder shot",
    "dutch_angle": "dutch angle",
    "medium": "medium shot",
    "wide": "wide shot",
}

# 무드 → 프롬프트 용어 매핑
MOOD_MAP: Dict[str, str] = {
    "tense": "tense atmosphere",
    "dark": "dark moody lighting",
    "bright": "bright cheerful lighting",
    "mysterious": "mysterious foggy atmosphere",
    "peaceful": "peaceful serene ambiance",
    "epic": "epic grand scale",
    "romantic": "warm romantic glow",
    "horror": "creepy unsettling atmosphere",
    "joyful": "vibrant joyful energy",
    "sad": "melancholic muted tones",
    "neutral": "balanced natural lighting",
    "dramatic": "dramatic high contrast lighting",
    "suspenseful": "suspenseful shadowy lighting",
    "cheerful": "bright warm cheerful tone",
    "gloomy": "gloomy desaturated atmosphere",
}


class ScenePromptBuilder:
    """StorySpec SceneSpec -> SDXL 이미지 프롬프트 변환기"""

    # IP-Adapter LoRA 트리거 워드 (항상 프롬프트 앞에 추가)
    TRIGGER_WORDS = "MG_ip, pixar"

    def __init__(self):
        self.prompt_compiler = PromptCompiler()

    def build_prompt(
        self,
        scene: SceneSpec,
        characters: List[CharacterSpec],
        style: str = "disney_3d",
    ) -> str:
        """
        SceneSpec -> 이미지 생성 프롬프트 변환

        Args:
            scene: 장면 명세
            characters: 등장 캐릭터 목록 (appearance 포함)
            style: 스타일 ("disney_3d")

        Returns:
            SDXLGenerator에 전달할 프롬프트 (trigger_words + 컴파일된 프롬프트)
        """
        # 1. 장면 설명 구성: action + location + mood
        scene_description = self.build_scene_description(scene)

        # 2. 등장 캐릭터의 appearance 토큰 조합
        # 다중 인물(2인 이상): appearance 제거 (토큰 뒤섞임 방지, action에 의존)
        # 1인물: appearance 유지 (캐릭터 디테일 보존)
        if len(scene.characters) >= 2:
            character_tokens = ""  # action에 이미 인물 묘사 포함됨
            logger.info(
                f"[ScenePromptBuilder] 다중 인물 씬 ({len(scene.characters)}명): "
                f"appearance 토큰 제외, action에 의존"
            )
        else:
            character_tokens = self.get_character_appearance(
                scene.characters, characters
            )

        # 3. 카메라 앵글 변환
        camera_prompt = self.camera_to_prompt(scene.camera)

        # 4. PromptCompiler.compile() 호출 (77토큰 제한 + 얼굴 묘사 필터 자동 적용)
        compiled_prompt = self.prompt_compiler.compile(
            scene_description=scene_description,
            character_tokens=character_tokens,
            style=style,
            emotion=scene.emotion,
            camera=camera_prompt,
        )

        # 5. trigger_words (MG_ip, pixar)를 프롬프트 앞에 추가
        # 중복 방지: 이미 포함되어 있으면 다시 추가하지 않음
        trigger_tokens = self.TRIGGER_WORDS.split(", ")
        existing_lower = compiled_prompt.lower()
        new_trigger_parts = [
            t for t in trigger_tokens
            if t.lower() not in existing_lower
        ]
        trigger_prefix = ", ".join(new_trigger_parts)
        if trigger_prefix:
            final_prompt = f"{trigger_prefix}, {compiled_prompt}"
        else:
            final_prompt = compiled_prompt

        # 6. SDXL 텍스트 렌더링 방지: positive prompt에도 텍스트 방지 지시문 추가
        # SDXL은 텍스트를 올바르게 렌더링하지 못하므로, 글씨 생성을 억제
        text_prevention = ", no text, no letters, no watermark"
        final_prompt = final_prompt + text_prevention

        logger.info(
            f"[ScenePromptBuilder] scene={scene.id}, "
            f"chars={scene.characters}, prompt_length={len(final_prompt)}"
        )

        return final_prompt

    def build_scene_description(self, scene: SceneSpec) -> str:
        """
        SceneSpec의 핵심 시각 정보를 조합

        action이 주요 시각 묘사이며, location과 mood를 보조 정보로 추가합니다.

        Args:
            scene: 장면 명세

        Returns:
            시각 묘사 문자열
        """
        parts = []

        # action이 주요 시각 묘사
        if scene.action:
            parts.append(scene.action)

        # location 보조 정보
        if scene.location:
            parts.append(f"in {scene.location}")

        # mood 보조 정보
        mood_prompt = self.mood_to_prompt(scene.mood)
        if mood_prompt:
            parts.append(mood_prompt)

        return ", ".join(parts)

    def get_character_appearance(
        self,
        character_ids: List[str],
        characters: List[CharacterSpec],
    ) -> str:
        """
        등장 캐릭터의 appearance를 토큰으로 조합

        Face Authority 원칙: appearance는 이미지 생성용 시각 묘사이며,
        얼굴 묘사는 PromptCompiler가 자동 필터링합니다.

        Args:
            character_ids: 장면에 등장하는 캐릭터 ID 목록
            characters: 전체 캐릭터 명세 목록

        Returns:
            캐릭터 appearance 토큰 문자열 (콤마로 구분)
        """
        # character_id -> CharacterSpec 빠른 조회용 매핑
        char_map = {c.id: c for c in characters}

        appearances = []
        for char_id in character_ids:
            char_spec = char_map.get(char_id)
            if char_spec and char_spec.appearance:
                appearances.append(char_spec.appearance)
            else:
                logger.warning(
                    f"[ScenePromptBuilder] 캐릭터 '{char_id}'의 appearance를 찾을 수 없음"
                )

        # 최대 3명까지 (프롬프트 길이 제한)
        return ", ".join(appearances[:3])

    def camera_to_prompt(self, camera: str) -> str:
        """
        카메라 앵글을 프롬프트 용어로 변환

        Args:
            camera: SceneSpec의 camera 값

        Returns:
            프롬프트용 카메라 용어 (PromptCompiler.CAMERA_TOKENS 키)
        """
        # PromptCompiler.CAMERA_TOKENS에 있는 키인지 먼저 확인
        if camera in self.prompt_compiler.CAMERA_TOKENS:
            return camera

        # 별도 매핑에서 조회
        if camera in CAMERA_MAP:
            mapped = CAMERA_MAP[camera]
            # PromptCompiler 토큰의 키 형태로 변환 시도
            for key in self.prompt_compiler.CAMERA_TOKENS:
                if key in mapped or mapped.startswith(key):
                    return key
            return mapped

        # 기본값: medium shot
        logger.debug(
            f"[ScenePromptBuilder] 알 수 없는 카메라 앵글 '{camera}', 기본값 사용"
        )
        return "medium"

    def mood_to_prompt(self, mood: str) -> str:
        """
        무드를 프롬프트 용어로 변환

        Args:
            mood: SceneSpec의 mood 값

        Returns:
            프롬프트용 무드 용어
        """
        if mood in MOOD_MAP:
            return MOOD_MAP[mood]

        # 매핑에 없으면 원본 mood 그대로 반환
        if mood and mood != "neutral":
            return f"{mood} atmosphere"

        return ""

    def build_negative_prompt(
        self,
        extra_negatives: Optional[List[str]] = None,
    ) -> str:
        """
        네거티브 프롬프트 생성

        텍스트 렌더링 방지 + 눈 일그러짐 방지 키워드 포함

        Args:
            extra_negatives: 추가 네거티브 토큰 목록

        Returns:
            네거티브 프롬프트 문자열
        """
        # 눈 일그러짐/비대칭 방지 키워드 자동 추가
        eye_prevention = [
            "asymmetric eyes", "cross-eyed", "deformed eyes",
            "misaligned eyes", "uneven eyes"
        ]
        all_extras = eye_prevention + (extra_negatives or [])

        return self.prompt_compiler.build_negative_prompt(
            extra_negatives=all_extras
        )
