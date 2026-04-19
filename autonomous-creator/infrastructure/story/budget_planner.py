"""
Budget Planner - Scene Budget Controller

비용/길이 제어를 위한 예산 계획 모듈
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from .story_spec import (
    SHORTS_CONSTRAINTS,
    LONGFORM_CONSTRAINTS,
    TargetFormat,
    ScenePurpose,
    SceneSpec
)


@dataclass
class BudgetPlan:
    """예산 계획"""
    target_format: str  # shorts / longform
    total_duration: int  # 총 길이 (초)
    scene_count: int  # 씬 수
    scene_duration_range: Tuple[int, int]  # 씬당 길이 범위
    hook_duration: int  # Hook 길이 (shorts: 3초 고정)

    # 예산 할당
    hook_scenes: int  # Hook 씬 수
    build_scenes: int  # Build 씬 수
    climax_scenes: int  # Climax 씬 수
    resolution_scenes: int  # Resolution 씬 수

    # 추가 메타데이터
    estimated_total_duration: int = 0  # 예상 총 길이
    buffer_duration: int = 0  # 버퍼 시간

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "target_format": self.target_format,
            "total_duration": self.total_duration,
            "scene_count": self.scene_count,
            "scene_duration_range": self.scene_duration_range,
            "hook_duration": self.hook_duration,
            "hook_scenes": self.hook_scenes,
            "build_scenes": self.build_scenes,
            "climax_scenes": self.climax_scenes,
            "resolution_scenes": self.resolution_scenes,
            "estimated_total_duration": self.estimated_total_duration,
            "buffer_duration": self.buffer_duration
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetPlan":
        """딕셔너리에서 생성"""
        return cls(**data)


class BudgetPlanner:
    """Scene Budget Controller - 비용/길이 제어"""

    # 포맷별 제약
    CONSTRAINTS = {
        "shorts": {
            "min_duration": 20,
            "max_duration": 35,
            "min_scenes": 6,
            "max_scenes": 10,
            "scene_duration_range": (2, 4),
            "hook_duration": 3
        },
        "longform": {
            "min_duration": 120,
            "max_duration": 480,
            "min_scenes": 20,
            "max_scenes": 60,
            "scene_duration_range": (3, 8),
            "hook_duration": 5
        }
    }

    # 씬 분배 비율 (4-Act 구조 기반)
    SCENE_DISTRIBUTION = {
        "shorts": {"hook": 1, "build": 3, "climax": 3, "resolution": 1},
        "longform": {"hook": 2, "build": 10, "climax": 5, "resolution": 3}
    }

    # 감정 강도 비율 (각 단계별 감정 강도)
    EMOTION_INTENSITY = {
        "hook": 0.8,
        "build": 0.5,
        "climax": 1.0,
        "resolution": 0.3
    }

    def __init__(self):
        """초기화"""
        pass

    def plan(self, target_format: str, arc_result: Optional[Any] = None,
             desired_duration: Optional[int] = None,
             desired_scene_count: Optional[int] = None) -> BudgetPlan:
        """
        포맷에 맞는 예산 계획 수립

        Args:
            target_format: 타겟 포맷 ("shorts" 또는 "longform")
            arc_result: 아크 결과 (선택적)
            desired_duration: 희망 총 길이 (선택적)
            desired_scene_count: 희망 씬 수 (선택적)

        Returns:
            BudgetPlan: 수립된 예산 계획
        """
        # 1. 제약 로드
        format_key = target_format.lower() if target_format else "shorts"
        constraints = self.CONSTRAINTS.get(format_key, self.CONSTRAINTS["shorts"])

        # 2. 씬 수 결정
        if desired_scene_count:
            scene_count = self.adjust_to_budget(desired_scene_count, format_key)
        else:
            # 기본값 사용
            scene_count = (constraints["min_scenes"] + constraints["max_scenes"]) // 2

        # 3. 씬 분배
        distribution = self.allocate_scenes(scene_count, format_key)

        # 4. 길이 할당
        if desired_duration:
            total_duration = max(constraints["min_duration"],
                                 min(desired_duration, constraints["max_duration"]))
        else:
            total_duration = (constraints["min_duration"] + constraints["max_duration"]) // 2

        # 5. 예상 총 길이 계산
        avg_scene_duration = sum(constraints["scene_duration_range"]) / 2
        estimated_total = int(scene_count * avg_scene_duration)
        buffer = abs(total_duration - estimated_total)

        return BudgetPlan(
            target_format=format_key,
            total_duration=total_duration,
            scene_count=scene_count,
            scene_duration_range=constraints["scene_duration_range"],
            hook_duration=constraints["hook_duration"],
            hook_scenes=distribution["hook"],
            build_scenes=distribution["build"],
            climax_scenes=distribution["climax"],
            resolution_scenes=distribution["resolution"],
            estimated_total_duration=estimated_total,
            buffer_duration=buffer
        )

    def allocate_scenes(self, total_scenes: int, format: str) -> Dict[str, int]:
        """
        씬 수를 각 단계에 분배

        Args:
            total_scenes: 전체 씬 수
            format: 포맷

        Returns:
            Dict[str, int]: 각 단계별 씬 수
        """
        format_key = format.lower() if format else "shorts"
        base_distribution = self.SCENE_DISTRIBUTION.get(
            format_key,
            self.SCENE_DISTRIBUTION["shorts"]
        )

        # 비율 계산
        total_ratio = sum(base_distribution.values())

        # 각 단계에 비율대로 분배
        result = {}
        allocated = 0

        for stage, ratio in base_distribution.items():
            count = max(1, int(total_scenes * ratio / total_ratio))
            result[stage] = count
            allocated += count

        # 남은 씬 보정 (build에 추가)
        remaining = total_scenes - allocated
        if remaining > 0:
            result["build"] += remaining
        elif remaining < 0:
            # 초과 시 resolution에서 차감 (최소 1개 유지)
            excess = abs(remaining)
            if result["resolution"] > 1:
                deduct = min(excess, result["resolution"] - 1)
                result["resolution"] -= deduct
                excess -= deduct
            if excess > 0 and result["build"] > 1:
                result["build"] -= min(excess, result["build"] - 1)

        return result

    def validate_budget(self, plan: BudgetPlan) -> List[str]:
        """
        예산 검증

        Args:
            plan: 검증할 예산 계획

        Returns:
            List[str]: 문제점 목록
        """
        errors = []
        constraints = self.CONSTRAINTS.get(plan.target_format, self.CONSTRAINTS["shorts"])

        # 씬 수 검증
        if plan.scene_count < constraints["min_scenes"]:
            errors.append(f"Too few scenes: {plan.scene_count} < {constraints['min_scenes']}")
        if plan.scene_count > constraints["max_scenes"]:
            errors.append(f"Too many scenes: {plan.scene_count} > {constraints['max_scenes']}")

        # 길이 검증
        if plan.total_duration < constraints["min_duration"]:
            errors.append(f"Duration too short: {plan.total_duration}s < {constraints['min_duration']}s")
        if plan.total_duration > constraints["max_duration"]:
            errors.append(f"Duration too long: {plan.total_duration}s > {constraints['max_duration']}s")

        # 씬 분배 검증
        total_allocated = plan.hook_scenes + plan.build_scenes + plan.climax_scenes + plan.resolution_scenes
        if total_allocated != plan.scene_count:
            errors.append(f"Scene allocation mismatch: {total_allocated} != {plan.scene_count}")

        # Hook 씬 수 검증 (최소 1개)
        if plan.hook_scenes < 1:
            errors.append("Hook must have at least 1 scene")

        # Resolution 씬 수 검증 (최소 1개)
        if plan.resolution_scenes < 1:
            errors.append("Resolution must have at least 1 scene")

        return errors

    def adjust_to_budget(self, scene_count: int, format: str) -> int:
        """
        예산에 맞게 씬 수 조정

        Args:
            scene_count: 원하는 씬 수
            format: 포맷

        Returns:
            int: 조정된 씬 수
        """
        constraints = self.CONSTRAINTS.get(format.lower(), self.CONSTRAINTS["shorts"])
        return max(constraints["min_scenes"],
                   min(scene_count, constraints["max_scenes"]))

    def get_constraints(self, format: str) -> Dict[str, Any]:
        """
        포맷별 제약 조건 반환

        Args:
            format: 포맷

        Returns:
            Dict: 제약 조건
        """
        return self.CONSTRAINTS.get(format.lower(), self.CONSTRAINTS["shorts"])

    def suggest_scene_count(self, target_duration: int, format: str) -> int:
        """
        목표 길이에 맞는 씬 수 제안

        Args:
            target_duration: 목표 길이 (초)
            format: 포맷

        Returns:
            int: 제안된 씬 수
        """
        constraints = self.CONSTRAINTS.get(format.lower(), self.CONSTRAINTS["shorts"])
        avg_duration = sum(constraints["scene_duration_range"]) / 2
        suggested = int(target_duration / avg_duration)
        return self.adjust_to_budget(suggested, format)

    def get_emotion_intensity(self, stage: str) -> float:
        """
        각 단계별 감정 강도 반환

        Args:
            stage: 단계명 (hook, build, climax, resolution)

        Returns:
            float: 감정 강도 (0.0 ~ 1.0)
        """
        return self.EMOTION_INTENSITY.get(stage.lower(), 0.5)


class DurationController:
    """Duration Controller - 길이 제어"""

    def __init__(self, budget_planner: BudgetPlanner):
        """
        초기화

        Args:
            budget_planner: BudgetPlanner 인스턴스
        """
        self.planner = budget_planner

    def estimate_duration(self, scene_count: int, format: str) -> int:
        """
        예상 길이 계산

        Args:
            scene_count: 씬 수
            format: 포맷

        Returns:
            int: 예상 길이 (초)
        """
        constraints = self.planner.get_constraints(format)
        avg_scene_duration = sum(constraints["scene_duration_range"]) / 2
        return int(scene_count * avg_scene_duration)

    def compress_if_needed(self, scenes: List[SceneSpec], target_duration: int) -> List[SceneSpec]:
        """
        목표 길이 초과 시 압축

        Args:
            scenes: 씬 목록
            target_duration: 목표 길이 (초)

        Returns:
            List[SceneSpec]: 압축된 씬 목록
        """
        if not scenes:
            return scenes

        current_duration = sum(s.duration for s in scenes)

        if current_duration <= target_duration:
            return scenes

        # 압축 비율 계산
        compression_ratio = target_duration / current_duration

        # 각 씬의 길이를 비율에 맞춰 조정
        compressed_scenes = []
        for scene in scenes:
            new_duration = max(1.0, scene.duration * compression_ratio)  # 최소 1초
            compressed_scene = SceneSpec(
                id=scene.id,
                purpose=scene.purpose,
                camera=scene.camera,
                mood=scene.mood,
                action=scene.action,
                characters=scene.characters.copy(),
                location=scene.location,
                dialogue=scene.dialogue,
                narration=scene.narration,
                duration=new_duration,
                emotion=scene.emotion
            )
            compressed_scenes.append(compressed_scene)

        return compressed_scenes

    def expand_if_needed(self, scenes: List[SceneSpec], target_duration: int,
                         max_scene_duration: float = 8.0) -> List[SceneSpec]:
        """
        목표 길이 미달 시 확장

        Args:
            scenes: 씬 목록
            target_duration: 목표 길이 (초)
            max_scene_duration: 최대 씬 길이 (기본 8초)

        Returns:
            List[SceneSpec]: 확장된 씬 목록
        """
        if not scenes:
            return scenes

        current_duration = sum(s.duration for s in scenes)

        if current_duration >= target_duration:
            return scenes

        # 확장 비율 계산
        expansion_ratio = target_duration / current_duration

        # 각 씬의 길이를 비율에 맞춰 조정 (최대 길이 제한)
        expanded_scenes = []
        for scene in scenes:
            new_duration = min(max_scene_duration, scene.duration * expansion_ratio)
            expanded_scene = SceneSpec(
                id=scene.id,
                purpose=scene.purpose,
                camera=scene.camera,
                mood=scene.mood,
                action=scene.action,
                characters=scene.characters.copy(),
                location=scene.location,
                dialogue=scene.dialogue,
                narration=scene.narration,
                duration=new_duration,
                emotion=scene.emotion
            )
            expanded_scenes.append(expanded_scene)

        return expanded_scenes

    def balance_durations(self, scenes: List[SceneSpec], format: str) -> List[SceneSpec]:
        """
        씬 길이 균형 조정

        Args:
            scenes: 씬 목록
            format: 포맷

        Returns:
            List[SceneSpec]: 균형 조정된 씬 목록
        """
        if not scenes:
            return scenes

        constraints = self.planner.get_constraints(format)
        min_duration, max_duration = constraints["scene_duration_range"]

        balanced_scenes = []
        for scene in scenes:
            # 범위 내로 조정
            new_duration = max(min_duration, min(scene.duration, max_duration))

            balanced_scene = SceneSpec(
                id=scene.id,
                purpose=scene.purpose,
                camera=scene.camera,
                mood=scene.mood,
                action=scene.action,
                characters=scene.characters.copy(),
                location=scene.location,
                dialogue=scene.dialogue,
                narration=scene.narration,
                duration=new_duration,
                emotion=scene.emotion
            )
            balanced_scenes.append(balanced_scene)

        return balanced_scenes

    def get_duration_report(self, scenes: List[SceneSpec]) -> Dict[str, Any]:
        """
        길이 리포트 생성

        Args:
            scenes: 씬 목록

        Returns:
            Dict: 길이 리포트
        """
        if not scenes:
            return {
                "total_duration": 0,
                "scene_count": 0,
                "average_duration": 0,
                "min_duration": 0,
                "max_duration": 0,
                "by_purpose": {}
            }

        durations = [s.duration for s in scenes]
        total = sum(durations)

        # 목적별 집계
        by_purpose = {}
        for purpose in ScenePurpose:
            purpose_scenes = [s for s in scenes if s.purpose == purpose]
            if purpose_scenes:
                by_purpose[purpose.value] = {
                    "count": len(purpose_scenes),
                    "total_duration": sum(s.duration for s in purpose_scenes),
                    "average_duration": sum(s.duration for s in purpose_scenes) / len(purpose_scenes)
                }

        return {
            "total_duration": total,
            "scene_count": len(scenes),
            "average_duration": total / len(scenes),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "by_purpose": by_purpose
        }
