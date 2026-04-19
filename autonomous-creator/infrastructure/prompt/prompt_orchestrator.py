"""
PromptOrchestrator - SceneGraph를 프롬프트로 변환

품질 높은 이미지/영상 프롬프트를 생성하는 핵심 계층
스타일을 데이터로 관리하여 유연한 스타일 스위칭 지원
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import logging

from core.domain.entities.scene import (
    SceneGraph,
    SceneNode,
    DialogueLine,
    SceneStyle,
    StyleType,
    LightingType,
    RenderingType,
    CharacterIdentity,
    CameraAngle,
    ActionType,
    Mood,
    Transition,
    STYLE_PROMPTS,
    LIGHTING_PROMPTS,
    COLOR_PALETTE_PROMPTS,
)

logger = logging.getLogger(__name__)


# ============================================================
# 프롬프트 템플릿 상수 (기본값용 - SceneStyle 데이터 우선)
# ============================================================

# Disney 3D 스타일 접두사 (기본값)
DISNEY_3D_PREFIX = STYLE_PROMPTS.get(StyleType.DISNEY_3D, "")

# 카메라 앵글별 프롬프트
CAMERA_ANGLE_PROMPTS = {
    CameraAngle.CLOSE_UP: "close-up shot, portrait framing, shallow depth of field, detailed facial features",
    CameraAngle.MEDIUM: "medium shot, upper body visible, natural framing",
    CameraAngle.WIDE: "wide shot, full body, environmental context, establishing shot",
    CameraAngle.BIRD_EYE: "bird's eye view, overhead angle, top-down perspective",
    CameraAngle.LOW_ANGLE: "low angle shot, dramatic perspective, heroic stance",
    CameraAngle.OVER_SHOULDER: "over-the-shoulder shot, POV conversation, depth layers",
    CameraAngle.POV: "first person perspective, POV shot, immersive angle",
}

# 액션별 프롬프트
ACTION_PROMPTS = {
    ActionType.IDLE: "standing still, calm pose",
    ActionType.WALKING: "walking naturally, gentle movement",
    ActionType.RUNNING: "running dynamically, motion blur, energetic",
    ActionType.TALKING: "speaking, animated expression, lip movement",
    ActionType.FIGHTING: "dynamic action pose, combat stance, intense",
    ActionType.DANCING: "dancing gracefully, rhythmic movement",
    ActionType.SITTING: "sitting comfortably, relaxed posture",
    ActionType.STANDING: "standing naturally, poised stance",
}

# 무드별 시각적 변환
MOOD_VISUAL_MAP = {
    Mood.HAPPY: "bright warm lighting, vibrant colors, cheerful atmosphere, soft glow",
    Mood.SAD: "dim cool lighting, muted colors, melancholic atmosphere, soft shadows",
    Mood.NEUTRAL: "balanced natural lighting, neutral tones, calm atmosphere",
    Mood.TENSE: "dramatic lighting, high contrast, shadows, suspenseful atmosphere",
    Mood.ROMANTIC: "soft golden hour lighting, warm pink tones, dreamy atmosphere, lens flare",
    Mood.MYSTERIOUS: "low key lighting, deep shadows, fog, enigmatic atmosphere",
    Mood.EXCITED: "dynamic lighting, saturated colors, energetic atmosphere, vibrant",
    Mood.PEACEFUL: "soft diffused lighting, pastel colors, serene atmosphere, gentle",
    Mood.SCARY: "dark harsh lighting, cold blue tones, ominous atmosphere, heavy shadows",
    Mood.DRAMATIC: "theatrical lighting, strong contrast, cinematic atmosphere, rim light",
}

# 전환 효과 프롬프트
TRANSITION_PROMPTS = {
    Transition.CUT: "",
    Transition.FADE: "fade transition",
    Transition.CROSSFADE: "smooth crossfade transition",
    Transition.WIPE: "wipe transition effect",
    Transition.DISSOLVE: "dissolve transition",
    Transition.ZOOM: "zoom transition",
}

# 컬러 팔레트 프롬프트 (SceneStyle에서 사용)
COLOR_PALETTE_PROMPTS = {
    "vibrant_warm": "vibrant warm colors, saturated reds oranges yellows",
    "muted_cool": "muted cool colors, desaturated blues greens",
    "pastel": "pastel colors, soft pinks blues lavenders",
    "dark_moody": "dark moody colors, deep shadows, low key",
    "autumn": "autumn colors, oranges browns reds",
    "spring": "spring colors, fresh greens pinks yellows",
}

# 모션 강도 레벨
class MotionIntensity(str, Enum):
    STATIC = "static"
    SUBTLE = "subtle"
    MODERATE = "moderate"
    DYNAMIC = "dynamic"
    INTENSE = "intense"


# ============================================================
# 프롬프트 번들
# ============================================================

@dataclass
class ImagePromptBundle:
    """이미지 프롬프트 번들"""
    positive: str
    negative: str
    style_prefix: str
    camera_prompt: str
    mood_prompt: str
    character_prompt: str
    location_prompt: str

    # 추가 파라미터
    aspect_ratio: str = "16:9"
    seed: Optional[int] = None


@dataclass
class VideoPromptBundle:
    """영상 프롬프트 번들"""
    image_prompt: str  # 베이스 이미지용
    motion_prompt: str  # 모션 설명
    camera_motion: str  # 카메라 모션
    intensity: MotionIntensity = MotionIntensity.MODERATE
    duration_seconds: float = 5.0

    # 연속성
    continuity_hints: List[str] = field(default_factory=list)


@dataclass
class TTSInput:
    """TTS 입력"""
    text: str
    voice_id: str
    emotion: str = "neutral"
    speed: float = 1.0
    pitch: float = 0.0

    # 캐릭터 매핑
    character_id: str = ""


# ============================================================
# PromptOrchestrator
# ============================================================

class PromptOrchestrator:
    """
    프롬프트 오케스트레이터

    SceneGraph를 고품질 프롬프트로 변환
    """

    def __init__(
        self,
        style_prefix: str = DISNEY_3D_PREFIX,
        default_negative: str = None
    ):
        self.style_prefix = style_prefix
        self.default_negative = default_negative or self._build_default_negative()

        # 캐릭터 voice 매핑 (시리즈에서 설정 가능)
        self.character_voice_map: Dict[str, str] = {}

        # 이전 장면 컨텍스트 (연속성 유지용)
        self._prev_scene: Optional[SceneNode] = None

    def _build_default_negative(self) -> str:
        """기본 네거티브 프롬프트"""
        return (
            "realistic photo, live action, western cartoon, anime, "
            "dark, gritty, photorealistic, low quality, blurry, "
            "watermark, text, signature, bad anatomy, deformed, "
            "ugly, duplicate, mutation, extra limbs"
        )

    # ============================================================
    # 이미지 프롬프트
    # ============================================================

    def build_image_prompt(
        self,
        scene: SceneNode,
        prev_scene: SceneNode = None,
        character_identities: Dict[str, CharacterIdentity] = None
    ) -> ImagePromptBundle:
        """
        이미지 프롬프트 생성 (스타일 데이터 활용)

        Args:
            scene: 장면 노드
            prev_scene: 이전 장면 (연속성용)
            character_identities: 캐릭터 정체성 맵

        Returns:
            ImagePromptBundle
        """
        parts = []

        # 1. 스타일 (데이터에서 가져옴 - NEW!)
        style_prompt = scene.style.to_prompt_segment()
        parts.append(style_prompt)

        # 2. 조명 (데이터에서 가져옴 - NEW!)
        lighting_prompt = LIGHTING_PROMPTS.get(scene.style.lighting, "")
        parts.append(lighting_prompt)

        # 3. 컬러 팔레트 (데이터에서 가져옴 - NEW!)
        color_prompt = COLOR_PALETTE_PROMPTS.get(scene.style.color_palette, "")
        parts.append(color_prompt)

        # 4. 카메라 앵글
        camera_prompt = CAMERA_ANGLE_PROMPTS.get(scene.camera_angle, "")
        parts.append(camera_prompt)

        # 5. 캐릭터 (일관성 적용 - NEW!)
        character_prompt = self._build_character_prompt_with_identity(
            scene.characters,
            character_identities
        )
        if character_prompt:
            parts.append(character_prompt)

        # 6. 액션
        action_prompt = ACTION_PROMPTS.get(scene.action, "")
        parts.append(action_prompt)

        # 7. 장면 설명
        parts.append(scene.description)

        # 8. 장소
        location_prompt = self._build_location_prompt(scene.location)
        if location_prompt:
            parts.append(location_prompt)

        # 9. 무드/분위기
        mood_prompt = MOOD_VISUAL_MAP.get(scene.mood, "")
        parts.append(mood_prompt)

        # 10. 연속성 힌트 (이전 장면과 연결)
        continuity = self._build_continuity_prompt(scene, prev_scene)
        if continuity:
            parts.append(continuity)

        # 11. 품질 태그
        parts.extend([
            "masterpiece",
            "best quality",
            "highly detailed",
            "4K resolution"
        ])

        positive = ", ".join(p for p in parts if p)

        return ImagePromptBundle(
            positive=positive,
            negative=self.default_negative,
            style_prefix=self.style_prefix,
            camera_prompt=camera_prompt,
            mood_prompt=mood_prompt,
            character_prompt=character_prompt,
            location_prompt=location_prompt
        )

    def _build_character_prompt(
        self,
        character_ids: List[str],
        appearances: Dict[str, str] = None
    ) -> str:
        """캐릭터 프롬프트 생성 (기본)"""
        if not character_ids:
            return ""

        appearances = appearances or {}
        parts = []

        for char_id in character_ids:
            if char_id in appearances:
                # 정의된 외형 사용
                parts.append(appearances[char_id])
            else:
                # 기본 캐릭터 표현
                parts.append(f"character {char_id}")

        return ", ".join(parts)

    def _build_character_prompt_with_identity(
        self,
        character_ids: List[str],
        character_identities: Dict[str, CharacterIdentity] = None
    ) -> str:
        """캐릭터 프롬프트 생성 (일관성 적용)"""
        if not character_ids:
            return ""

        character_identities = character_identities or {}
        parts = []

        for char_id in character_ids:
            if char_id in character_identities:
                # CharacterIdentity에서 일관성 프롬프트 사용
                identity = character_identities[char_id]
                parts.append(identity.get_consistency_prompt())

                # 외형 설명 추가
                if identity.appearance_description:
                    parts.append(identity.appearance_description)
            else:
                # 기본 캐릭터 표현
                parts.append(f"character {char_id}")

        # 전체 일관성 태그 추가
        if len(character_ids) > 0:
            parts.append("consistent character design, same face, same outfit")

        return ", ".join(parts)

    def _build_location_prompt(self, location: str) -> str:
        """장소 프롬프트 생성"""
        if not location:
            return ""

        # 장소 확장 로직 (향후 location DB 연동 가능)
        return f"in {location}"

    def _build_continuity_prompt(
        self,
        scene: SceneNode,
        prev_scene: SceneNode
    ) -> str:
        """연속성 프롬프트"""
        if not prev_scene:
            return ""

        parts = []

        # 같은 캐릭터 연속성
        common_chars = set(scene.characters) & set(prev_scene.characters)
        if common_chars:
            parts.append("same character design, consistent appearance")

        # 장소 연속성
        if scene.location == prev_scene.location:
            parts.append("same environment, consistent background")

        return ", ".join(parts)

    # ============================================================
    # 영상 프롬프트
    # ============================================================

    def build_video_prompt(
        self,
        scene: SceneNode,
        image_prompt: str,
        prev_scene: SceneNode = None
    ) -> VideoPromptBundle:
        """
        영상 프롬프트 생성

        Args:
            scene: 장면 노드
            image_prompt: 베이스 이미지 프롬프트
            prev_scene: 이전 장면

        Returns:
            VideoPromptBundle
        """
        # 모션 프롬프트
        motion_prompt = self._build_motion_prompt(scene)

        # 카메라 모션
        camera_motion = self._build_camera_motion(scene, prev_scene)

        # 모션 강도 결정
        intensity = self._determine_motion_intensity(scene)

        # 연속성 힌트
        continuity_hints = self._build_video_continuity(scene, prev_scene)

        return VideoPromptBundle(
            image_prompt=image_prompt,
            motion_prompt=motion_prompt,
            camera_motion=camera_motion,
            intensity=intensity,
            duration_seconds=scene.duration_seconds,
            continuity_hints=continuity_hints
        )

    def _build_motion_prompt(self, scene: SceneNode) -> str:
        """모션 프롬프트 생성"""
        parts = []

        # 액션 기반 모션
        if scene.action == ActionType.WALKING:
            parts.append("walking forward naturally, smooth gait")
        elif scene.action == ActionType.RUNNING:
            parts.append("running fast, dynamic movement, hair flowing")
        elif scene.action == ActionType.TALKING:
            parts.append("subtle head movement, natural gestures, lip sync")
        elif scene.action == ActionType.FIGHTING:
            parts.append("dynamic combat motion, fast action, impact")
        elif scene.action == ActionType.DANCING:
            parts.append("graceful dancing motion, rhythmic movement")
        else:
            parts.append("subtle breathing motion, gentle sway")

        # 추가 모션 힌트
        if scene.mood == Mood.HAPPY:
            parts.append("energetic bouncy movement")
        elif scene.mood == Mood.SAD:
            parts.append("slow heavy movement")
        elif scene.mood == Mood.TENSE:
            parts.append("cautious deliberate movement")

        return ", ".join(parts)

    def _build_camera_motion(
        self,
        scene: SceneNode,
        prev_scene: SceneNode
    ) -> str:
        """카메라 모션 생성"""
        # 카메라 앵글에 따른 모션
        if scene.camera_angle == CameraAngle.CLOSE_UP:
            return "subtle camera drift, slight push in"
        elif scene.camera_angle == CameraAngle.WIDE:
            return "slow establishing pan, gentle camera movement"
        elif scene.camera_angle == CameraAngle.LOW_ANGLE:
            return "dramatic rising camera, heroic reveal"
        else:
            return "smooth cinematic camera movement, gentle tracking"

    def _determine_motion_intensity(self, scene: SceneNode) -> MotionIntensity:
        """모션 강도 결정"""
        # 액션 기반
        if scene.action in [ActionType.FIGHTING, ActionType.RUNNING]:
            return MotionIntensity.INTENSE
        elif scene.action in [ActionType.DANCING]:
            return MotionIntensity.DYNAMIC
        elif scene.action in [ActionType.WALKING, ActionType.TALKING]:
            return MotionIntensity.MODERATE
        elif scene.action == ActionType.IDLE:
            # 무드 기반
            if scene.mood in [Mood.HAPPY, Mood.EXCITED]:
                return MotionIntensity.SUBTLE
            return MotionIntensity.STATIC

        return MotionIntensity.MODERATE

    def _build_video_continuity(
        self,
        scene: SceneNode,
        prev_scene: SceneNode
    ) -> List[str]:
        """영상 연속성 힌트"""
        hints = []

        if prev_scene:
            # 캐릭터 연속성
            hints.append("maintain character appearance from previous scene")

            # 장소 전환
            if scene.location != prev_scene.location:
                hints.append(f"scene transition from {prev_scene.location} to {scene.location}")

        return hints

    # ============================================================
    # TTS 입력
    # ============================================================

    def build_tts_input(
        self,
        dialogue: DialogueLine,
        default_voice: str = "ko-KR-SunHiNeural"
    ) -> TTSInput:
        """
        TTS 입력 생성

        Args:
            dialogue: 대사 라인
            default_voice: 기본 보이스

        Returns:
            TTSInput
        """
        # 캐릭터별 보이스 매핑
        voice_id = self.character_voice_map.get(
            dialogue.character_id,
            default_voice
        )

        # 감정 → TTS 파라미터 변환
        emotion_params = self._emotion_to_tts_params(dialogue.emotion)

        return TTSInput(
            text=dialogue.text,
            voice_id=voice_id,
            emotion=dialogue.emotion,
            character_id=dialogue.character_id,
            **emotion_params
        )

    def _emotion_to_tts_params(self, emotion: str) -> Dict[str, float]:
        """감정을 TTS 파라미터로 변환"""
        params = {"speed": 1.0, "pitch": 0.0}

        emotion_map = {
            "happy": {"speed": 1.1, "pitch": 5.0},
            "sad": {"speed": 0.85, "pitch": -5.0},
            "excited": {"speed": 1.2, "pitch": 10.0},
            "angry": {"speed": 1.1, "pitch": 0.0},
            "fear": {"speed": 0.9, "pitch": -3.0},
            "neutral": {"speed": 1.0, "pitch": 0.0},
        }

        return emotion_map.get(emotion, params)

    # ============================================================
    # 전체 파이프라인
    # ============================================================

    def build_all_prompts(
        self,
        scene_graph: SceneGraph,
        character_appearances: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        전체 SceneGraph의 프롬프트 생성

        Args:
            scene_graph: 장면 그래프
            character_appearances: 캐릭터 외형 맵

        Returns:
            전체 프롬프트 딕셔너리
        """
        result = {
            "story_id": scene_graph.story_id,
            "title": scene_graph.title,
            "art_style": scene_graph.art_style,
            "scenes": []
        }

        prev_scene = None

        for scene in scene_graph.get_ordered_scenes():
            # 이미지 프롬프트
            image_bundle = self.build_image_prompt(
                scene,
                prev_scene,
                character_appearances
            )

            # 영상 프롬프트
            video_bundle = self.build_video_prompt(
                scene,
                image_bundle.positive,
                prev_scene
            )

            # TTS 입력들
            tts_inputs = [
                self.build_tts_input(d)
                for d in scene.dialogue
            ]

            scene_prompts = {
                "scene_id": scene.scene_id,
                "order": scene.order,
                "image": {
                    "positive": image_bundle.positive,
                    "negative": image_bundle.negative,
                },
                "video": {
                    "motion_prompt": video_bundle.motion_prompt,
                    "camera_motion": video_bundle.camera_motion,
                    "intensity": video_bundle.intensity.value,
                    "duration": video_bundle.duration_seconds,
                },
                "tts": [
                    {
                        "text": t.text,
                        "voice_id": t.voice_id,
                        "emotion": t.emotion,
                    }
                    for t in tts_inputs
                ],
                "narration": scene.narration,
                "transition_in": scene.transition_in.value,
                "transition_out": scene.transition_out.value,
            }

            result["scenes"].append(scene_prompts)
            prev_scene = scene

        return result

    # ============================================================
    # 설정
    # ============================================================

    def set_character_voice(self, character_id: str, voice_id: str) -> None:
        """캐릭터별 보이스 설정"""
        self.character_voice_map[character_id] = voice_id

    def set_style_prefix(self, prefix: str) -> None:
        """스타일 접두사 설정"""
        self.style_prefix = prefix


# ============================================================
# 편의 함수
# ============================================================

_orchestrator: Optional[PromptOrchestrator] = None


def get_prompt_orchestrator() -> PromptOrchestrator:
    """싱글톤 오케스트레이터"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PromptOrchestrator()
    return _orchestrator
