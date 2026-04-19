"""
Series-Aware Prompt Builder - 시리즈 컨텍스트 기반 프롬프트 생성

시리즈, 캐릭터, 장소 정보를 통합한 프롬프트 생성
"""
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

from infrastructure.series import get_series_manager
from infrastructure.character import get_character_library
from infrastructure.api.config.api_config import get_api_config

logger = logging.getLogger(__name__)


# ============================================================
# 프롬프트 매핑 상수
# ============================================================

CAMERA_ANGLE_PROMPTS = {
    "close-up": "close-up shot, portrait framing, shallow depth of field, detailed facial features",
    "medium": "medium shot, upper body visible, natural framing",
    "wide": "wide shot, full body, environmental context, establishing shot",
    "bird_eye": "bird's eye view, overhead angle, top-down perspective",
    "low_angle": "low angle shot, dramatic perspective, heroic stance",
    "over_shoulder": "over-the-shoulder shot, POV conversation, depth layers",
    "pov": "first person perspective, POV shot, immersive angle",
}

ACTION_PROMPTS = {
    "idle": "standing still, calm pose, relaxed",
    "walking": "walking naturally, gentle movement, smooth gait",
    "running": "running dynamically, motion blur, energetic",
    "talking": "speaking, animated expression, lip movement",
    "fighting": "dynamic action pose, combat stance, intense",
    "dancing": "dancing gracefully, rhythmic movement",
    "sitting": "sitting comfortably, relaxed posture",
    "standing": "standing naturally, poised stance",
}

MOOD_VISUAL_MAP = {
    "happy": "bright warm lighting, vibrant colors, cheerful atmosphere, soft glow",
    "sad": "dim cool lighting, muted colors, melancholic atmosphere, soft shadows",
    "neutral": "balanced natural lighting, neutral tones, calm atmosphere",
    "tense": "dramatic lighting, high contrast, shadows, suspenseful atmosphere",
    "romantic": "soft golden hour lighting, warm pink tones, dreamy atmosphere, lens flare",
    "mysterious": "low key lighting, deep shadows, fog, enigmatic atmosphere",
    "excited": "dynamic lighting, saturated colors, energetic atmosphere, vibrant",
    "peaceful": "soft diffused lighting, pastel colors, serene atmosphere, gentle",
    "scary": "dark harsh lighting, cold blue tones, ominous atmosphere, heavy shadows",
    "dramatic": "theatrical lighting, strong contrast, cinematic atmosphere, rim light",
}


@dataclass
class PromptContext:
    """프롬프트 컨텍스트"""
    series_id: str
    series_name: str
    episode_id: Optional[str] = None
    scene_id: Optional[str] = None
    character_ids: List[str] = None
    location_key: Optional[str] = None

    # 상세 설정
    expressions: Dict[str, str] = None
    poses: Dict[str, str] = None
    outfits: Dict[str, str] = None

    # 추가 설명
    scene_description: str = ""
    mood: str = ""
    time_of_day: str = ""


class SeriesPromptBuilder:
    """
    시리즈 기반 프롬프트 빌더

    시리즈 컨텍스트를 사용하여 일관된 스타일의 프롬프트 생성
    """

    def __init__(self):
        self.series_manager = get_series_manager()
        self.character_library = get_character_library()
        self.api_config = get_api_config()

    async def build_image_prompt(
        self,
        context: PromptContext,
        additional_keywords: List[str] = None,
        camera_angle: str = None,
        action: str = None
    ) -> str:
        """
        이미지 프롬프트 생성

        Args:
            context: 프롬프트 컨텍스트
            additional_keywords: 추가 키워드
            camera_angle: 카메라 앵글 (CAMERA_ANGLE_PROMPTS 키)
            action: 액션 (ACTION_PROMPTS 키)

        Returns:
            완성된 이미지 프롬프트
        """
        parts = []

        # 1. 시리즈 스타일 접두사
        series_context = await self.series_manager.get_prompt_context(context.series_id)
        parts.append(series_context.get("style_prefix", ""))

        # 2. 카메라 앵글 (매핑 테이블 사용)
        if camera_angle and camera_angle in CAMERA_ANGLE_PROMPTS:
            parts.append(CAMERA_ANGLE_PROMPTS[camera_angle])

        # 3. 캐릭터
        if context.character_ids:
            char_prompts = []
            for char_id in context.character_ids:
                char = await self.character_library.load(char_id)
                if char:
                    expr = (context.expressions or {}).get(char_id, "default")
                    pose = (context.poses or {}).get(char_id, "standing")
                    outfit = (context.outfits or {}).get(char_id, "default")

                    char_prompt = char.get_full_prompt(
                        expression=expr,
                        pose=pose,
                        outfit=outfit,
                        include_disney_style=False
                    )
                    char_prompts.append(char_prompt)

            if char_prompts:
                parts.append(", ".join(char_prompts))

        # 4. 액션 (매핑 테이블 사용)
        if action and action in ACTION_PROMPTS:
            parts.append(ACTION_PROMPTS[action])

        # 5. 장소
        if context.location_key:
            series = await self.series_manager.load(context.series_id)
            if series and context.location_key in series.locations:
                parts.append(series.locations[context.location_key])
            parts.append(series_context.get("world_setting", ""))

        # 6. 장면 설명
        if context.scene_description:
            parts.append(context.scene_description)

        # 7. 분위기/시간 (매핑 테이블 사용)
        if context.mood:
            if context.mood in MOOD_VISUAL_MAP:
                parts.append(MOOD_VISUAL_MAP[context.mood])
            else:
                parts.append(f"{context.mood} atmosphere")
        if context.time_of_day:
            parts.append(context.time_of_day)

        # 8. 추가 키워드
        if additional_keywords:
            parts.extend(additional_keywords)

        # 9. 품질 태그
        parts.extend([
            "masterpiece",
            "best quality",
            "highly detailed"
        ])

        return ", ".join(p for p in parts if p)

    async def build_video_prompt(
        self,
        context: PromptContext,
        motion_description: str = "",
        camera_motion: str = "",
        action: str = None,
        camera_angle: str = None
    ) -> str:
        """
        영상 프롬프트 생성

        Args:
            context: 프롬프트 컨텍스트
            motion_description: 모션 설명 (직접 지정 시 사용)
            camera_motion: 카메라 모션 (직접 지정 시 사용)
            action: 액션 키 (ACTION_PROMPTS에서 자동 생성)
            camera_angle: 카메라 앵글 키 (CAMERA_ANGLE_PROMPTS에서 자동 생성)

        Returns:
            완성된 영상 프롬프트
        """
        parts = []

        # 1. 기본 이미지 프롬프트 (camera_angle, action 포함)
        image_prompt = await self.build_image_prompt(
            context,
            camera_angle=camera_angle,
            action=action
        )
        parts.append(image_prompt)

        # 2. 모션 설명 (직접 지정 또는 ACTION_PROMPTS에서 자동 생성)
        if motion_description:
            parts.append(motion_description)
        elif action and action in ACTION_PROMPTS:
            # 액션을 기반으로 모션 설명 자동 생성
            parts.append(f"{ACTION_PROMPTS[action]}, fluid movement")

        # 3. 카메라 모션 (직접 지정 또는 CAMERA_ANGLE_PROMPTS 기반 자동 생성)
        if camera_motion:
            parts.append(camera_motion)
        elif camera_angle and camera_angle in CAMERA_ANGLE_PROMPTS:
            # 카메라 앵글을 기반으로 카메라 모션 자동 생성
            angle_motion_map = {
                "close-up": "subtle camera drift, gentle zoom",
                "medium": "smooth camera pan, steady tracking",
                "wide": "slow establishing shot, wide sweep",
                "bird_eye": "slow aerial descent, top-down tracking",
                "low_angle": "slow upward tilt, dramatic reveal",
                "over_shoulder": "subtle dolly movement, focus shift",
                "pov": "first person movement, immersive camera",
            }
            parts.append(angle_motion_map.get(camera_angle, "smooth camera movement"))

        # 4. 영상 품질
        parts.extend([
            "smooth motion",
            "cinematic quality",
            "consistent animation"
        ])

        return ", ".join(parts)

    async def build_negative_prompt(
        self,
        context: PromptContext
    ) -> str:
        """네거티브 프롬프트"""
        negatives = []

        # 시리즈 기본 네거티브
        series_context = await self.series_manager.get_prompt_context(context.series_id)
        if series_context.get("negative_prompt"):
            negatives.append(series_context["negative_prompt"])

        # 캐릭터별 네거티브
        if context.character_ids:
            for char_id in context.character_ids:
                char = await self.character_library.load(char_id)
                if char:
                    negatives.append(char.get_negative_prompt())

        # 공통 네거티브
        negatives.extend([
            "blurry",
            "low quality",
            "bad anatomy",
            "watermark",
            "text",
            "signature"
        ])

        # 중복 제거
        seen = set()
        unique = []
        for n in negatives:
            if n not in seen:
                seen.add(n)
                unique.append(n)

        return ", ".join(unique)

    async def get_full_generation_params(
        self,
        context: PromptContext,
        generation_type: str = "image"
    ) -> Dict[str, Any]:
        """
        전체 생성 파라미터

        Args:
            context: 프롬프트 컨텍스트
            generation_type: "image" 또는 "video"

        Returns:
            생성 파라미터 딕셔너리
        """
        if generation_type == "image":
            prompt = await self.build_image_prompt(context)
        else:
            prompt = await self.build_video_prompt(context)

        negative = await self.build_negative_prompt(context)

        return {
            "prompt": prompt,
            "negative_prompt": negative,
            "series_id": context.series_id,
            "episode_id": context.episode_id,
            "scene_id": context.scene_id,
            "character_ids": context.character_ids or [],
            "style_prefix": self.api_config.get_style_prompt_prefix()
        }


# ============================================================
# 편의 함수
# ============================================================

_prompt_builder: Optional[SeriesPromptBuilder] = None


def get_prompt_builder() -> SeriesPromptBuilder:
    """프롬프트 빌더 싱글톤"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = SeriesPromptBuilder()
    return _prompt_builder


async def quick_prompt(
    series_id: str,
    scene_description: str,
    character_ids: List[str] = None
) -> str:
    """
    빠른 프롬프트 생성

    Args:
        series_id: 시리즈 ID
        scene_description: 장면 설명
        character_ids: 캐릭터 ID 목록

    Returns:
        프롬프트
    """
    builder = get_prompt_builder()
    context = PromptContext(
        series_id=series_id,
        character_ids=character_ids or [],
        scene_description=scene_description
    )
    return await builder.build_image_prompt(context)
