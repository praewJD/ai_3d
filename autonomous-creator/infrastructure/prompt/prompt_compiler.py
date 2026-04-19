# -*- coding: utf-8 -*-
"""
Prompt Compiler - CLIP 77토큰 최적화 프롬프트 생성기

토큰 압축 + 일관성 유지
"""
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class PromptCompiler:
    """
    77토큰 최적화 프롬프트 컴파일러

    CLIP 텍스트 인코더의 77토큰 제한을 해결하기 위한 압축 전략
    """

    # 토큰 제한 (안전 마진 포함)
    MAX_TOKENS = 75  # 77에서 여유분 2개

    # 품질 키워드 (공통)
    QUALITY_TOKENS = "cinematic, ultra detailed, 4k, masterpiece"

    # 스타일 토큰 맵
    STYLE_TOKENS = {
        "disney_3d": "Disney 3D style, Pixar quality, soft lighting",
        "anime": "anime style, vibrant colors, clean lines",
        "realistic": "photorealistic, detailed textures, natural lighting",
        "dark_fantasy": "dark fantasy, dramatic shadows, moody atmosphere",
        "comic": "comic book style, bold lines, vibrant colors"
    }

    # 감정 → 시각 토큰 맵
    EMOTION_TOKENS = {
        "shock": "dramatic impact, high contrast, explosive",
        "tension": "dark atmosphere, sharp shadows, suspenseful",
        "action": "dynamic motion, energy effects, intense",
        "climax": "epic scale, powerful, dramatic lighting",
        "hope": "warm lighting, bright, optimistic",
        "sadness": "melancholic, soft shadows, muted colors",
        "mystery": "enigmatic, fog, hidden details",
        "fear": "scary, dark, unsettling"
    }

    # Face Authority: IP-Adapter와 충돌하는 얼굴 묘사 금지 목록
    # 프롬프트에서 이 단어들이 포함되면 제거 (얼굴 결정권은 IP-Adapter만 가짐)
    FACE_DESCRIPTION_BAN_LIST = [
        "beautiful face", "handsome face", "pretty face", "gorgeous face",
        "big eyes", "small eyes", "round eyes", "expressive eyes",
        "long hair", "short hair", "blonde hair", "dark hair", "curly hair",
        "pale skin", "fair skin", "dark skin",
        "high cheekbones", "sharp jawline", "full lips", "thin lips",
        "cute face", "young face", "old face",
        "smiling face", "serious face", "angry face",
        "freckles", "dimples", "beauty mark",
    ]

    # 카메라 → 시각 토큰 맵
    CAMERA_TOKENS = {
        "close-up": "close-up shot, detailed face",
        "medium": "medium shot, upper body",
        "wide": "wide shot, full scene",
        "bird_eye": "aerial view, overhead",
        "low_angle": "low angle, dramatic perspective",
        "over_shoulder": "over shoulder, POV"
    }

    @classmethod
    def sanitize_face_descriptions(cls, prompt: str) -> str:
        """
        Face Authority: 프롬프트에서 얼굴 묘사 단어 제거

        IP-Adapter가 얼굴을 결정하므로, 프롬프트의 얼굴 묘사는 충돌을 일으킴.
        금지 목록의 단어를 제거하고 남은 쉼표/공백을 정리.

        Args:
            prompt: 원본 프롬프트

        Returns:
            얼굴 묘사가 제거된 프롬프트
        """
        removed_words = []
        result = prompt

        for banned in cls.FACE_DESCRIPTION_BAN_LIST:
            # 대소문자 구분 없이 제거
            pattern = re.compile(re.escape(banned), re.IGNORECASE)
            if pattern.search(result):
                removed_words.append(banned)
                result = pattern.sub("", result)

        # 제거 후 남는 쉼표/공백 정리
        # 연속된 공백 → 단일 공백
        result = re.sub(r" {2,}", " ", result)
        # 빈 쉼표 요소 제거 (", ," → ",")
        result = re.sub(r",\s*,", ",", result)
        # 연속된 쉼표 → 단일 쉼표
        result = re.sub(r",{2,}", ",", result)
        # 쉼표 앞뒤 공백 정리
        result = re.sub(r"\s*,\s*", ", ", result)
        # 선행/후행 쉼표, 공백 제거
        result = result.strip(" ,")

        # 로그 출력
        if removed_words:
            logger.info(f"[Face Authority] Removed face descriptions: {removed_words}")

        return result

    def __init__(self, max_tokens: int = 75):
        self.max_tokens = max_tokens

    def compile(
        self,
        scene_description: str,
        character_tokens: str,
        style: str = "disney_3d",
        emotion: str = None,
        camera: str = None,
        additional_tokens: str = ""
    ) -> str:
        """
        프롬프트 컴파일

        Args:
            scene_description: 장면 설명
            character_tokens: 캐릭터 핵심 토큰
            style: 스타일 (disney_3d, anime, realistic, etc.)
            emotion: 감정 (shock, tension, action, etc.)
            camera: 카메라 앵글
            additional_tokens: 추가 토큰

        Returns:
            77토큰 이하의 최적화된 프롬프트
        """
        parts = []

        # 0. Face Authority: scene_description에서 얼굴 묘사 제거
        # (character_tokens는 identity용이므로 제외)
        scene_description = self.sanitize_face_descriptions(scene_description)

        # 1. 장면 설명 (action 기반, 77토큰 앞쪽 배치로 핵심 묘사 보존)
        compressed_scene = self._compress_scene(scene_description)
        parts.append(compressed_scene)

        # 2. 캐릭터 (핵심, 최대 10단어로 압축)
        compressed_chars = self._compress_character(character_tokens)
        parts.append(compressed_chars)

        # 3. 스타일
        style_token = self.STYLE_TOKENS.get(style, self.STYLE_TOKENS["disney_3d"])
        parts.append(style_token)

        # 4. 카메라
        if camera and camera in self.CAMERA_TOKENS:
            parts.append(self.CAMERA_TOKENS[camera])

        # 5. 감정
        if emotion and emotion in self.EMOTION_TOKENS:
            parts.append(self.EMOTION_TOKENS[emotion])

        # 6. 추가 토큰
        if additional_tokens:
            parts.append(additional_tokens)

        # 7. 품질 (마지막)
        parts.append(self.QUALITY_TOKENS)

        # 조합 및 압축
        prompt = ", ".join(parts)
        prompt = self._truncate_to_tokens(prompt)

        return prompt

    def _compress_scene(self, description: str) -> str:
        """장면 설명 압축"""
        # 불필요한 단어 제거
        stop_words = ["the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for"]

        words = description.split()
        filtered = [w for w in words if w.lower() not in stop_words]

        # 최대 25단어로 제한 (장면 묘사 보존을 위해 15→25 완화)
        return " ".join(filtered[:25])

    def _compress_character(self, character_tokens: str) -> str:
        """캐릭터 appearance 압축 (최대 10단어)"""
        if not character_tokens:
            return ""

        # 불필요한 단어 제거
        filler = ["with", "wears", "wearing", "has", "he", "she", "his", "her", "a", "an", "the",
                   "and", "of", "is", "in", "over", "on", "to", "side", "style"]
        words = character_tokens.split(",")
        # 콤마로 분리된 각 특징 유지, 최대 10개
        cleaned = []
        for w in words:
            w = w.strip()
            if w and w.lower() not in filler:
                cleaned.append(w)
            if len(cleaned) >= 10:
                break

        return ", ".join(cleaned)

    def _truncate_to_tokens(self, prompt: str) -> str:
        """
        프롬프트 반환 (청킹은 SDXLGenerator에서 처리)

        기존에는 77토큰에서 잘랐으나,
        프롬프트 청킹(Prompt Chunking) 도입으로 더 이상 여기서 자르지 않음.
        SDXLGenerator가 75토큰 단위로 청킹하여 처리.
        """
        # 실제 토큰 수 로깅만
        actual_tokens = self._estimate_tokens(prompt)
        logger.debug(f"Prompt tokens: {actual_tokens:.0f} (chunking in generator)")

        return prompt

    def _estimate_tokens(self, text: str) -> float:
        """토큰 수 추정"""
        # 간단한 추정: 단어 수 * 1.3
        words = len(text.split())
        return words * 1.3

    def build_negative_prompt(
        self,
        base_negative: str = "",
        extra_negatives: List[str] = None
    ) -> str:
        """
        네거티브 프롬프트 생성

        SDXL 텍스트 렌더링 방지 키워드 포함:
        SDXL은 텍스트를 올바르게 렌더링하지 못하므로,
        글씨/로고/워터마크가 깨진 형태로 나오는 것을 방지
        """
        defaults = [
            "blurry", "deformed", "bad anatomy", "different person",
            "extra limbs", "low quality", "distorted face", "watermark",
            "text", "letters", "words", "signature", "logo", "font",
            "typography", "writing", "caption", "subtitle",
            "cropped", "worst quality",
            "normal quality", "jpeg artifacts"
        ]

        all_negatives = defaults + (extra_negatives or [])

        if base_negative:
            all_negatives = [base_negative] + all_negatives

        # 중복 제거
        unique = list(dict.fromkeys(all_negatives))

        return ", ".join(unique)


def truncate_to_77_tokens(text: str) -> str:
    """
    77토큰으로 자르기 (편의 함수)
    """
    compiler = PromptCompiler(max_tokens=75)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return ", ".join(parts[:12])  # 약 70~77토큰 유지
