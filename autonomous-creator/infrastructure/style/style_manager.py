"""
StyleManager - 스타일 스위칭 관리

스타일을 데이터로 관리하고 규칙 기반 스위칭 지원
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from core.domain.entities.scene import (
    SceneGraph,
    SceneNode,
    SceneStyle,
    StyleType,
    LightingType,
    RenderingType,
    Mood,
    ActionType,
)

logger = logging.getLogger(__name__)


@dataclass
class StyleSwitchResult:
    """스타일 전환 결과"""
    style: SceneStyle
    reason: str
    confidence: float  # 0.0 - 1.0


class StyleSwitchingStrategy(str, Enum):
    """스타일 전환 전략"""
    FIXED = "fixed"                    # 고정 (변경 없음)
    EMOTION_BASED = "emotion_based"    # 감정 기반
    ACTION_BASED = "action_based"      # 액션 기반
    HYBRID = "hybrid"                  # 하이브리드 (권장)


class StyleManager:
    """
    스타일 관리자

    규칙 기반 스타일 스위칭 및 Sequence 단위 일관성 유지
    """

    def __init__(
        self,
        default_style: SceneStyle = None,
        strategy: StyleSwitchingStrategy = StyleSwitchingStrategy.HYBRID
    ):
        self.default_style = default_style or SceneStyle()
        self.strategy = strategy

        # Sequence 단위 스타일 잠금
        self._locked_style: Optional[SceneStyle] = None
        self._lock_enabled: bool = True

    # ============================================================
    # 스타일 스위칭 규칙
    # ============================================================

    def decide_style(
        self,
        scene: SceneNode,
        prev_scene: SceneNode = None,
        context: Dict[str, Any] = None
    ) -> StyleSwitchResult:
        """
        장면에 적합한 스타일 결정

        Args:
            scene: 현재 장면
            prev_scene: 이전 장면
            context: 추가 컨텍스트

        Returns:
            StyleSwitchResult
        """
        # 1. 잠금 확인
        if self._locked_style and self._lock_enabled:
            return StyleSwitchResult(
                style=self._locked_style,
                reason="Style locked for sequence",
                confidence=1.0
            )

        # 2. 장면에 이미 스타일이 있고 잠금되어 있으면 유지
        if scene.style and scene.style.locked:
            return StyleSwitchResult(
                style=scene.style,
                reason="Scene style locked",
                confidence=1.0
            )

        # 3. 전략별 결정
        if self.strategy == StyleSwitchingStrategy.FIXED:
            return self._fixed_style()

        elif self.strategy == StyleSwitchingStrategy.EMOTION_BASED:
            return self._emotion_based_style(scene)

        elif self.strategy == StyleSwitchingStrategy.ACTION_BASED:
            return self._action_based_style(scene)

        else:  # HYBRID
            return self._hybrid_style(scene, prev_scene, context)

    def _fixed_style(self) -> StyleSwitchResult:
        """고정 스타일"""
        return StyleSwitchResult(
            style=self.default_style,
            reason="Fixed style strategy",
            confidence=1.0
        )

    def _emotion_based_style(self, scene: SceneNode) -> StyleSwitchResult:
        """감정 기반 스타일 결정"""
        # 감정 강도에 따른 스타일
        emotion_style_map = {
            Mood.HAPPY: StyleType.DISNEY_3D,
            Mood.EXCITED: StyleType.DISNEY_3D,
            Mood.SAD: StyleType.DISNEY_3D,  # Disney도 감정 표현 가능
            Mood.ROMANTIC: StyleType.DISNEY_3D,
            Mood.TENSE: StyleType.REALISTIC,  # 긴장감은 리얼
            Mood.SCARY: StyleType.REALISTIC,
            Mood.DRAMATIC: StyleType.REALISTIC,
            Mood.MYSTERIOUS: StyleType.ANIME,
        }

        style_type = emotion_style_map.get(scene.mood, StyleType.DISNEY_3D)

        # 감정에 따른 조명
        emotion_lighting_map = {
            Mood.HAPPY: LightingType.GOLDEN_HOUR,
            Mood.SAD: LightingType.BLUE_HOUR,
            Mood.TENSE: LightingType.DRAMATIC,
            Mood.ROMANTIC: LightingType.CANDLELIGHT,
            Mood.EXCITED: LightingType.NATURAL,
            Mood.SCARY: LightingType.HARSH,
            Mood.MYSTERIOUS: LightingType.SOFT,
            Mood.DRAMATIC: LightingType.DRAMATIC,
            Mood.PEACEFUL: LightingType.SOFT,
            Mood.NEUTRAL: LightingType.NATURAL,
        }

        lighting = emotion_lighting_map.get(scene.mood, LightingType.SOFT)

        style = SceneStyle(
            type=style_type,
            lighting=lighting,
            rendering=RenderingType.CEL_SHADED if style_type == StyleType.DISNEY_3D else RenderingType.CINEMATIC
        )

        return StyleSwitchResult(
            style=style,
            reason=f"Emotion-based: {scene.mood.value}",
            confidence=0.8
        )

    def _action_based_style(self, scene: SceneNode) -> StyleSwitchResult:
        """액션 기반 스타일 결정"""
        # 대화 많은 장면 → Disney (감정 표현)
        if scene.action == ActionType.TALKING:
            style = SceneStyle(
                type=StyleType.DISNEY_3D,
                lighting=LightingType.SOFT,
                rendering=RenderingType.CEL_SHADED
            )
            return StyleSwitchResult(
                style=style,
                reason="Dialogue-heavy scene",
                confidence=0.85
            )

        # 액션 장면 → Realistic (역동성)
        if scene.action in [ActionType.FIGHTING, ActionType.RUNNING]:
            style = SceneStyle(
                type=StyleType.REALISTIC,
                lighting=LightingType.DRAMATIC,
                rendering=RenderingType.CINEMATIC
            )
            return StyleSwitchResult(
                style=style,
                reason="Action scene",
                confidence=0.85
            )

        # 기본
        return self._fixed_style()

    def _hybrid_style(
        self,
        scene: SceneNode,
        prev_scene: SceneNode,
        context: Dict[str, Any]
    ) -> StyleSwitchResult:
        """하이브리드 스타일 결정 (감정 + 액션 + 컨텍스트)"""

        # 1. 우선순위: 액션
        if scene.action in [ActionType.FIGHTING, ActionType.RUNNING]:
            return self._action_based_style(scene)

        # 2. 대화 장면에서 감정 강도 확인
        if scene.action == ActionType.TALKING:
            # 감정이 강하면 Disney 유지
            intense_emotions = [Mood.HAPPY, Mood.SAD, Mood.EXCITED, Mood.ANGRY]
            if scene.mood in intense_emotions:
                return self._emotion_based_style(scene)

        # 3. 이전 장면과의 연속성 확인
        if prev_scene and prev_scene.style:
            # 같은 장소면 스타일 유지
            if scene.location == prev_scene.location:
                return StyleSwitchResult(
                    style=prev_scene.style,
                    reason="Same location continuity",
                    confidence=0.9
                )

        # 4. 기본 감정 기반
        return self._emotion_based_style(scene)

    # ============================================================
    # Sequence 관리
    # ============================================================

    def lock_style(self, style: SceneStyle = None) -> None:
        """스타일 잠금 (Sequence 전체)"""
        self._locked_style = style or self.default_style
        self._locked_style.locked = True
        logger.info(f"Style locked: {self._locked_style.type.value}")

    def unlock_style(self) -> None:
        """스타일 잠금 해제"""
        self._locked_style = None
        logger.info("Style unlocked")

    def apply_to_scene_graph(
        self,
        scene_graph: SceneGraph,
        force: bool = False
    ) -> int:
        """
        SceneGraph 전체에 스타일 적용

        Args:
            scene_graph: 장면 그래프
            force: 잠금된 스타일도 덮어쓰기

        Returns:
            변경된 장면 수
        """
        changes = 0
        prev_scene = None

        for scene in scene_graph.get_ordered_scenes():
            # 잠금된 장면은 스킵 (force가 아니면)
            if scene.style.locked and not force:
                prev_scene = scene
                continue

            # 스타일 결정
            result = self.decide_style(scene, prev_scene)

            # 적용
            scene.style = result.style
            changes += 1

            logger.debug(
                f"Scene {scene.scene_id}: {result.reason} "
                f"(confidence: {result.confidence:.2f})"
            )

            prev_scene = scene

        # 기본 스타일 업데이트
        scene_graph.default_style = self.default_style

        return changes

    # ============================================================
    # 스타일 검증
    # ============================================================

    def validate_style_consistency(
        self,
        scene_graph: SceneGraph
    ) -> List[str]:
        """
        스타일 일관성 검증

        Returns:
            경고 메시지 목록
        """
        warnings = []

        if len(scene_graph.scenes) < 2:
            return warnings

        prev_style = None
        for scene in scene_graph.get_ordered_scenes():
            if prev_style:
                # 스타일 타입이 급격히 변하면 경고
                if scene.style.type != prev_style.type:
                    warnings.append(
                        f"Scene {scene.scene_id}: Style type changed "
                        f"from {prev_style.type.value} to {scene.style.type.value}"
                    )

            prev_style = scene.style

        return warnings


# ============================================================
# 편의 함수
# ============================================================

_style_manager: Optional[StyleManager] = None


def get_style_manager() -> StyleManager:
    """싱글톤 StyleManager"""
    global _style_manager
    if _style_manager is None:
        _style_manager = StyleManager()
    return _style_manager


def create_disney_style() -> SceneStyle:
    """Disney 3D 스타일 생성"""
    return SceneStyle(
        type=StyleType.DISNEY_3D,
        lighting=LightingType.SOFT,
        rendering=RenderingType.CEL_SHADED,
        color_palette="vibrant_warm"
    )


def create_realistic_style() -> SceneStyle:
    """Realistic 스타일 생성"""
    return SceneStyle(
        type=StyleType.REALISTIC,
        lighting=LightingType.CINEMATIC,
        rendering=RenderingType.PHOTOREALISTIC,
        color_palette="muted_cool"
    )


def create_anime_style() -> SceneStyle:
    """Anime 스타일 생성"""
    return SceneStyle(
        type=StyleType.ANIME,
        lighting=LightingType.NATURAL,
        rendering=RenderingType.FLAT,
        color_palette="pastel"
    )
