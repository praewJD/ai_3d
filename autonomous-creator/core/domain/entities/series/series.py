"""
Series Entity - 시리즈 정보 관리

하나의 스토리 시리즈 (여러 에피소드로 구성)
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class SeriesStatus(str, Enum):
    """시리즈 상태"""
    DRAFT = "draft"           # 기획 중
    PRODUCTION = "production"  # 제작 중
    COMPLETED = "completed"    # 완료
    PAUSED = "paused"          # 일시중지


class SeriesGenre(str, Enum):
    """장르"""
    FANTASY = "fantasy"
    ROMANCE = "romance"
    ADVENTURE = "adventure"
    COMEDY = "comedy"
    DRAMA = "drama"
    ACTION = "action"
    THRILLER = "thriller"
    HORROR = "horror"
    SCIFI = "scifi"
    SLICE_OF_LIFE = "slice_of_life"
    FAIRY_TALE = "fairy_tale"


class SeriesTarget(str, Enum):
    """타겟 시청층"""
    CHILDREN = "children"         # 어린이
    FAMILY = "family"             # 가족
    TEEN = "teen"                 # 청소년
    YOUNG_ADULT = "young_adult"   # 청년
    ADULT = "adult"               # 성인


class Series(BaseModel):
    """
    시리즈 엔티티

    여러 에피소드로 구성된 스토리 시리즈
    시리즈 내에서 캐릭터, 스타일, 설정이 일관되게 유지됨
    """

    # 기본 정보
    id: str = Field(default_factory=lambda: f"series_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)

    # 상태
    status: SeriesStatus = Field(default=SeriesStatus.DRAFT)

    # 장르/타겟
    genres: List[SeriesGenre] = Field(default_factory=list)
    target_audience: SeriesTarget = Field(default=SeriesTarget.FAMILY)

    # ============================================================
    # 🎨 스타일 설정
    # ============================================================

    # 기본 아트 스타일
    art_style: str = Field(
        default="Disney 3D animation style, Pixar quality",
        description="시리즈 기본 아트 스타일"
    )

    # 색감 테마
    color_theme: str = Field(
        default="vibrant and warm",
        description="색감 테마 (vibrant, pastel, dark, neon 등)"
    )

    # 조명 스타일
    lighting_style: str = Field(
        default="soft cinematic lighting",
        description="조명 스타일"
    )

    # 스타일 키워드 (모든 프롬프트에 추가)
    style_keywords: List[str] = Field(
        default_factory=lambda: [
            "Disney 3D animation style",
            "Pixar quality",
            "smooth cel shading",
            "beautiful lighting"
        ]
    )

    # 네거티브 프롬프트
    negative_prompt: str = Field(
        default="realistic photo, live action, western cartoon, rough lines, low quality",
        description="시리즈 공통 네거티브 프롬프트"
    )

    # ============================================================
    # 🌍 월드 설정
    # ============================================================

    # 세계관
    world_setting: str = Field(
        default="",
        description="세계관 설명 (판타지 왕국, 현대 도시 등)"
    )

    # 시대 배경
    time_period: str = Field(
        default="fantasy",
        description="시대 배경 (fantasy, modern, medieval, future 등)"
    )

    # 지역 설정
    locations: Dict[str, str] = Field(
        default_factory=dict,
        description="주요 장소 {장소ID: 설명}"
    )

    # 마법/능력 시스템
    magic_system: Optional[str] = Field(
        default=None,
        description="마법/능력 시스템 설명"
    )

    # ============================================================
    # 👥 캐릭터
    # ============================================================

    # 주인공 ID 목록
    protagonist_ids: List[str] = Field(
        default_factory=list,
        description="주인공 캐릭터 ID 목록"
    )

    # 주요 조연 ID 목록
    supporting_character_ids: List[str] = Field(
        default_factory=list,
        description="주요 조연 캐릭터 ID 목록"
    )

    # 캐릭터 관계
    character_relationships: Dict[str, str] = Field(
        default_factory=dict,
        description="캐릭터 관계 {char1_id:char2_id: 관계}"
    )

    # ============================================================
    # 📺 에피소드
    # ============================================================

    # 에피소드 ID 목록
    episode_ids: List[str] = Field(
        default_factory=list,
        description="에피소드 ID 목록 (순서대로)"
    )

    # 시즌 구분
    seasons: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="시즌별 에피소드 {season_id: [episode_ids]}"
    )

    # ============================================================
    # ⚙️ 생성 설정
    # ============================================================

    # 비용 최적화 전략
    cost_strategy: str = Field(
        default="key_scenes_api",
        description="비용 최적화 전략"
    )

    # 프레임워크 설정
    default_fps: int = Field(default=30)
    default_resolution: str = Field(default="1080x1920")

    # TTS 설정
    default_voice_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="기본 TTS 설정"
    )

    # ============================================================
    # 메타데이터
    # ============================================================

    # 태그
    tags: List[str] = Field(default_factory=list)

    # 제작자
    creator: str = Field(default="")

    # 생성/수정 시간
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 커스텀 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "series_abc123",
                "name": "겨울 왕국 이야기",
                "description": "마법의 힘을 가진 공주의 모험 이야기",
                "status": "production",
                "genres": ["fantasy", "adventure"],
                "art_style": "Disney 3D animation style, ice and snow theme",
                "world_setting": "북유럽풍 판타지 왕국",
                "protagonist_ids": ["char_ella", "char_anna"]
            }
        }

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now()

    # ============================================================
    # 프롬프트 생성
    # ============================================================

    def get_style_prefix(self) -> str:
        """스타일 접두사 반환"""
        return ", ".join(self.style_keywords)

    def get_full_prompt_prefix(self) -> str:
        """전체 프롬프트 접두사"""
        parts = [
            self.get_style_prefix(),
            self.color_theme,
            self.lighting_style
        ]
        return ", ".join(p for p in parts if p)

    def get_location_prompt(self, location_key: str = None) -> str:
        """장소 프롬프트"""
        if location_key and location_key in self.locations:
            return f"{self.locations[location_key]}, {self.world_setting}"
        return self.world_setting

    # ============================================================
    # 에피소드 관리
    # ============================================================

    def add_episode(self, episode_id: str, season: str = "season_1") -> None:
        """에피소드 추가"""
        if episode_id not in self.episode_ids:
            self.episode_ids.append(episode_id)

            # 시즌에도 추가
            if season not in self.seasons:
                self.seasons[season] = []
            if episode_id not in self.seasons[season]:
                self.seasons[season].append(episode_id)

            self.update_timestamp()

    def remove_episode(self, episode_id: str) -> None:
        """에피소드 제거"""
        if episode_id in self.episode_ids:
            self.episode_ids.remove(episode_id)

        for season_eps in self.seasons.values():
            if episode_id in season_eps:
                season_eps.remove(episode_id)

        self.update_timestamp()

    def get_episode_count(self) -> int:
        """에피소드 수"""
        return len(self.episode_ids)

    # ============================================================
    # 캐릭터 관리
    # ============================================================

    def add_protagonist(self, character_id: str) -> None:
        """주인공 추가"""
        if character_id not in self.protagonist_ids:
            self.protagonist_ids.append(character_id)
            self.update_timestamp()

    def add_supporting_character(self, character_id: str) -> None:
        """조연 추가"""
        if character_id not in self.supporting_character_ids:
            self.supporting_character_ids.append(character_id)
            self.update_timestamp()

    def get_all_character_ids(self) -> List[str]:
        """모든 캐릭터 ID"""
        return self.protagonist_ids + self.supporting_character_ids

    def is_character_in_series(self, character_id: str) -> bool:
        """캐릭터가 이 시리즈에 속하는지"""
        return character_id in self.get_all_character_ids()

    # ============================================================
    # 장소 관리
    # ============================================================

    def add_location(self, location_id: str, description: str) -> None:
        """장소 추가"""
        self.locations[location_id] = description
        self.update_timestamp()

    # ============================================================
    # 직렬화
    # ============================================================

    def to_prompt_context(self) -> Dict[str, Any]:
        """프롬프트 컨텍스트로 변환"""
        return {
            "series_id": self.id,
            "series_name": self.name,
            "art_style": self.art_style,
            "style_prefix": self.get_full_prompt_prefix(),
            "negative_prompt": self.negative_prompt,
            "world_setting": self.world_setting,
            "time_period": self.time_period,
            "color_theme": self.color_theme,
            "lighting_style": self.lighting_style
        }
