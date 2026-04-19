"""
SceneGraph Entity - 장면 그래프 데이터 구조

스토리를 구조화된 장면 데이터로 표현
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import json


# ============================================================
# 스타일 관련 Enum 및 클래스
# ============================================================

class StyleType(str, Enum):
    """스타일 타입"""
    DISNEY_3D = "3d_disney"
    REALISTIC = "realistic"
    ANIME = "anime"
    WATERCOLOR = "watercolor"
    PIXEL_ART = "pixel_art"
    CLAYMATION = "claymation"


class LightingType(str, Enum):
    """조명 타입"""
    NATURAL = "natural"
    STUDIO = "studio"
    GOLDEN_HOUR = "golden_hour"
    BLUE_HOUR = "blue_hour"
    DRAMATIC = "dramatic"
    SOFT = "soft"
    HARSH = "harsh"
    NEON = "neon"
    CANDLELIGHT = "candlelight"


class RenderingType(str, Enum):
    """렌더링 타입"""
    STANDARD = "standard"
    CINEMATIC = "cinematic"
    FLAT = "flat"
    CEL_SHADED = "cel_shaded"
    PAINTERLY = "painterly"
    PHOTOREALISTIC = "photorealistic"


@dataclass
class SceneStyle:
    """장면 스타일 (데이터로 관리)"""
    type: StyleType = StyleType.DISNEY_3D
    lighting: LightingType = LightingType.SOFT
    rendering: RenderingType = RenderingType.CEL_SHADED
    color_palette: str = "vibrant_warm"  # vibrant_warm, muted_cool, pastel, dark_moody

    # 스타일 잠금 (Sequence 단위 유지용)
    locked: bool = False

    def to_prompt_segment(self) -> str:
        """스타일을 프롬프트 세그먼트로 변환"""
        return _STYLE_PROMPTS.get(self.type, _STYLE_PROMPTS[StyleType.DISNEY_3D])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "lighting": self.lighting.value,
            "rendering": self.rendering.value,
            "color_palette": self.color_palette,
            "locked": self.locked
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneStyle":
        if isinstance(data.get("type"), str):
            data["type"] = StyleType(data["type"])
        if isinstance(data.get("lighting"), str):
            data["lighting"] = LightingType(data["lighting"])
        if isinstance(data.get("rendering"), str):
            data["rendering"] = RenderingType(data["rendering"])
        return cls(**data)


# 스타일별 프롬프트 템플릿
_STYLE_PROMPTS = {
    StyleType.DISNEY_3D: (
        "Disney 3D animation style, Pixar quality, "
        "soft global illumination, expressive characters, "
        "stylized proportions, vibrant colors, "
        "smooth cel shading, high quality 3D render"
    ),
    StyleType.REALISTIC: (
        "photorealistic, cinematic lighting, "
        "film grain, real world textures, "
        "natural skin tones, detailed environment, "
        "8K resolution, professional photography"
    ),
    StyleType.ANIME: (
        "anime style, Japanese animation, "
        "clean linework, cel shading, "
        "expressive eyes, stylized hair, "
        "vibrant colors, high quality illustration"
    ),
    StyleType.WATERCOLOR: (
        "watercolor painting style, "
        "soft edges, flowing colors, "
        "artistic, dreamy atmosphere, "
        "traditional media look"
    ),
    StyleType.PIXEL_ART: (
        "pixel art style, retro game aesthetic, "
        "limited color palette, crisp pixels, "
        "16-bit style, nostalgic feel"
    ),
    StyleType.CLAYMATION: (
        "claymation style, stop motion look, "
        "clay textures, handcrafted appearance, "
        "Aardman animation style, tactile feel"
    ),
}

# 조명별 프롬프트
_LIGHTING_PROMPTS = {
    LightingType.NATURAL: "natural daylight, soft shadows",
    LightingType.STUDIO: "studio lighting, professional setup",
    LightingType.GOLDEN_HOUR: "golden hour lighting, warm sunset glow",
    LightingType.BLUE_HOUR: "blue hour lighting, twilight atmosphere",
    LightingType.DRAMATIC: "dramatic lighting, high contrast, shadows",
    LightingType.SOFT: "soft diffused lighting, gentle shadows",
    LightingType.HARSH: "harsh direct lighting, strong shadows",
    LightingType.NEON: "neon lights, cyberpunk atmosphere, colorful glow",
    LightingType.CANDLELIGHT: "candlelight, warm intimate glow, flickering",
}

# 컬러 팔레트
_COLOR_PALETTE_PROMPTS = {
    "vibrant_warm": "vibrant warm colors, saturated reds oranges yellows",
    "muted_cool": "muted cool colors, desaturated blues greens",
    "pastel": "pastel colors, soft pinks blues lavenders",
    "dark_moody": "dark moody colors, deep shadows, low key",
    "autumn": "autumn colors, oranges browns reds",
    "spring": "spring colors, fresh greens pinks yellows",
}

# 공개 상수 (별칭)
STYLE_PROMPTS = _STYLE_PROMPTS
LIGHTING_PROMPTS = _LIGHTING_PROMPTS
COLOR_PALETTE_PROMPTS = _COLOR_PALETTE_PROMPTS


# ============================================================
# 카메라/액션/무드 Enum
# ============================================================

class CameraAngle(str, Enum):
    """카메라 앵글"""
    CLOSE_UP = "close-up"
    MEDIUM = "medium_shot"
    WIDE = "wide_shot"
    BIRD_EYE = "bird_eye"
    LOW_ANGLE = "low_angle"
    OVER_SHOULDER = "over_shoulder"
    POV = "pov"


class ActionType(str, Enum):
    """액션 타입"""
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    TALKING = "talking"
    FIGHTING = "fighting"
    DANCING = "dancing"
    SITTING = "sitting"
    STANDING = "standing"


class Mood(str, Enum):
    """분위기/무드"""
    HAPPY = "happy"
    SAD = "sad"
    NEUTRAL = "neutral"
    TENSE = "tense"
    ROMANTIC = "romantic"
    MYSTERIOUS = "mysterious"
    EXCITED = "excited"
    PEACEFUL = "peaceful"
    SCARY = "scary"
    DRAMATIC = "dramatic"


class Transition(str, Enum):
    """장면 전환 효과"""
    CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    WIPE = "wipe"
    DISSOLVE = "dissolve"
    ZOOM = "zoom"


# ============================================================
# 캐릭터 일관성
# ============================================================

@dataclass
class CharacterIdentity:
    """캐릭터 정체성 (일관성 유지용)"""
    character_id: str
    name: str

    # 외형 고정
    appearance_description: str = ""
    face_embedding_ref: str = ""  # IP-Adapter용 참조
    outfit: str = "default"

    # 스타일 잠금
    style_lock: bool = True  # True면 스타일 변경 금지

    # 메타데이터
    voice_id: str = ""
    personality_traits: List[str] = field(default_factory=list)

    def get_consistency_prompt(self) -> str:
        """일관성 유지용 프롬프트"""
        parts = [
            f"character named {self.name}",
            "same face, same appearance",
            "consistent character design"
        ]
        if self.outfit and self.outfit != "default":
            parts.append(f"wearing {self.outfit}")
        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterIdentity":
        return cls(**data)


@dataclass
class DialogueLine:
    """대사 라인"""
    character_id: str
    text: str
    emotion: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueLine":
        return cls(**data)


@dataclass
class SceneNode:
    """단일 장면 노드"""
    scene_id: str
    description: str

    # 캐릭터 및 장소
    characters: List[str] = field(default_factory=list)
    location: str = ""

    # 스타일 (NEW!)
    style: SceneStyle = field(default_factory=SceneStyle)

    # 카메라/액션
    camera_angle: CameraAngle = CameraAngle.MEDIUM
    action: ActionType = ActionType.IDLE
    mood: Mood = Mood.NEUTRAL

    # 미디어
    dialogue: List[DialogueLine] = field(default_factory=list)
    narration: str = ""

    # 전환
    transition_in: Transition = Transition.FADE
    transition_out: Transition = Transition.FADE

    # 메타데이터
    duration_seconds: float = 5.0
    order: int = 0

    # 추가 프롬프트 정보
    extra_prompts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        # Enum 변환
        data["camera_angle"] = self.camera_angle.value
        data["action"] = self.action.value
        data["mood"] = self.mood.value
        data["transition_in"] = self.transition_in.value
        data["transition_out"] = self.transition_out.value
        # Style 변환
        data["style"] = self.style.to_dict()
        # DialogueLine 변환
        data["dialogue"] = [d.to_dict() for d in self.dialogue]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneNode":
        """딕셔너리에서 생성"""
        # Enum 변환
        if isinstance(data.get("camera_angle"), str):
            data["camera_angle"] = CameraAngle(data["camera_angle"])
        if isinstance(data.get("action"), str):
            data["action"] = ActionType(data["action"])
        if isinstance(data.get("mood"), str):
            data["mood"] = Mood(data["mood"])
        if isinstance(data.get("transition_in"), str):
            data["transition_in"] = Transition(data["transition_in"])
        if isinstance(data.get("transition_out"), str):
            data["transition_out"] = Transition(data["transition_out"])

        # Style 변환 (NEW!)
        if "style" in data and isinstance(data["style"], dict):
            data["style"] = SceneStyle.from_dict(data["style"])
        elif "style" not in data:
            data["style"] = SceneStyle()

        # DialogueLine 변환
        if "dialogue" in data and isinstance(data["dialogue"], list):
            data["dialogue"] = [
                DialogueLine.from_dict(d) if isinstance(d, dict) else d
                for d in data["dialogue"]
            ]

        return cls(**data)

    def get_full_prompt(self, style_prefix: str = "") -> str:
        """전체 프롬프트 생성 (스타일 데이터 활용)"""
        parts = []

        # 스타일 (데이터에서 가져옴)
        parts.append(self.style.to_prompt_segment())

        # 조명
        parts.append(_LIGHTING_PROMPTS.get(self.style.lighting, ""))

        # 컬러 팔레트
        parts.append(_COLOR_PALETTE_PROMPTS.get(self.style.color_palette, ""))

        # 장면 설명
        parts.append(self.description)

        # 캐릭터
        if self.characters:
            parts.append(f"with {', '.join(self.characters)}")

        # 장소
        if self.location:
            parts.append(f"in {self.location}")

        # 카메라
        parts.append(f"{self.camera_angle.value} shot")

        # 분위기
        parts.append(f"{self.mood.value} atmosphere")

        # 액션
        if self.action != ActionType.IDLE:
            parts.append(self.action.value)

        # 추가 프롬프트
        parts.extend(self.extra_prompts)

        return ", ".join(parts)


@dataclass
class SceneGraph:
    """장면들의 연결 그래프"""
    story_id: str
    title: str = ""

    # 장면 목록
    scenes: List[SceneNode] = field(default_factory=list)

    # 스타일 설정 (데이터로 관리 - NEW!)
    default_style: SceneStyle = field(default_factory=SceneStyle)

    # 캐릭터 정체성 맵 (일관성 유지 - NEW!)
    character_identities: Dict[str, CharacterIdentity] = field(default_factory=dict)

    # 메타데이터
    series_id: Optional[str] = None
    episode: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> float:
        """총 재생 시간"""
        return sum(s.duration_seconds for s in self.scenes)

    @property
    def scene_count(self) -> int:
        """장면 수"""
        return len(self.scenes)

    def get_scene(self, scene_id: str) -> Optional[SceneNode]:
        """ID로 장면 조회"""
        for scene in self.scenes:
            if scene.scene_id == scene_id:
                return scene
        return None

    def get_ordered_scenes(self) -> List[SceneNode]:
        """순서대로 정렬된 장면 목록"""
        return sorted(self.scenes, key=lambda s: s.order)

    def add_scene(self, scene: SceneNode) -> None:
        """장면 추가"""
        if scene.order == 0:
            scene.order = len(self.scenes)
        # 스타일이 없으면 기본 스타일 적용
        if not scene.style or scene.style.type == StyleType.DISNEY_3D:
            scene.style = self.default_style
        self.scenes.append(scene)

    def lock_style_for_sequence(self, style: SceneStyle) -> None:
        """Sequence 전체 스타일 잠금"""
        self.default_style = style
        self.default_style.locked = True
        for scene in self.scenes:
            if not scene.style.locked:
                scene.style = style

    def add_character_identity(self, identity: CharacterIdentity) -> None:
        """캐릭터 정체성 추가"""
        self.character_identities[identity.character_id] = identity

    def get_character_identity(self, character_id: str) -> Optional[CharacterIdentity]:
        """캐릭터 정체성 조회"""
        return self.character_identities.get(character_id)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "story_id": self.story_id,
            "title": self.title,
            "scenes": [s.to_dict() for s in self.scenes],
            "default_style": self.default_style.to_dict(),
            "character_identities": {
                k: v.to_dict() for k, v in self.character_identities.items()
            },
            "series_id": self.series_id,
            "episode": self.episode,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneGraph":
        """딕셔너리에서 생성"""
        scenes = [
            SceneNode.from_dict(s) if isinstance(s, dict) else s
            for s in data.pop("scenes", [])
        ]
        # Style 변환
        if "default_style" in data and isinstance(data["default_style"], dict):
            data["default_style"] = SceneStyle.from_dict(data["default_style"])
        # CharacterIdentities 변환
        if "character_identities" in data:
            data["character_identities"] = {
                k: CharacterIdentity.from_dict(v) if isinstance(v, dict) else v
                for k, v in data["character_identities"].items()
            }
        return cls(scenes=scenes, **data)

    @classmethod
    def from_json(cls, json_str: str) -> "SceneGraph":
        """JSON 문자열에서 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_all_characters(self) -> List[str]:
        """모든 등장 캐릭터 목록"""
        characters = set()
        for scene in self.scenes:
            characters.update(scene.characters)
        return list(characters)

    def get_all_locations(self) -> List[str]:
        """모든 장소 목록"""
        locations = set()
        for scene in self.scenes:
            if scene.location:
                locations.add(scene.location)
        return list(locations)
