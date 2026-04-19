# -*- coding: utf-8 -*-
"""
Prompt Builder - 통합 프롬프트 빌더

캐릭터 + 장소 + 액션을 조합하여 완전한 프롬프트 생성
"""
from typing import Optional
from dataclasses import dataclass

from core.domain.entities.character import Character
from infrastructure.script_parser.scene_parser import ParsedScene
from infrastructure.prompt.character_template import CharacterTemplate, PoseType
from infrastructure.prompt.location_db import LocationDB


@dataclass
class ScenePrompt:
    """장면 프롬프트 결과"""
    positive: str
    negative: str
    characters: list[str]
    location: str
    metadata: dict


class PromptBuilder:
    """
    통합 프롬프트 빌더

    캐릭터 템플릿 + 장소 DB를 조합하여 장면 프롬프트 생성
    """

    # 액션 → 포즈 매핑
    ACTION_POSE_MAP = {
        "standing": PoseType.STANDING,
        "sitting": PoseType.SITTING,
        "walking": PoseType.WALKING,
        "running": PoseType.RUNNING,
        "fighting": PoseType.FIGHTING,
        "flying": PoseType.FLYING,
        "dramatic": PoseType.DRAMATIC,
        "calm": PoseType.CALM,
    }

    # 액션 키워드 감지
    ACTION_KEYWORDS = {
        "fighting": ["fight", "combat", "punch", "kick", "attack", "battle", "สู้", "싸우", "戦"],
        "running": ["run", "chase", "sprint", "flee", "วิ่ง", "달리", "走"],
        "walking": ["walk", "stroll", "approach", "เดิน", "걷", "歩"],
        "flying": ["fly", "float", "hover", "soar", "บิน", "날", "飛"],
        "dramatic": ["dramatic", "intense", "epic", "confrontation"],
        "calm": ["calm", "peaceful", "relaxed", "quiet", "สงบ", "차분"],
    }

    # 스타일 프리셋
    STYLE_PRESETS = {
        "cinematic": {
            "base": "cinematic composition, film grain, anamorphic lens",
            "quality": ["8k", "professional photography", "color graded"],
        },
        "anime": {
            "base": "anime style, cel shaded, vibrant colors",
            "quality": ["high quality", "detailed", "studio animation"],
        },
        "realistic": {
            "base": "photorealistic, hyperrealistic, photography",
            "quality": ["8k", "RAW photo", "professional lighting"],
        },
        "cyberpunk": {
            "base": "cyberpunk aesthetic, neon noir, high tech low life",
            "quality": ["8k", "dramatic lighting", "cinematic"],
        },
        "dramatic": {
            "base": "dramatic lighting, high contrast, noir style",
            "quality": ["8k", "moody", "atmospheric"],
        },
    }

    def __init__(
        self,
        character_template: CharacterTemplate = None,
        location_db: LocationDB = None,
        style: str = "cinematic",
    ):
        self.character_template = character_template or CharacterTemplate()
        self.location_db = location_db or LocationDB()
        self.style = style

    def build_scene_prompt(
        self,
        characters: list[Character],
        scene: ParsedScene,
        style: Optional[str] = None,
    ) -> ScenePrompt:
        """
        장면 전체 프롬프트 생성

        Args:
            characters: 장면에 등장하는 캐릭터들
            scene: 파싱된 장면 정보
            style: 스타일 프리셋

        Returns:
            ScenePrompt: 완성된 프롬프트
        """
        style = style or self.style
        style_preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["cinematic"])

        parts = []

        # 1. 캐릭터 프롬프트
        char_prompts = []
        for char in characters[:3]:  # 최대 3명
            pose = self._detect_pose(scene.action)
            char_prompt = self.character_template.build_prompt(
                char,
                pose=pose,
                action=scene.action,
                include_quality=False,
            )
            char_prompts.append(char_prompt)

        if char_prompts:
            parts.append(', '.join(char_prompts))

        # 2. 장소 프롬프트
        location_prompt = self.location_db.build_location_prompt(
            city=self._detect_city(scene.location),
            place_type=scene.location,
            time=scene.time_of_day,
            camera_angle=self._map_camera_angle(scene.camera_angle),
        )
        if location_prompt:
            parts.append(location_prompt)

        # 3. 분위기/무드
        if scene.mood:
            parts.append(scene.mood)

        # 4. 스타일
        parts.append(style_preset["base"])

        # 5. 품질 태그
        parts.extend(style_preset["quality"])

        # Positive 프롬프트 완성
        positive = ', '.join(parts)

        # Negative 프롬프트
        negatives = ["blurry", "low quality", "watermark", "text", "oversaturated"]

        # 캐릭터별 negative 추가
        for char in characters[:3]:
            char_neg = self.character_template.build_negative(char)
            negatives.append(char_neg)

        # 장소 negative 추가
        loc_neg = self.location_db.build_negative_prompt(
            city=self._detect_city(scene.location),
            place_type=scene.location,
        )
        if loc_neg:
            negatives.append(loc_neg)

        negative = ', '.join(dict.fromkeys(negatives))  # 중복 제거

        return ScenePrompt(
            positive=positive,
            negative=negative,
            characters=[c.name for c in characters],
            location=scene.location,
            metadata={
                "style": style,
                "time_of_day": scene.time_of_day,
                "camera_angle": scene.camera_angle,
            },
        )

    def build_character_prompt(
        self,
        character: Character,
        pose: str = "standing",
        action: Optional[str] = None,
        style: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        단일 캐릭터 프롬프트 생성

        Args:
            character: 캐릭터
            pose: 포즈 문자열
            action: 액션 설명
            style: 스타일

        Returns:
            (positive, negative)
        """
        style = style or self.style
        style_preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["cinematic"])

        pose_type = self.ACTION_POSE_MAP.get(pose.lower(), PoseType.STANDING)

        positive = self.character_template.build_prompt(
            character,
            pose=pose_type,
            action=action,
            include_quality=False,
        )
        positive += f", {style_preset['base']}"
        positive += ', ' + ', '.join(style_preset['quality'])

        negative = self.character_template.build_negative(character)

        return positive, negative

    def build_reference_prompt(
        self,
        character: Character,
    ) -> tuple[str, str]:
        """
        IP-Adapter 기준 이미지용 프롬프트

        깔끔한 정면 샷, 배경 단순화
        """
        positive = self.character_template.build_reference_prompt(character)

        negative = self.character_template.build_negative(character)
        negative += ", complex background, multiple people, action pose"

        return positive, negative

    def _detect_pose(self, action: str) -> PoseType:
        """액션에서 포즈 감지"""
        if not action:
            return PoseType.STANDING

        action_lower = action.lower()

        for pose_type, keywords in self.ACTION_KEYWORDS.items():
            if any(kw in action_lower for kw in keywords):
                return self.ACTION_POSE_MAP.get(pose_type, PoseType.ACTION)

        return PoseType.STANDING

    def _detect_city(self, location: str) -> Optional[str]:
        """위치에서 도시 감지"""
        if not location:
            return None

        location_lower = location.lower()

        city_keywords = {
            "bangkok": ["bangkok", "กรุงเทพ", "방콕"],
            "seoul": ["seoul", "서울"],
            "tokyo": ["tokyo", "도쿄", "東京"],
        }

        for city, keywords in city_keywords.items():
            if any(kw in location_lower for kw in keywords):
                return city

        return None

    def _map_camera_angle(self, angle: Optional[str]) -> str:
        """카메라 앵글 매핑"""
        if not angle:
            return "wide"

        angle_map = {
            "low_angle": "low_angle",
            "high_angle": "high_angle",
            "wide": "wide",
            "close_up": "close_up",
            "medium": "medium",
        }

        return angle_map.get(angle.lower(), "wide")
