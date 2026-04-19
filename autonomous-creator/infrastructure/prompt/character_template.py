# -*- coding: utf-8 -*-
"""
Character Template - 캐릭터 프롬프트 템플릿

일관된 캐릭터 프롬프트 생성을 위한 템플릿 시스템
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from core.domain.entities.character import Character, CharacterType


class PoseType(Enum):
    """포즈 타입"""
    STANDING = "standing"
    SITTING = "sitting"
    WALKING = "walking"
    RUNNING = "running"
    FIGHTING = "fighting"
    FLYING = "flying"
    ACTION = "action"
    DRAMATIC = "dramatic"
    CALM = "calm"


@dataclass
class StyleSettings:
    """스타일 설정"""
    base_style: str = "cinematic"
    quality_tags: list[str] = None
    negative_base: list[str] = None

    def __post_init__(self):
        if self.quality_tags is None:
            self.quality_tags = ["8k", "high detail", "professional"]
        if self.negative_base is None:
            self.negative_base = ["blurry", "low quality", "watermark", "text"]


class CharacterTemplate:
    """
    캐릭터 프롬프트 템플릿

    캐릭터 엔티티를 SD 3.5 프롬프트로 변환
    """

    # 기본 템플릿
    BASE_TEMPLATE = """
{gender} {age}, {body_type} build,
{hair_description},
wearing {clothing},
{accessories},
{distinctive_features},
{power_effects}
""".strip()

    # 포즈 템플릿
    POSE_TEMPLATES = {
        PoseType.STANDING: "standing upright, confident posture, full body visible",
        PoseType.SITTING: "sitting on {surface}, relaxed pose",
        PoseType.WALKING: "walking forward, mid-stride, dynamic",
        PoseType.RUNNING: "running, action pose, motion blur",
        PoseType.FIGHTING: "combat stance, ready to strike, dynamic action pose",
        PoseType.FLYING: "floating in air, {power_effect}, superhero pose",
        PoseType.ACTION: "{action_description}, dynamic pose, motion",
        PoseType.DRAMATIC: "dramatic pose, intense expression, cinematic framing",
        PoseType.CALM: "calm pose, peaceful expression, relaxed stance",
    }

    # 타입별 추가 태그
    TYPE_TAGS = {
        CharacterType.PROTAGONIST: ["heroic", "determined", "noble"],
        CharacterType.SUPPORTING: ["friendly", "approachable"],
        CharacterType.ANIMAL: ["animal companion", "cute"],
        CharacterType.NPC: ["background character"],
        CharacterType.CREATURE: ["mystical creature", "fantasy being"],
    }

    # 성별 매핑
    GENDER_MAP = {
        "male": "male",
        "female": "female",
        "unknown": "person",
    }

    # 나이 매핑
    AGE_MAP = {
        "child": "child",
        "young adult": "young adult",
        "adult": "adult",
        "middle_aged": "middle-aged",
        "elderly": "elderly",
    }

    # 체형 매핑
    BODY_MAP = {
        "slim": "slim",
        "average": "average",
        "athletic": "athletic",
        "muscular": "muscular",
        "heavy": "heavy",
    }

    def __init__(self, style: StyleSettings = None):
        self.style = style or StyleSettings()

    def build_prompt(
        self,
        character: Character,
        pose: PoseType = PoseType.STANDING,
        action: Optional[str] = None,
        include_quality: bool = True,
    ) -> str:
        """
        캐릭터 프롬프트 생성

        Args:
            character: 캐릭터 엔티티
            pose: 포즈 타입
            action: 액션 설명 (PoseType.ACTION인 경우)
            include_quality: 품질 태그 포함 여부

        Returns:
            완성된 프롬프트
        """
        parts = []

        # 1. 기본 외형
        base_prompt = self._build_base_prompt(character)
        parts.append(base_prompt)

        # 2. 포즈
        pose_prompt = self._build_pose_prompt(pose, action, character)
        parts.append(pose_prompt)

        # 3. 타입 태그
        type_tags = self.TYPE_TAGS.get(character.type, [])
        if type_tags:
            parts.append(', '.join(type_tags))

        # 4. 스타일
        parts.append(self.style.base_style)

        # 5. 품질 태그
        if include_quality:
            parts.extend(self.style.quality_tags)

        return ', '.join(parts)

    def _build_base_prompt(self, character: Character) -> str:
        """기본 외형 프롬프트"""
        app = character.appearance

        # 성별
        gender = self.GENDER_MAP.get(app.gender, "person")

        # 나이
        age = self.AGE_MAP.get(app.age, "adult")

        # 체형
        body = self.BODY_MAP.get(app.body_type, "average")

        # 머리
        hair = app.hair if app.hair else "natural hair"

        # 의상
        clothing = ', '.join(app.clothing) if app.clothing else "casual clothes"

        # 액세서리
        accessories = ', '.join(app.accessories) if app.accessories else "no accessories"

        # 특징
        features = ', '.join(app.distinctive_features) if app.distinctive_features else ""

        # 능력 효과
        power_effects = character._powers_to_visual()

        # 템플릿 적용
        prompt = self.BASE_TEMPLATE.format(
            gender=gender,
            age=age,
            body_type=body,
            hair_description=hair,
            clothing=clothing,
            accessories=accessories,
            distinctive_features=features,
            power_effects=power_effects,
        )

        return prompt

    def _build_pose_prompt(
        self,
        pose: PoseType,
        action: Optional[str],
        character: Character
    ) -> str:
        """포즈 프롬프트"""
        template = self.POSE_TEMPLATES.get(pose, self.POSE_TEMPLATES[PoseType.STANDING])

        # 변수 치환
        power_effect = character._powers_to_visual() or "energy glow"

        result = template.format(
            surface="ground",
            action_description=action or "moving",
            power_effect=power_effect,
        )

        return result

    def build_negative(self, character: Character) -> str:
        """
        Negative 프롬프트 생성

        Args:
            character: 캐릭터 엔티티

        Returns:
            Negative 프롬프트
        """
        negatives = list(self.style.negative_base)

        # 캐릭터 타입에 따른 추가 negative
        if character.type == CharacterType.HERO:
            negatives.extend(["villain", "evil", "dark", "menacing"])
        elif character.type == CharacterType.VILLAIN:
            negatives.extend(["hero", "friendly", "bright colors", "heroic"])

        # 성별 반대 제외
        if character.appearance.gender == "male":
            negatives.append("female")
        elif character.appearance.gender == "female":
            negatives.append("male")

        return ', '.join(negatives)

    def build_reference_prompt(self, character: Character) -> str:
        """
        기준 이미지용 프롬프트

        IP-Adapter 기준 이미지는 깔끔한 정면 샷이 좋음
        """
        parts = []

        # 기본 외형
        base = self._build_base_prompt(character)
        parts.append(base)

        # 기준 이미지용 포즈
        parts.append("standing straight, facing camera, front view")
        parts.append("neutral expression, simple background")
        parts.append("full body visible, clear details")

        # 스타일
        parts.append("reference sheet style")
        parts.extend(self.style.quality_tags)

        return ', '.join(parts)
