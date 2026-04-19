"""
Character Entity - 캐릭터 정보 저장

시리즈 전체에서 일관된 캐릭터 유지를 위한 엔티티
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid


class CharacterType(str, Enum):
    """캐릭터 타입"""
    PROTAGONIST = "protagonist"      # 주인공 (시리즈 전체)
    SUPPORTING = "supporting"         # 조연 (반복 등장)
    ANIMAL = "animal"                 # 동물 캐릭터
    NPC = "npc"                       # 배경 인물 (일회용)
    CREATURE = "creature"             # 판타지 생물


class CharacterRole(str, Enum):
    """캐릭터 역할"""
    HERO = "hero"                     # 영웅/주인공
    VILLAIN = "villain"               # 악당
    SIDEKICK = "sidekick"             # 조력자
    MENTOR = "mentor"                 # 스승
    LOVE_INTEREST = "love_interest"   # 연인
    COMIC_RELIEF = "comic_relief"     # 개그 캐릭터
    BACKGROUND = "background"         # 배경


class CharacterGender(str, Enum):
    """성별"""
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    ANIMAL = "animal"
    UNKNOWN = "unknown"


@dataclass
class CharacterAppearance:
    """캐릭터 외형 정보 (간단 버전)"""
    age: str = ""
    gender: str = ""
    body_type: str = ""
    hair: str = ""
    skin: str = ""
    clothing: str = ""
    accessories: str = ""


class Character(BaseModel):
    """
    캐릭터 엔티티

    캐릭터의 외형, 성격, 스타일 정보를 저장하여
    시리즈 전체에서 일관된 캐릭터 표현 유지
    """

    # 기본 정보
    id: str = Field(default_factory=lambda: f"char_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., min_length=1, max_length=50)
    type: CharacterType = Field(default=CharacterType.SUPPORTING)
    role: CharacterRole = Field(default=CharacterRole.BACKGROUND)
    gender: CharacterGender = Field(default=CharacterGender.UNKNOWN)

    # 설명
    description: str = Field(default="", max_length=1000)
    personality: List[str] = Field(default_factory=list)
    traits: List[str] = Field(default_factory=list)  # 특징 (안경, 머리스타일 등)

    # ============================================================
    # 🎨 외형 프롬프트 (Disney 3D 스타일)
    # ============================================================

    # 기본 외형
    appearance_prompt: str = Field(
        default="",
        description="기본 외형 프롬프트"
    )

    # 얼굴 특징
    face_description: str = Field(
        default="",
        description="얼굴 상세 설명 (눈, 코, 입, 턱선 등)"
    )

    # 헤어스타일
    hair_description: str = Field(
        default="",
        description="머리 스타일 (색, 길이, 스타일)"
    )

    # 체형
    body_description: str = Field(
        default="",
        description="체형 (키, 체격, 나이대)"
    )

    # 피부색
    skin_tone: str = Field(
        default="fair skin",
        description="피부색"
    )

    # 눈 색깔
    eye_color: str = Field(
        default="",
        description="눈 색깔"
    )

    # ============================================================
    # 👗 의상
    # ============================================================

    # 기본 의상
    default_outfit: str = Field(
        default="",
        description="기본 의상"
    )

    # 의상 변형 (상황별)
    outfit_variants: Dict[str, str] = Field(
        default_factory=dict,
        description="상황별 의상 (casual, formal, sleep, battle 등)"
    )

    # 액세서리
    accessories: List[str] = Field(
        default_factory=list,
        description="액세서리 (안경, 목걸이 등)"
    )

    # ============================================================
    # 🎭 표정/포즈
    # ============================================================

    # 기본 표정
    default_expression: str = Field(
        default="gentle smile",
        description="기본 표정"
    )

    # 표정 변형
    expressions: Dict[str, str] = Field(
        default_factory=lambda: {
            "happy": "bright smile, joyful eyes",
            "sad": "tearful eyes, frown",
            "angry": "furrowed brows, determined look",
            "surprised": "wide eyes, open mouth",
            "scared": "worried expression, trembling",
            "neutral": "calm expression"
        }
    )

    # 포즈
    poses: Dict[str, str] = Field(
        default_factory=lambda: {
            "standing": "standing naturally",
            "sitting": "sitting comfortably",
            "walking": "walking naturally",
            "running": "running dynamically",
            "action": "dynamic action pose"
        }
    )

    # ============================================================
    # 🖼️ 참조 이미지
    # ============================================================

    # 기준 이미지 (IP-Adapter용)
    reference_image_path: Optional[str] = Field(
        default=None,
        description="캐릭터 기준 이미지 경로"
    )

    # 추가 참조 이미지
    reference_images: Dict[str, str] = Field(
        default_factory=dict,
        description="상황별 참조 이미지 (front, side, back, expression 등)"
    )

    # ============================================================
    # 🎬 애니메이션 설정
    # ============================================================

    # 움직임 스타일
    motion_style: str = Field(
        default="graceful",
        description="움직임 스타일 (graceful, energetic, clumsy 등)"
    )

    # 목소리 톤 (TTS용)
    voice_description: str = Field(
        default="",
        description="목소리 설명 (TTS 설정용)"
    )

    # TTS 설정
    tts_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="TTS 상세 설정 (voice_id, speed, pitch 등)"
    )

    # ============================================================
    # 메타데이터
    # ============================================================

    # 태그
    tags: List[str] = Field(default_factory=list)

    # 등장 에피소드
    episodes: List[str] = Field(
        default_factory=list,
        description="등장한 에피소드 ID 목록"
    )

    # 생성/수정 시간
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 비고
    notes: str = Field(default="")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "char_abc123",
                "name": "엘라",
                "type": "protagonist",
                "role": "hero",
                "gender": "female",
                "description": "마법의 힘을 가진 공주",
                "appearance_prompt": "young princess with long platinum blonde hair, blue eyes, elegant features, Disney style",
                "face_description": "large expressive blue eyes, small nose, gentle smile, heart-shaped face",
                "hair_description": "long flowing platinum blonde hair, side braid",
                "default_outfit": "ice blue ball gown with snowflake patterns",
                "reference_image_path": "characters/ella/reference.png"
            }
        }

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now()

    def get_full_prompt(
        self,
        expression: str = "default",
        pose: str = "standing",
        outfit: str = "default",
        include_disney_style: bool = True
    ) -> str:
        """
        전체 캐릭터 프롬프트 생성

        Args:
            expression: 표정 키
            pose: 포즈 키
            outfit: 의상 키
            include_disney_style: Disney 스타일 접두사 포함 여부

        Returns:
            완성된 프롬프트
        """
        parts = []

        # Disney 3D 스타일 접두사
        if include_disney_style:
            parts.append("Disney 3D animation style, Pixar quality")
            parts.append("smooth cel shading, beautiful lighting")

        # 기본 외형
        if self.appearance_prompt:
            parts.append(self.appearance_prompt)

        # 얼굴
        if self.face_description:
            parts.append(self.face_description)

        # 머리
        if self.hair_description:
            parts.append(self.hair_description)

        # 체형
        if self.body_description:
            parts.append(self.body_description)

        # 의상
        if outfit == "default":
            if self.default_outfit:
                parts.append(f"wearing {self.default_outfit}")
        elif outfit in self.outfit_variants:
            parts.append(f"wearing {self.outfit_variants[outfit]}")

        # 액세서리
        if self.accessories:
            parts.append(", ".join(self.accessories))

        # 표정
        expr = self.expressions.get(expression, self.default_expression)
        if expr:
            parts.append(expr)

        # 포즈
        pose_desc = self.poses.get(pose, "")
        if pose_desc:
            parts.append(pose_desc)

        return ", ".join(parts)

    def get_negative_prompt(self) -> str:
        """네거티브 프롬프트"""
        negatives = [
            "realistic photo",
            "live action",
            "western cartoon",
            "rough lines",
            "low quality",
            "blurry",
            "bad anatomy"
        ]

        # 캐릭터 타입별 추가
        if self.type == CharacterType.ANIMAL:
            negatives.extend(["human", "person", "man", "woman"])
        else:
            negatives.append("animal")

        return ", ".join(negatives)

    def add_episode(self, episode_id: str) -> None:
        """에피소드 추가"""
        if episode_id not in self.episodes:
            self.episodes.append(episode_id)
            self.update_timestamp()

    def to_prompt_dict(self) -> Dict[str, str]:
        """프롬프트용 딕셔너리 변환"""
        return {
            "name": self.name,
            "type": self.type.value,
            "appearance": self.appearance_prompt,
            "face": self.face_description,
            "hair": self.hair_description,
            "body": self.body_description,
            "outfit": self.default_outfit,
            "full_prompt": self.get_full_prompt(),
            "negative": self.get_negative_prompt()
        }


# ============================================================
# 편의 함수
# ============================================================

def create_protagonist(
    name: str,
    gender: CharacterGender,
    appearance: str,
    personality: List[str] = None,
    **kwargs
) -> Character:
    """주인공 생성 헬퍼"""
    return Character(
        name=name,
        type=CharacterType.PROTAGONIST,
        gender=gender,
        appearance_prompt=appearance,
        personality=personality or [],
        **kwargs
    )


def create_animal_character(
    name: str,
    species: str,
    appearance: str,
    **kwargs
) -> Character:
    """동물 캐릭터 생성 헬퍼"""
    return Character(
        name=name,
        type=CharacterType.ANIMAL,
        gender=CharacterGender.ANIMAL,
        appearance_prompt=f"{species}, {appearance}",
        description=f"A {species} character named {name}",
        **kwargs
    )
