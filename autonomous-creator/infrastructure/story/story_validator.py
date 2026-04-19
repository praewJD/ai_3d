"""
StorySpec Validator + Retry Loop

스토리 검증 및 재시도 로직
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any, Tuple
from enum import Enum
import time

from infrastructure.story.story_spec import (
    StorySpec, SceneSpec, TargetFormat, ScenePurpose,
    SHORTS_CONSTRAINTS, LONGFORM_CONSTRAINTS
)


class ValidationError:
    """검증 오류"""
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error", "warning", "info"

    def __str__(self):
        return f"[{self.severity.upper()}] {self.field}: {self.message}"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity
        }


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    score: float = 0.0  # 0~100
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "score": self.score,
            "details": self.details
        }


class StoryValidator:
    """StorySpec 검증기"""

    def __init__(self):
        self.rules = [
            self._validate_structure,
            self._validate_duration,
            self._validate_scene_count,
            self._validate_arc_completeness,
            self._validate_characters,
            self._validate_scene_flow,
            self._validate_hook_strength,
        ]

    def validate(self, story_spec: StorySpec) -> ValidationResult:
        """스토리 전체 검증"""
        errors = []
        warnings = []

        for rule in self.rules:
            try:
                rule_errors, rule_warnings = rule(story_spec)
                errors.extend(rule_errors)
                warnings.extend(rule_warnings)
            except Exception as e:
                errors.append(ValidationError("validation", f"Rule failed: {e}"))

        # 점수 계산
        score = self._calculate_score(errors, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score
        )

    def _validate_structure(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """기본 구조 검증"""
        errors = []
        warnings = []

        if not spec.title:
            errors.append(ValidationError("title", "Missing title"))
        if not spec.arc or not spec.arc.hook:
            errors.append(ValidationError("arc.hook", "Missing hook"))
        if not spec.scenes or len(spec.scenes) == 0:
            errors.append(ValidationError("scenes", "No scenes"))

        return errors, warnings

    def _validate_duration(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """길이 검증"""
        errors = []
        warnings = []

        constraints = SHORTS_CONSTRAINTS if spec.target == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS

        total_duration = spec.total_duration()

        if total_duration < constraints["min_duration"]:
            errors.append(ValidationError(
                "duration",
                f"Too short: {total_duration}s < {constraints['min_duration']}s"
            ))
        elif total_duration > constraints["max_duration"]:
            errors.append(ValidationError(
                "duration",
                f"Too long: {total_duration}s > {constraints['max_duration']}s"
            ))

        return errors, warnings

    def _validate_scene_count(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """씬 수 검증"""
        errors = []
        warnings = []

        constraints = SHORTS_CONSTRAINTS if spec.target == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS
        scene_count = len(spec.scenes)

        if scene_count < constraints["min_scenes"]:
            errors.append(ValidationError(
                "scene_count",
                f"Too few scenes: {scene_count} < {constraints['min_scenes']}"
            ))
        elif scene_count > constraints["max_scenes"]:
            errors.append(ValidationError(
                "scene_count",
                f"Too many scenes: {scene_count} > {constraints['max_scenes']}"
            ))

        return errors, warnings

    def _validate_arc_completeness(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """아크 완성도 검증"""
        errors = []
        warnings = []

        # 각 purpose별 씬 존재 확인
        purposes = {scene.purpose.value for scene in spec.scenes}

        required = {"hook", "climax"}
        for purpose in required:
            if purpose not in purposes:
                errors.append(ValidationError(
                    "arc",
                    f"Missing {purpose} scene"
                ))

        return errors, warnings

    def _validate_characters(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """캐릭터 검증"""
        errors = []
        warnings = []

        # 캐릭터 ID 일관성
        all_char_ids = {c.id for c in spec.characters}
        for scene in spec.scenes:
            for char_id in scene.characters:
                if char_id not in all_char_ids:
                    warnings.append(ValidationError(
                        f"scene.{scene.id}",
                        f"Unknown character: {char_id}",
                        "warning"
                    ))

        return errors, warnings

    def _validate_scene_flow(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """씬 흐름 검증"""
        errors = []
        warnings = []

        # Hook이 첫 번째에 위치하는지
        if spec.scenes and spec.scenes[0].purpose != ScenePurpose.HOOK:
            warnings.append(ValidationError(
                "scene_flow",
                "First scene should be hook",
                "warning"
            ))

        return errors, warnings

    def _validate_hook_strength(self, spec: StorySpec) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Hook 강도 검증"""
        errors = []
        warnings = []

        # Hook 씬 찾기
        hook_scenes = [s for s in spec.scenes if s.purpose == ScenePurpose.HOOK]

        if hook_scenes:
            hook = hook_scenes[0]
            # Hook이 3초 이내인지
            if hook.duration > 3:
                warnings.append(ValidationError(
                    "hook",
                    f"Hook too long: {hook.duration}s > 3s",
                    "warning"
                ))

        return errors, warnings

    def _calculate_score(self, errors: List[ValidationError], warnings: List[ValidationError]) -> float:
        """점수 계산 (0~100)"""
        score = 100.0
        score -= len(errors) * 15  # 각 에러 -15점
        score -= len(warnings) * 5  # 각 경고 -5점
        return max(0, score)


class RetryPolicy:
    """재시도 정책"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_on_errors: Optional[List[str]] = None,
        backoff_factor: float = 1.5
    ):
        self.max_retries = max_retries
        self.retry_on_errors = retry_on_errors or ["duration", "scene_count"]
        self.backoff_factor = backoff_factor


class RetryLoop:
    """검증 실패 시 재시도 루프"""

    def __init__(
        self,
        validator: StoryValidator,
        policy: Optional[RetryPolicy] = None
    ):
        self.validator = validator
        self.policy = policy or RetryPolicy()

    async def execute_with_retry(
        self,
        generate_func: Callable,
        fix_func: Optional[Callable] = None,
        max_retries: Optional[int] = None
    ) -> Tuple[Optional[StorySpec], ValidationResult, int]:
        """
        생성 → 검증 → 실패 시 수정 후 재시도

        Args:
            generate_func: 스토리 생성 함수 (async)
            fix_func: 수정 함수 (async), 선택적
            max_retries: 최대 재시도 횟수

        Returns:
            (StorySpec, ValidationResult, retry_count)
        """
        retries = max_retries or self.policy.max_retries
        retry_count = 0

        # 1. 초기 생성
        spec = await generate_func()
        result = self.validator.validate(spec)

        # 2. 검증 통과 시 반환
        if result.is_valid:
            return spec, result, retry_count

        # 3. 실패 시 재시도
        while retry_count < retries and not result.is_valid:
            retry_count += 1

            # 수정 함수가 있으면 사용
            if fix_func:
                spec = await fix_func(spec, result.errors)
            else:
                # 자동 수정 시도
                spec = self._auto_fix(spec, result.errors)

            # 재검증
            result = self.validator.validate(spec)

            # 백오프
            time.sleep(self.policy.backoff_factor ** retry_count * 0.1)

        return spec, result, retry_count

    def _auto_fix(self, spec: StorySpec, errors: List[ValidationError]) -> StorySpec:
        """자동 수정"""
        for error in errors:
            if error.field == "duration":
                spec = self._fix_duration(spec)
            elif error.field == "scene_count":
                spec = self._fix_scene_count(spec)

        return spec

    def _fix_duration(self, spec: StorySpec) -> StorySpec:
        """길이 수정"""
        constraints = SHORTS_CONSTRAINTS if spec.target == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS
        total_duration = spec.total_duration()

        if spec.scenes:
            if total_duration < constraints["min_duration"]:
                # 씬 duration 늘리기
                scale_factor = constraints["min_duration"] / max(total_duration, 0.1)
                for scene in spec.scenes:
                    scene.duration *= scale_factor
            elif total_duration > constraints["max_duration"]:
                # 씬 duration 줄이기
                scale_factor = constraints["max_duration"] / max(total_duration, 1.0)
                for scene in spec.scenes:
                    scene.duration = max(1.0, scene.duration * scale_factor)

        return spec

    def _fix_scene_count(self, spec: StorySpec) -> StorySpec:
        """씬 수 수정"""
        constraints = SHORTS_CONSTRAINTS if spec.target == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS
        scene_count = len(spec.scenes)

        if scene_count < constraints["min_scenes"]:
            # 기존 씬 복제하여 추가
            needed = constraints["min_scenes"] - scene_count
            for i in range(needed):
                if spec.scenes:
                    base_scene = spec.scenes[i % scene_count]
                    new_scene = SceneSpec(
                        id=f"{base_scene.id}_dup{i}",
                        purpose=base_scene.purpose,
                        camera=base_scene.camera,
                        mood=base_scene.mood,
                        action=base_scene.action,
                        characters=base_scene.characters.copy(),
                        location=base_scene.location,
                        dialogue=base_scene.dialogue,
                        narration=base_scene.narration,
                        duration=base_scene.duration,
                        emotion=base_scene.emotion
                    )
                    spec.scenes.append(new_scene)

        elif scene_count > constraints["max_scenes"]:
            # 뒤에서부터 씬 제거
            while len(spec.scenes) > constraints["max_scenes"]:
                spec.scenes.pop()

        return spec
