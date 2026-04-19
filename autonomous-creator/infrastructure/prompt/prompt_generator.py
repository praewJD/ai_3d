"""
Prompt Generator - AI 기반 프롬프트 생성

장면 설명을 이미지/영상 생성용 프롬프트로 변환
"""
import json
from typing import Optional, Dict, List, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from core.domain.entities.story import Scene, Story
from core.domain.entities.preset import StylePreset
from core.domain.interfaces.ai_provider import IAIProvider


class PromptType(str, Enum):
    """프롬프트 타입"""
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class GeneratedPrompts:
    """생성된 프롬프트 결과"""
    scene_id: str
    image_prompt: str
    video_prompt: str
    negative_prompt: str
    raw_description: str


class PromptGenerator:
    """
    AI 기반 프롬프트 생성기

    장면 설명 → 고품질 이미지/영상 프롬프트 변환
    """

    TEMPLATE_DIR = Path(__file__).parent / "templates"

    def __init__(
        self,
        llm_provider: IAIProvider,
        style_preset: Optional[StylePreset] = None,
        model_type: str = "luma_kling"
    ):
        self.llm = llm_provider
        self.style_preset = style_preset
        self.model_type = model_type

        # 템플릿 로드
        self._image_template = self._load_template("image.json")
        self._video_template = self._load_template("video.json")

    def _load_template(self, filename: str) -> dict:
        """템플릿 파일 로드"""
        template_path = self.TEMPLATE_DIR / filename
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    async def generate_image_prompt(
        self,
        scene: Scene,
        enhance: bool = True
    ) -> str:
        """
        이미지 생성용 프롬프트 생성

        Args:
            scene: 장면 엔티티
            enhance: 품질 강화 태그 추가 여부

        Returns:
            이미지 생성용 프롬프트
        """
        # 스타일 접두사 가져오기
        style_name = self._get_style_name()
        style_prefix = self._image_template.get("style_prefixes", {}).get(
            style_name, "high quality artwork"
        )

        # LLM으로 프롬프트 생성
        prompt_request = f"""Convert this scene description into a detailed image generation prompt.

Scene: {scene.description}

Style: {style_name}

Requirements:
1. Expand the description with visual details
2. Include lighting and atmosphere
3. Add composition details (vertical 9:16 ratio)
4. Keep the main subject clear
5. Output ONLY the prompt, no explanations

Format: comma-separated tags"""

        response = await self.llm.generate(prompt_request)

        # 프롬프트 조합
        base_prompt = response.strip()
        quality_tags = ", ".join(self._image_template.get("quality_tags", []))

        if enhance:
            final_prompt = f"{style_prefix}, {base_prompt}, {quality_tags}"
        else:
            final_prompt = f"{style_prefix}, {base_prompt}"

        return final_prompt

    async def generate_video_prompt(
        self,
        scene: Scene,
        duration_hint: str = "medium"
    ) -> str:
        """
        영상 생성용 프롬프트 생성

        Args:
            scene: 장면 엔티티
            duration_hint: 영상 길이 힌트 (short/medium/long)

        Returns:
            영상 생성용 프롬프트
        """
        # 모델별 설정 가져오기
        model_config = self._video_template.get("model_specific", {}).get(
            self.model_type, {}
        )

        # LLM으로 모션 프롬프트 생성
        prompt_request = f"""Convert this scene description into a video generation prompt focused on MOTION.

Scene: {scene.description}
Duration: {duration_hint} ({self._get_duration_seconds(duration_hint)} seconds)

Requirements:
1. Describe how subjects MOVE
2. Describe camera motion (if any)
3. Describe environmental motion (wind, water, etc.)
4. Keep it concise and action-focused
5. Output ONLY the prompt, no explanations

Format: natural language describing motion"""

        response = await self.llm.generate(prompt_request)

        # 모델별 접미사 추가
        model_suffix = model_config.get("suffix", "")

        final_prompt = f"{response.strip()}, {model_suffix}"

        return final_prompt

    async def generate_all_prompts(
        self,
        story: Story,
        enhance_images: bool = True
    ) -> List[GeneratedPrompts]:
        """
        스토리의 모든 장면 프롬프트 생성

        Args:
            story: 스토리 엔티티
            enhance_images: 이미지 프롬프트 강화 여부

        Returns:
            각 장면의 프롬프트 결과 리스트
        """
        results = []

        for scene in story.scenes:
            # 이미지 프롬프트 생성
            image_prompt = await self.generate_image_prompt(
                scene,
                enhance=enhance_images
            )

            # 영상 프롬프트 생성
            video_prompt = await self.generate_video_prompt(scene)

            # 네거티브 프롬프트
            negative_prompt = self._get_negative_prompt()

            results.append(GeneratedPrompts(
                scene_id=scene.id,
                image_prompt=image_prompt,
                video_prompt=video_prompt,
                negative_prompt=negative_prompt,
                raw_description=scene.description
            ))

        return results

    def _get_style_name(self) -> str:
        """현재 스타일 이름 가져오기"""
        if self.style_preset and hasattr(self.style_preset, 'style'):
            return self.style_preset.style
        return "anime"

    def _get_negative_prompt(self) -> str:
        """스타일별 네거티브 프롬프트"""
        style_name = self._get_style_name()
        negatives = self._image_template.get("negative_prompt", {})
        return negatives.get(style_name, negatives.get("default", ""))

    def _get_duration_seconds(self, hint: str) -> int:
        """영상 길이 힌트를 초로 변환"""
        guidelines = self._video_template.get("duration_guidelines", {})
        return guidelines.get(hint, {}).get("seconds", 5)


class PromptEnhancer:
    """
    프롬프트 강화기

    기본 프롬프트에 추가 태그/품질 향상 요소 추가
    """

    @staticmethod
    def add_lighting(prompt: str, lighting: str) -> str:
        """조명 효과 추가"""
        lighting_tags = {
            "golden_hour": "golden hour lighting, warm sunset light",
            "blue_hour": "blue hour lighting, twilight",
            "studio": "studio lighting, soft box light",
            "dramatic": "dramatic lighting, high contrast",
            "soft": "soft lighting, diffused light",
            "backlight": "backlight, rim lighting, silhouette"
        }
        tag = lighting_tags.get(lighting, "")
        return f"{prompt}, {tag}" if tag else prompt

    @staticmethod
    def add_camera_angle(prompt: str, angle: str) -> str:
        """카메라 앵글 추가"""
        angle_tags = {
            "low": "low angle shot, looking up",
            "high": "high angle shot, looking down",
            "eye_level": "eye level shot",
            "birds_eye": "bird's eye view, overhead shot",
            "dutch": "dutch angle, tilted frame"
        }
        tag = angle_tags.get(angle, "")
        return f"{prompt}, {tag}" if tag else prompt

    @staticmethod
    def add_atmosphere(prompt: str, atmosphere: str) -> str:
        """분위기 추가"""
        atmosphere_tags = {
            "misty": "misty, foggy, atmospheric",
            "rainy": "rainy, wet, droplets",
            "sunny": "bright sunny day, clear sky",
            "cloudy": "overcast, cloudy sky",
            "night": "night time, dark, stars"
        }
        tag = atmosphere_tags.get(atmosphere, "")
        return f"{prompt}, {tag}" if tag else prompt
