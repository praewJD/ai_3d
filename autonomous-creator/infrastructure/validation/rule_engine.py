"""
RuleEngine - SceneGraph 검증 및 자동 수정

LLM 출력의 불확실성을 줄이기 위한 검증 계층
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional, Callable
from abc import ABC, abstractmethod
import re
import logging

from core.domain.entities.scene import (
    SceneGraph,
    SceneNode,
    CameraAngle,
    ActionType,
    Mood,
    Transition
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixed_count: int = 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """다른 결과와 병합"""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
        self.fixed_count += other.fixed_count


class IValidationRule(ABC):
    """검증 규칙 인터페이스"""

    @property
    @abstractmethod
    def name(self) -> str:
        """규칙 이름"""
        pass

    @abstractmethod
    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        """검증 실행"""
        pass

    @abstractmethod
    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        """자동 수정"""
        pass


class RequiredFieldRule(IValidationRule):
    """필수 필드 검증"""

    @property
    def name(self) -> str:
        return "required_fields"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not scene_graph.story_id:
            result.add_error("story_id is required")

        if not scene_graph.scenes:
            result.add_error("At least one scene is required")

        for scene in scene_graph.scenes:
            if not scene.scene_id:
                result.add_error(f"Scene missing scene_id: {scene.description[:50]}")

            if not scene.description:
                result.add_error(f"Scene {scene.scene_id} missing description")

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        for i, scene in enumerate(scene_graph.scenes):
            if not scene.scene_id:
                scene.scene_id = f"scene_{i:03d}"
                fixes += 1
                logger.info(f"Auto-fixed: Set scene_id to {scene.scene_id}")

        return scene_graph, fixes


class DurationRule(IValidationRule):
    """재생 시간 검증"""

    MIN_DURATION = 1.0
    MAX_DURATION = 30.0
    DEFAULT_DURATION = 5.0

    @property
    def name(self) -> str:
        return "duration"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        for scene in scene_graph.scenes:
            if scene.duration_seconds < self.MIN_DURATION:
                result.add_warning(
                    f"Scene {scene.scene_id}: duration {scene.duration_seconds}s < min {self.MIN_DURATION}s"
                )
            elif scene.duration_seconds > self.MAX_DURATION:
                result.add_warning(
                    f"Scene {scene.scene_id}: duration {scene.duration_seconds}s > max {self.MAX_DURATION}s"
                )

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        for scene in scene_graph.scenes:
            if scene.duration_seconds < self.MIN_DURATION:
                scene.duration_seconds = self.DEFAULT_DURATION
                fixes += 1
                logger.info(f"Auto-fixed: Set duration to {self.DEFAULT_DURATION}s for {scene.scene_id}")
            elif scene.duration_seconds > self.MAX_DURATION:
                scene.duration_seconds = self.MAX_DURATION
                fixes += 1
                logger.info(f"Auto-fixed: Capped duration to {self.MAX_DURATION}s for {scene.scene_id}")

        return scene_graph, fixes


class CharacterConsistencyRule(IValidationRule):
    """캐릭터 일관성 검증"""

    @property
    def name(self) -> str:
        return "character_consistency"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        # 모든 캐릭터 수집
        all_characters = scene_graph.get_all_characters()

        # 캐릭터 이름 정규화 체크
        for char in all_characters:
            if not self._is_normalized(char):
                result.add_warning(f"Character name may need normalization: '{char}'")

        return result

    def _is_normalized(self, name: str) -> bool:
        """이름이 정규화되었는지 확인"""
        # 소문자, 숫자, 언더스코어만 허용
        return bool(re.match(r'^[a-z0-9_]+$', name))

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0
        char_map: Dict[str, str] = {}

        # 캐릭터 이름 정규화 맵 생성
        for char in scene_graph.get_all_characters():
            if not self._is_normalized(char):
                normalized = self._normalize_name(char)
                char_map[char] = normalized
                fixes += 1

        # 적용
        for scene in scene_graph.scenes:
            scene.characters = [
                char_map.get(c, c) for c in scene.characters
            ]

        return scene_graph, fixes

    def _normalize_name(self, name: str) -> str:
        """이름 정규화"""
        # 소문자화, 공백을 언더스코어로
        normalized = name.lower().replace(" ", "_")
        # 특수문자 제거
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)
        return normalized or "character"


class CameraVarietyRule(IValidationRule):
    """카메라 앵글 다양성 검증"""

    @property
    def name(self) -> str:
        return "camera_variety"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if len(scene_graph.scenes) < 3:
            return result

        # 카메라 앵글 분포 확인
        angle_counts: Dict[CameraAngle, int] = {}
        for scene in scene_graph.scenes:
            angle_counts[scene.camera_angle] = angle_counts.get(scene.camera_angle, 0) + 1

        # 같은 앵글이 50% 이상이면 경고
        total = len(scene_graph.scenes)
        for angle, count in angle_counts.items():
            ratio = count / total
            if ratio > 0.5:
                result.add_warning(
                    f"Camera angle '{angle.value}' used {ratio:.0%} of scenes. Consider more variety."
                )

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        if len(scene_graph.scenes) < 3:
            return scene_graph, fixes

        # 추천 앵글 패턴
        recommended = [
            CameraAngle.WIDE,      # 시작
            CameraAngle.MEDIUM,    # 전개
            CameraAngle.CLOSE_UP,  # 클라이맥스
            CameraAngle.MEDIUM,
            CameraAngle.WIDE,      # 마무리
        ]

        for i, scene in enumerate(scene_graph.scenes):
            # 항상 같은 앵글이면 추천 패턴 적용
            recommended_angle = recommended[i % len(recommended)]
            if scene.camera_angle != recommended_angle:
                # 대화 장면은 close-up 유지
                if scene.action != ActionType.TALKING:
                    scene.camera_angle = recommended_angle
                    fixes += 1

        return scene_graph, fixes


class LocationTransitionRule(IValidationRule):
    """장소 전환 검증"""

    @property
    def name(self) -> str:
        return "location_transition"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        prev_location = None
        for scene in scene_graph.get_ordered_scenes():
            if prev_location and scene.location:
                # 장소가 급격히 변하면 전환 효과 확인
                if prev_location != scene.location:
                    if scene.transition_in == Transition.CUT:
                        result.add_warning(
                            f"Scene {scene.scene_id}: Location changed from '{prev_location}' to '{scene.location}' "
                            f"but using 'cut' transition. Consider 'fade' or 'crossfade'."
                        )
            prev_location = scene.location

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        prev_location = None
        for scene in scene_graph.get_ordered_scenes():
            if prev_location and scene.location:
                if prev_location != scene.location:
                    if scene.transition_in == Transition.CUT:
                        scene.transition_in = Transition.FADE
                        fixes += 1
                        logger.info(f"Auto-fixed: Changed transition to 'fade' for location change in {scene.scene_id}")
            prev_location = scene.location

        return scene_graph, fixes


class OrderConsistencyRule(IValidationRule):
    """순서 일관성 검증"""

    @property
    def name(self) -> str:
        return "order_consistency"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        orders = [s.order for s in scene_graph.scenes]

        # 중복 확인
        if len(orders) != len(set(orders)):
            result.add_warning("Duplicate scene orders detected")

        # 연속성 확인
        if orders:
            sorted_orders = sorted(orders)
            expected = list(range(len(orders)))
            if sorted_orders != expected:
                result.add_warning("Scene orders are not sequential")

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        # 순서 재할당
        for i, scene in enumerate(scene_graph.get_ordered_scenes()):
            if scene.order != i:
                scene.order = i
                fixes += 1

        return scene_graph, fixes


class EmotionFlowRule(IValidationRule):
    """감정 흐름 검증 - 감정이 급격히 변하지 않도록"""

    # 감정 강도 매핑 (0-10)
    MOOD_INTENSITY = {
        Mood.NEUTRAL: 5,
        Mood.PEACEFUL: 3,
        Mood.HAPPY: 7,
        Mood.EXCITED: 9,
        Mood.SAD: 7,
        Mood.ROMANTIC: 6,
        Mood.TENSE: 8,
        Mood.MYSTERIOUS: 6,
        Mood.SCARY: 9,
        Mood.DRAMATIC: 8,
    }

    @property
    def name(self) -> str:
        return "emotion_flow"

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if len(scene_graph.scenes) < 2:
            return result

        prev_mood = None
        prev_intensity = 5

        for scene in scene_graph.get_ordered_scenes():
            current_intensity = self.MOOD_INTENSITY.get(scene.mood, 5)

            if prev_mood:
                # 감정 강도 차이가 너무 크면 경고
                intensity_diff = abs(current_intensity - prev_intensity)

                if intensity_diff > 5:
                    result.add_warning(
                        f"Scene {scene.scene_id}: Abrupt emotion change "
                        f"from {prev_mood.value} to {scene.mood.value} (diff={intensity_diff})"
                    )

            prev_mood = scene.mood
            prev_intensity = current_intensity

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        if len(scene_graph.scenes) < 3:
            return scene_graph, fixes

        # 중간 장면의 감정 조정 (너무 급격한 변화 완화)
        scenes = scene_graph.get_ordered_scenes()

        for i in range(1, len(scenes) - 1):
            prev_intensity = self.MOOD_INTENSITY.get(scenes[i-1].mood, 5)
            next_intensity = self.MOOD_INTENSITY.get(scenes[i+1].mood, 5)
            current_intensity = self.MOOD_INTENSITY.get(scenes[i].mood, 5)

            # 이전/다음과 현재 차이가 모두 크면 중간값으로 조정
            if (abs(current_intensity - prev_intensity) > 4 and
                abs(current_intensity - next_intensity) > 4):

                # NEUTRAL로 조정하여 완충 역할
                scenes[i].mood = Mood.NEUTRAL
                fixes += 1
                logger.info(f"Auto-fixed: Buffered emotion in scene {scenes[i].scene_id}")

        return scene_graph, fixes


class VisualDensityRule(IValidationRule):
    """시각적 밀도 검증 - 장면이 너무 단순하지 않은지"""

    # 최소 필요 요소
    MIN_ELEMENTS = 2  # 최소 2개 이상의 시각적 요소

    @property
    def name(self) -> str:
        return "visual_density"

    def _count_visual_elements(self, scene: SceneNode) -> int:
        """시각적 요소 카운트"""
        count = 0

        # 캐릭터
        if scene.characters:
            count += len(scene.characters)

        # 장소
        if scene.location:
            count += 1

        # 액션
        if scene.action != ActionType.IDLE:
            count += 1

        # 대화
        if scene.dialogue:
            count += 1

        # 설명 길이 (단어 수 기반)
        word_count = len(scene.description.split())
        if word_count > 10:
            count += 1

        return count

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        for scene in scene_graph.scenes:
            elements = self._count_visual_elements(scene)

            if elements < self.MIN_ELEMENTS:
                result.add_warning(
                    f"Scene {scene.scene_id}: Low visual density ({elements} elements). "
                    f"Consider adding more details."
                )

        return result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, int]:
        fixes = 0

        for scene in scene_graph.scenes:
            elements = self._count_visual_elements(scene)

            if elements < self.MIN_ELEMENTS:
                # 기본 카메라 앵글 추가 (없는 경우)
                if scene.camera_angle == CameraAngle.MEDIUM:
                    # 이미 기본값이면 설명 강화 제안
                    scene.extra_prompts.append(
                        "detailed environment, rich background, atmospheric lighting"
                    )
                    fixes += 1
                    logger.info(f"Auto-fixed: Added visual density to scene {scene.scene_id}")

        return scene_graph, fixes


class RuleEngine:
    """
    규칙 기반 검증 엔진

    SceneGraph의 품질을 보장하고
    LLM 출력의 불확실성을 줄임
    """

    def __init__(self):
        self.rules: List[IValidationRule] = [
            RequiredFieldRule(),
            DurationRule(),
            CharacterConsistencyRule(),
            CameraVarietyRule(),
            LocationTransitionRule(),
            OrderConsistencyRule(),
            # 품질 규칙 (NEW!)
            EmotionFlowRule(),
            VisualDensityRule(),
        ]

    def add_rule(self, rule: IValidationRule) -> None:
        """규칙 추가"""
        self.rules.append(rule)

    def validate(self, scene_graph: SceneGraph) -> ValidationResult:
        """전체 검증"""
        final_result = ValidationResult(is_valid=True)

        for rule in self.rules:
            logger.debug(f"Running rule: {rule.name}")
            result = rule.validate(scene_graph)
            final_result.merge(result)

        logger.info(
            f"Validation complete: valid={final_result.is_valid}, "
            f"errors={len(final_result.errors)}, warnings={len(final_result.warnings)}"
        )

        return final_result

    def auto_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, ValidationResult]:
        """
        자동 수정

        Returns:
            (수정된 SceneGraph, 검증 결과)
        """
        result = ValidationResult(is_valid=True)
        total_fixes = 0

        for rule in self.rules:
            scene_graph, fixes = rule.auto_fix(scene_graph)
            total_fixes += fixes
            if fixes > 0:
                logger.info(f"Rule '{rule.name}' made {fixes} fixes")

        result.fixed_count = total_fixes

        # 수정 후 재검증
        final_validation = self.validate(scene_graph)
        final_validation.fixed_count = total_fixes

        return scene_graph, final_validation

    def validate_and_fix(self, scene_graph: SceneGraph) -> Tuple[SceneGraph, ValidationResult]:
        """
        검증 후 필요시 자동 수정

        Returns:
            (SceneGraph, ValidationResult)
        """
        result = self.validate(scene_graph)

        if not result.is_valid or result.warnings:
            return self.auto_fix(scene_graph)

        return scene_graph, result
