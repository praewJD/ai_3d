"""
StorySpec Entity - 스토리 명세 데이터 구조

스토리의 구조화된 명세를 표현하는 데이터 클래스들
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import json


# ============================================================
# 상수 정의
# ============================================================

SHORTS_CONSTRAINTS = {
    "min_duration": 20,
    "max_duration": 35,
    "min_scenes": 6,
    "max_scenes": 10,
    "scene_duration_range": (2, 4)
}

LONGFORM_CONSTRAINTS = {
    "min_duration": 120,
    "max_duration": 480,
    "min_scenes": 20,
    "max_scenes": 60
}

SHORT_DRAMA_CONSTRAINTS = {
    "min_duration": 45,          # 최소 45초 (고정)
    "max_duration": None,         # 최대 무제한 (스토리에 따라)
    "min_scenes": 5,              # 최소 5개 (5단계 구조)
    "max_scenes": None,           # 최대 무제한
    "scene_duration_range": (3, 15),
}


# ============================================================
# Enum 정의
# ============================================================

class TargetFormat(str, Enum):
    """타겟 포맷"""
    SHORTS = "shorts"
    LONGFORM = "longform"
    SHORT_DRAMA = "short_drama"


class ScenePurpose(str, Enum):
    """장면 목적"""
    HOOK = "hook"
    BUILD = "build"
    CLIMAX = "climax"
    RESOLUTION = "resolution"


# ============================================================
# Dataclass 정의
# ============================================================

@dataclass
class CharacterSpec:
    """캐릭터 명세"""
    id: str
    name: str
    appearance: str = ""
    traits: List[str] = field(default_factory=list)
    seed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterSpec":
        return cls(**data)


@dataclass
class ArcSpec:
    """스토리 아크 명세"""
    hook: str = ""
    build: str = ""
    climax: str = ""
    resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArcSpec":
        return cls(**data)


@dataclass
class SceneSpec:
    """장면 명세"""
    id: str
    purpose: ScenePurpose = ScenePurpose.BUILD
    camera: str = "medium_shot"
    mood: str = "neutral"
    action: str = ""
    characters: List[str] = field(default_factory=list)
    location: str = ""
    dialogue: str = ""
    narration: str = ""
    duration: float = 3.0
    emotion: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["purpose"] = self.purpose.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneSpec":
        if isinstance(data.get("purpose"), str):
            data["purpose"] = ScenePurpose(data["purpose"])
        return cls(**data)


@dataclass
class StorySpec:
    """스토리 명세"""
    title: str = ""
    genre: str = ""
    target: TargetFormat = TargetFormat.SHORTS
    duration: float = 30.0
    characters: List[CharacterSpec] = field(default_factory=list)
    arc: ArcSpec = field(default_factory=ArcSpec)
    scenes: List[SceneSpec] = field(default_factory=list)
    emotion_curve: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화)"""
        return {
            "title": self.title,
            "genre": self.genre,
            "target": self.target.value,
            "duration": self.duration,
            "characters": [c.to_dict() for c in self.characters],
            "arc": self.arc.to_dict(),
            "scenes": [s.to_dict() for s in self.scenes],
            "emotion_curve": self.emotion_curve,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorySpec":
        """딕셔너리에서 생성 (JSON 역직렬화)"""
        # Enum 변환
        if isinstance(data.get("target"), str):
            data["target"] = TargetFormat(data["target"])

        # CharacterSpec 변환
        characters = [
            CharacterSpec.from_dict(c) if isinstance(c, dict) else c
            for c in data.pop("characters", [])
        ]

        # ArcSpec 변환
        if "arc" in data and isinstance(data["arc"], dict):
            data["arc"] = ArcSpec.from_dict(data["arc"])

        # SceneSpec 변환
        scenes = [
            SceneSpec.from_dict(s) if isinstance(s, dict) else s
            for s in data.pop("scenes", [])
        ]

        return cls(characters=characters, scenes=scenes, **data)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        기본 검증

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # 타이틀 검증
        if not self.title or not self.title.strip():
            errors.append("Title is required")

        # 타겟 포맷에 따른 제약 검증
        if self.target == TargetFormat.SHORTS:
            constraints = SHORTS_CONSTRAINTS
        elif self.target == TargetFormat.SHORT_DRAMA:
            constraints = SHORT_DRAMA_CONSTRAINTS
        else:
            constraints = LONGFORM_CONSTRAINTS

        # 길이 검증
        if self.duration < constraints["min_duration"]:
            errors.append(
                f"Duration {self.duration}s is below minimum {constraints['min_duration']}s"
            )
        if constraints["max_duration"] is not None and self.duration > constraints["max_duration"]:
            errors.append(
                f"Duration {self.duration}s exceeds maximum {constraints['max_duration']}s"
            )

        # 장면 수 검증
        scene_count = len(self.scenes)
        if scene_count < constraints["min_scenes"]:
            errors.append(
                f"Scene count {scene_count} is below minimum {constraints['min_scenes']}"
            )
        if constraints["max_scenes"] is not None and scene_count > constraints["max_scenes"]:
            errors.append(
                f"Scene count {scene_count} exceeds maximum {constraints['max_scenes']}"
            )

        # 장면 ID 중복 검증
        scene_ids = [s.id for s in self.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            errors.append("Duplicate scene IDs found")

        # 캐릭터 ID 중복 검증
        character_ids = [c.id for c in self.characters]
        if len(character_ids) != len(set(character_ids)):
            errors.append("Duplicate character IDs found")

        # 장면에서 참조하는 캐릭터가 정의되어 있는지 검증
        defined_character_ids = set(c.id for c in self.characters)
        for scene in self.scenes:
            for char_id in scene.characters:
                if char_id not in defined_character_ids:
                    errors.append(
                        f"Scene '{scene.id}' references undefined character '{char_id}'"
                    )

        return len(errors) == 0, errors

    def total_duration(self) -> float:
        """총 길이 계산 (장면들의 duration 합계)"""
        return sum(s.duration for s in self.scenes)

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "StorySpec":
        """JSON 문자열에서 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_constraints(self) -> Dict[str, Any]:
        """현재 타겟 포맷에 대한 제약 조건 반환"""
        if self.target == TargetFormat.SHORTS:
            return SHORTS_CONSTRAINTS
        elif self.target == TargetFormat.SHORT_DRAMA:
            return SHORT_DRAMA_CONSTRAINTS
        return LONGFORM_CONSTRAINTS
