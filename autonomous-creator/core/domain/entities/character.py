# -*- coding: utf-8 -*-
"""
Character Entity - 캐릭터 정보 구조화

스크립트에서 추출된 캐릭터 정보를 담는 엔티티
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from pathlib import Path
import json
import hashlib


class CharacterType(Enum):
    """캐릭터 타입"""
    HERO = "hero"
    VILLAIN = "villain"
    SUPPORTING = "supporting"
    EXTRA = "extra"


@dataclass
class CharacterAppearance:
    """캐릭터 외형"""
    age: str = "adult"
    gender: str = "unknown"
    body_type: str = "average"
    hair: str = ""
    clothing: list[str] = field(default_factory=list)
    accessories: list[str] = field(default_factory=list)
    distinctive_features: list[str] = field(default_factory=list)

    def to_prompt_segment(self) -> str:
        """프롬프트용 문자열 변환"""
        parts = []

        if self.gender != "unknown":
            parts.append(self.gender)
        parts.append(self.age)
        if self.body_type != "average":
            parts.append(f"{self.body_type} build")

        if self.hair:
            parts.append(self.hair)

        if self.clothing:
            parts.append(f"wearing {', '.join(self.clothing)}")

        if self.accessories:
            parts.append(', '.join(self.accessories))

        if self.distinctive_features:
            parts.append(', '.join(self.distinctive_features))

        return ', '.join(parts)


@dataclass
class Character:
    """
    캐릭터 엔티티

    스크립트에서 추출된 캐릭터 정보를 담는 메인 데이터 구조
    """
    name: str
    name_local: Optional[str] = None
    type: CharacterType = CharacterType.SUPPORTING
    appearance: CharacterAppearance = field(default_factory=CharacterAppearance)
    personality: list[str] = field(default_factory=list)
    powers: list[str] = field(default_factory=list)

    # IP-Adapter용
    reference_image_path: Optional[str] = None
    embedding_cache_path: Optional[str] = None

    # 메타데이터
    source_language: str = "unknown"

    def __post_init__(self):
        """초기화 후 처리"""
        # ID 자동 생성
        if not hasattr(self, '_id') or not self._id:
            self._id = self._generate_id()

    @property
    def id(self) -> str:
        """캐릭터 고유 ID"""
        return self._id

    def _generate_id(self) -> str:
        """이름 기반 고유 ID 생성"""
        base = f"{self.name}_{self.type.value}"
        return hashlib.md5(base.encode()).hexdigest()[:12]

    def to_prompt_segment(self, include_type: bool = True) -> str:
        """
        프롬프트용 문자열 변환

        Args:
            include_type: 캐릭터 타입 포함 여부

        Returns:
            프롬프트용 문자열
        """
        parts = []

        # 외형
        appearance_str = self.appearance.to_prompt_segment()
        if appearance_str:
            parts.append(appearance_str)

        # 능력 (시각적으로 표현 가능한 것만)
        if self.powers:
            power_effects = self._powers_to_visual()
            if power_effects:
                parts.append(power_effects)

        return ', '.join(parts)

    def _powers_to_visual(self) -> str:
        """능력을 시각적 효과로 변환"""
        power_effects = {
            "sound wave control": "glowing blue sound waves emanating",
            "sound sensing": "eyes glowing blue",
            "fire control": "flames surrounding hands",
            "ice control": "frost emanating from body",
            "super strength": "muscular stance",
            "flight": "floating in air",
            "teleportation": "swirling energy around body",
            "mind control": "purple energy waves from head",
            "electricity": "lightning crackling around body",
            "darkness": "dark shadows emanating",
        }

        effects = []
        for power in self.powers:
            power_lower = power.lower()
            for key, effect in power_effects.items():
                if key in power_lower:
                    effects.append(effect)
                    break

        return ', '.join(effects) if effects else ""

    def get_negative_prompt(self) -> str:
        """캐릭터 타입에 따른 negative 프롬프트"""
        base_negatives = ["blurry", "low quality", "watermark", "text"]

        if self.type == CharacterType.HERO:
            base_negatives.extend(["villain", "evil", "dark", "menacing"])
        elif self.type == CharacterType.VILLAIN:
            base_negatives.extend(["hero", "friendly", "bright colors"])

        # 성별 반대 제외
        if self.appearance.gender == "male":
            base_negatives.append("female")
        elif self.appearance.gender == "female":
            base_negatives.append("male")

        return ', '.join(base_negatives)

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "name_local": self.name_local,
            "type": self.type.value,
            "appearance": {
                "age": self.appearance.age,
                "gender": self.appearance.gender,
                "body_type": self.appearance.body_type,
                "hair": self.appearance.hair,
                "clothing": self.appearance.clothing,
                "accessories": self.appearance.accessories,
                "distinctive_features": self.appearance.distinctive_features,
            },
            "personality": self.personality,
            "powers": self.powers,
            "reference_image_path": self.reference_image_path,
            "source_language": self.source_language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """딕셔너리에서 생성"""
        appearance_data = data.get("appearance", {})
        appearance = CharacterAppearance(
            age=appearance_data.get("age", "adult"),
            gender=appearance_data.get("gender", "unknown"),
            body_type=appearance_data.get("body_type", "average"),
            hair=appearance_data.get("hair", ""),
            clothing=appearance_data.get("clothing", []),
            accessories=appearance_data.get("accessories", []),
            distinctive_features=appearance_data.get("distinctive_features", []),
        )

        char = cls(
            name=data["name"],
            name_local=data.get("name_local"),
            type=CharacterType(data.get("type", "supporting")),
            appearance=appearance,
            personality=data.get("personality", []),
            powers=data.get("powers", []),
            reference_image_path=data.get("reference_image_path"),
            source_language=data.get("source_language", "unknown"),
        )

        # 기존 ID 복원
        if "id" in data:
            char._id = data["id"]

        return char

    def save(self, path: str) -> None:
        """JSON으로 저장"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "Character":
        """JSON에서 로드"""
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# 캐릭터 팩토리 함수들
def create_hero(name: str, name_local: str = None, **kwargs) -> Character:
    """히어로 캐릭터 생성 헬퍼"""
    return Character(
        name=name,
        name_local=name_local,
        type=CharacterType.HERO,
        **kwargs
    )


def create_villain(name: str, name_local: str = None, **kwargs) -> Character:
    """빌런 캐릭터 생성 헬퍼"""
    return Character(
        name=name,
        name_local=name_local,
        type=CharacterType.VILLAIN,
        **kwargs
    )
