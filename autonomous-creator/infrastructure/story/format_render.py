"""
Format Render Engine - Shorts / Longform 변환 엔진

스토리를 다른 포맷으로 변환하는 렌더링 엔진
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
import copy
import uuid

from infrastructure.story.story_spec import (
    StorySpec, SceneSpec, ScenePurpose, TargetFormat,
    SHORTS_CONSTRAINTS, LONGFORM_CONSTRAINTS
)


@dataclass
class RenderedStory:
    """렌더링된 스토리"""
    story_spec: StorySpec
    format: TargetFormat
    total_duration: float
    scene_count: int
    compression_ratio: float = 1.0  # 압축률 (1.0 = 원본)
    expansion_ratio: float = 1.0  # 확장률
    changes: List[str] = None  # 변경 사항 목록

    def __post_init__(self):
        if self.changes is None:
            self.changes = []

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "story_spec": self.story_spec.to_dict(),
            "format": self.format.value,
            "total_duration": self.total_duration,
            "scene_count": self.scene_count,
            "compression_ratio": self.compression_ratio,
            "expansion_ratio": self.expansion_ratio,
            "changes": self.changes
        }


class FormatRenderEngine:
    """Shorts / Longform 변환 엔진"""

    def __init__(self):
        self.compressors: Dict[str, Callable] = {
            "duration": self._compress_by_duration,
            "scene": self._compress_by_scene_merge,
            "description": self._compress_descriptions
        }
        self.expanders: Dict[str, Callable] = {
            "scene": self._expand_by_scene_split,
            "description": self._expand_descriptions,
            "transition": self._add_transitions
        }

    def render(self, story_spec: StorySpec, target: TargetFormat) -> RenderedStory:
        """스토리를 타겟 포맷으로 렌더링"""
        # 현재 포맷과 동일하면 그대로 반환
        if story_spec.target == target:
            return RenderedStory(
                story_spec=story_spec,
                format=target,
                total_duration=story_spec.total_duration(),
                scene_count=len(story_spec.scenes)
            )

        # 포맷 변환
        if target == TargetFormat.SHORTS:
            return self._render_to_shorts(story_spec)
        else:
            return self._render_to_longform(story_spec)

    def _render_to_shorts(self, spec: StorySpec) -> RenderedStory:
        """Longform → Shorts 변환 (압축)"""
        constraints = SHORTS_CONSTRAINTS
        changes = []

        # 원본 씬 복사
        scenes = [copy.deepcopy(s) for s in spec.scenes]
        original_scene_count = len(scenes)

        # 1. 씬 수 압축
        if len(scenes) > constraints["max_scenes"]:
            scenes = self._compress_scenes(scenes, constraints["max_scenes"])
            changes.append(f"Compressed scenes: {original_scene_count} -> {len(scenes)}")

        # 2. Duration 조정
        total_duration = sum(s.duration for s in scenes)
        if total_duration > constraints["max_duration"]:
            scenes = self._adjust_durations(scenes, constraints["max_duration"])
            new_duration = sum(s.duration for s in scenes)
            changes.append(f"Adjusted duration: {total_duration:.1f}s -> {new_duration:.1f}s")

        # 3. Hook 강화 (Shorts는 Hook가 생명)
        scenes = self._strengthen_hook(scenes)
        changes.append("Hook strengthened for shorts")

        # 4. 설명 압축
        scenes = self._compress_descriptions(scenes)
        changes.append("Descriptions compressed")

        # 5. 새 StorySpec 생성
        new_spec = StorySpec(
            title=spec.title,
            genre=spec.genre,
            target=TargetFormat.SHORTS,
            duration=constraints["max_duration"],
            characters=[copy.deepcopy(c) for c in spec.characters],
            arc=copy.deepcopy(spec.arc),
            scenes=scenes,
            emotion_curve=spec.emotion_curve[:len(scenes)] if spec.emotion_curve else [],
            metadata=copy.deepcopy(spec.metadata)
        )

        compression_ratio = original_scene_count / len(scenes) if len(scenes) > 0 else 1.0

        return RenderedStory(
            story_spec=new_spec,
            format=TargetFormat.SHORTS,
            total_duration=sum(s.duration for s in scenes),
            scene_count=len(scenes),
            compression_ratio=compression_ratio,
            changes=changes
        )

    def _render_to_longform(self, spec: StorySpec) -> RenderedStory:
        """Shorts → Longform 변환 (확장)"""
        constraints = LONGFORM_CONSTRAINTS
        changes = []

        # 원본 씬 복사
        scenes = [copy.deepcopy(s) for s in spec.scenes]
        original_scene_count = len(scenes)

        # 1. 씬 확장
        if len(scenes) < constraints["min_scenes"]:
            scenes = self._expand_scenes(scenes, constraints["min_scenes"])
            changes.append(f"Expanded scenes: {original_scene_count} -> {len(scenes)}")

        # 2. 서브 갈등 추가
        scenes = self._add_sub_conflicts(scenes)
        changes.append("Added sub-conflicts for longform")

        # 3. 전환 씬 추가
        scenes = self._add_transition_scenes(scenes)
        changes.append("Added transition scenes")

        # 4. Duration 조정 - 각 씬이 최소 3초 이상이 되도록
        min_scene_duration = constraints.get("scene_duration_range", (3, 15))[0]
        for scene in scenes:
            if scene.duration < min_scene_duration:
                scene.duration = min_scene_duration

        # 5. 설명 확장
        scenes = self._expand_descriptions(scenes)
        changes.append("Descriptions expanded")

        # 6. 새 StorySpec 생성
        new_spec = StorySpec(
            title=spec.title,
            genre=spec.genre,
            target=TargetFormat.LONGFORM,
            duration=sum(s.duration for s in scenes),
            characters=[copy.deepcopy(c) for c in spec.characters],
            arc=copy.deepcopy(spec.arc),
            scenes=scenes,
            emotion_curve=self._expand_emotion_curve(spec.emotion_curve, len(scenes)),
            metadata=copy.deepcopy(spec.metadata)
        )

        expansion_ratio = len(scenes) / original_scene_count if original_scene_count > 0 else 1.0

        return RenderedStory(
            story_spec=new_spec,
            format=TargetFormat.LONGFORM,
            total_duration=sum(s.duration for s in scenes),
            scene_count=len(scenes),
            expansion_ratio=expansion_ratio,
            changes=changes
        )

    # ============================================================
    # 압축 메서드들 (Longform -> Shorts)
    # ============================================================

    def _compress_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """씬 압축 - 비슷한 씬 병합"""
        if len(scenes) <= target:
            return scenes

        # Hook와 Climax는 보존, Build 씬 병합
        preserved = []
        build_scenes = []

        for scene in scenes:
            if scene.purpose in [ScenePurpose.HOOK, ScenePurpose.CLIMAX]:
                preserved.append(scene)
            else:
                build_scenes.append(scene)

        # 병합할 수 있는 Build 씬 수 계산
        available_slots = target - len(preserved)

        if available_slots <= 0:
            # 보존할 씬만으로도 타겟 초과 - 중요도 순으로 선택
            return self._select_important_scenes(scenes, target)

        # Build 씬 병합
        merged_builds = self._merge_build_scenes(build_scenes, available_slots)

        # 보존된 씬과 병합된 Build 씬 결합 (순서 유지)
        result = []
        preserved_idx = 0
        merged_idx = 0

        for scene in scenes:
            if scene.purpose in [ScenePurpose.HOOK, ScenePurpose.CLIMAX]:
                if preserved_idx < len(preserved):
                    result.append(preserved[preserved_idx])
                    preserved_idx += 1
            else:
                if merged_idx < len(merged_builds):
                    result.append(merged_builds[merged_idx])
                    merged_idx += 1

        return result[:target]

    def _select_important_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """중요도 순으로 씬 선택"""
        # 우선순위: Hook > Climax > Resolution > Build
        priority_order = {
            ScenePurpose.HOOK: 0,
            ScenePurpose.CLIMAX: 1,
            ScenePurpose.RESOLUTION: 2,
            ScenePurpose.BUILD: 3
        }

        sorted_scenes = sorted(scenes, key=lambda s: priority_order.get(s.purpose, 99))
        return sorted_scenes[:target]

    def _merge_build_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """Build 씬 병합"""
        if not scenes or target <= 0:
            return []

        if len(scenes) <= target:
            return scenes

        result = []
        merge_size = len(scenes) // target if target > 0 else len(scenes)

        for i in range(0, len(scenes), merge_size):
            chunk = scenes[i:i + merge_size]
            if len(result) < target:
                if len(chunk) == 1:
                    result.append(chunk[0])
                else:
                    # 여러 씬 병합
                    merged = self._merge_scene_list(chunk)
                    result.append(merged)

        return result[:target]

    def _merge_scene_list(self, scenes: List[SceneSpec]) -> SceneSpec:
        """여러 씬을 하나로 병합"""
        if not scenes:
            return SceneSpec(id="merged_empty")

        # 첫 번째 씬을 기준으로 병합
        merged = copy.deepcopy(scenes[0])
        merged.id = f"merged_{uuid.uuid4().hex[:8]}"

        # Duration 합산
        merged.duration = sum(s.duration for s in scenes)

        # 액션 병합
        actions = [s.action for s in scenes if s.action]
        if actions:
            merged.action = " -> ".join(actions[:3])  # 최대 3개

        # 대화 병합
        dialogues = [s.dialogue for s in scenes if s.dialogue]
        if dialogues:
            merged.dialogue = " / ".join(dialogues[:2])  # 최대 2개

        # 내레이션 병합
        narrations = [s.narration for s in scenes if s.narration]
        if narrations:
            merged.narration = " ... ".join(narrations[:2])  # 최대 2개

        # 등장인물 병합
        all_characters = set()
        for s in scenes:
            all_characters.update(s.characters)
        merged.characters = list(all_characters)

        return merged

    def _adjust_durations(self, scenes: List[SceneSpec], target_duration: int) -> List[SceneSpec]:
        """Duration 조정"""
        if not scenes:
            return scenes

        current_duration = sum(s.duration for s in scenes)
        if current_duration <= target_duration:
            return scenes

        # 비율 계산
        ratio = target_duration / current_duration

        # 각 씬의 duration 조정
        for scene in scenes:
            scene.duration = max(1.5, scene.duration * ratio)  # 최소 1.5초 보장

        return scenes

    def _strengthen_hook(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """Hook 강화"""
        if scenes and scenes[0].purpose == ScenePurpose.HOOK:
            # Hook는 3초 이내로 강력하게
            scenes[0].duration = min(scenes[0].duration, 3)

            # Hook 액션 강화
            if scenes[0].action:
                # 이미 강한 후크 액션이 있는지 확인
                hook_keywords = ["shock", "surprise", "reveal", "dramatic", "intense"]
                has_hook = any(kw in scenes[0].action.lower() for kw in hook_keywords)

                if not has_hook:
                    scenes[0].action = f"[HOOK] {scenes[0].action}"

            # Hook 내레이션 강화
            if scenes[0].narration and not scenes[0].narration.startswith("!"):
                scenes[0].narration = f"{scenes[0].narration}"

        return scenes

    def _compress_by_duration(self, scenes: List[SceneSpec], target_duration: int) -> List[SceneSpec]:
        """Duration 기반 압축"""
        return self._adjust_durations(scenes, target_duration)

    def _compress_by_scene_merge(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """씬 병합 기반 압축"""
        if len(scenes) <= 2:
            return scenes

        result = []
        i = 0
        while i < len(scenes):
            if i + 1 < len(scenes):
                # 두 씬 병합
                merged = self._merge_scene_list([scenes[i], scenes[i + 1]])
                result.append(merged)
                i += 2
            else:
                result.append(scenes[i])
                i += 1

        return result

    def _compress_descriptions(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """설명 압축"""
        for scene in scenes:
            # 액션 압축 (최대 100자)
            if len(scene.action) > 100:
                scene.action = scene.action[:97] + "..."

            # 대화 압축 (최대 80자)
            if len(scene.dialogue) > 80:
                scene.dialogue = scene.dialogue[:77] + "..."

            # 내레이션 압축 (최대 60자)
            if len(scene.narration) > 60:
                scene.narration = scene.narration[:57] + "..."

        return scenes

    # ============================================================
    # 확장 메서드들 (Shorts -> Longform)
    # ============================================================

    def _expand_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """씬 확장 - 씬 분할"""
        if len(scenes) >= target:
            return scenes

        result = []
        scenes_to_add = target - len(scenes)

        # 각 씬을 분할하여 확장
        for scene in scenes:
            result.append(scene)

            # 분할이 필요한 경우
            if scenes_to_add > 0 and scene.duration > 5:
                # 긴 씬을 분할
                split_scenes = self._split_scene(scene)
                if split_scenes:
                    result.extend(split_scenes)
                    scenes_to_add -= len(split_scenes)

        # 여전히 부족하면 일반 씬 추가
        while len(result) < target:
            new_scene = self._create_filler_scene(len(result))
            result.append(new_scene)

        return result

    def _split_scene(self, scene: SceneSpec) -> List[SceneSpec]:
        """씬 분할"""
        if scene.duration <= 5:
            return []

        # 2개로 분할
        half_duration = scene.duration / 2

        first_part = copy.deepcopy(scene)
        first_part.id = f"{scene.id}_part1"
        first_part.duration = half_duration

        second_part = copy.deepcopy(scene)
        second_part.id = f"{scene.id}_part2"
        second_part.duration = half_duration

        # 두 번째 파트는 BUILD 목적으로 변경
        if second_part.purpose == ScenePurpose.HOOK:
            second_part.purpose = ScenePurpose.BUILD

        return [first_part, second_part]

    def _create_filler_scene(self, index: int) -> SceneSpec:
        """빈 공간을 채우는 씬 생성"""
        return SceneSpec(
            id=f"filler_{index}",
            purpose=ScenePurpose.BUILD,
            action="Transition moment",
            duration=5.0,
            mood="neutral",
            emotion="neutral"
        )

    def _add_sub_conflicts(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """서브 갈등 추가"""
        if len(scenes) < 3:
            return scenes

        result = []

        # Build 씬 사이에 서브 갈등 씬 추가
        for i, scene in enumerate(scenes):
            result.append(scene)

            # BUILD 씬 다음에 서브 갈등 추가 (마지막 씬 제외)
            if (scene.purpose == ScenePurpose.BUILD and
                i < len(scenes) - 1 and
                i % 3 == 1):  # 3개 중 1개 꼴로 추가

                sub_conflict = SceneSpec(
                    id=f"subconflict_{i}",
                    purpose=ScenePurpose.BUILD,
                    action="Minor obstacle appears",
                    duration=4.0,
                    mood="tense",
                    emotion="anxiety"
                )
                result.append(sub_conflict)

        return result

    def _add_transition_scenes(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """전환 씬 추가"""
        if len(scenes) < 2:
            return scenes

        result = []

        for i, scene in enumerate(scenes):
            result.append(scene)

            # 씬 사이에 전환 씬 추가 (마지막 제외)
            if i < len(scenes) - 1:
                next_scene = scenes[i + 1]

                # 장소가 다르면 전환 씬 추가
                if (scene.location and next_scene.location and
                    scene.location != next_scene.location):

                    transition = SceneSpec(
                        id=f"transition_{i}",
                        purpose=ScenePurpose.BUILD,
                        action=f"Moving from {scene.location} to {next_scene.location}",
                        duration=2.0,
                        mood="neutral",
                        emotion="neutral"
                    )
                    result.append(transition)

        return result

    def _expand_by_scene_split(self, scenes: List[SceneSpec], factor: int) -> List[SceneSpec]:
        """씬 분할 기반 확장"""
        result = []
        for scene in scenes:
            result.append(scene)
            for j in range(factor - 1):
                new_scene = copy.deepcopy(scene)
                new_scene.id = f"{scene.id}_exp{j + 1}"
                new_scene.duration = scene.duration / factor
                result.append(new_scene)
        return result

    def _expand_descriptions(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """설명 확장"""
        for scene in scenes:
            # 액션 확장 - 더 상세하게
            if scene.action and len(scene.action) < 50:
                scene.action = f"Detailed: {scene.action}"

            # 분위기 추가
            if scene.mood == "neutral":
                scene.mood = "contemplative"

        return scenes

    def _add_transitions(self, scenes: List[SceneSpec]) -> List[SceneSpec]:
        """전환 씬 추가"""
        return self._add_transition_scenes(scenes)

    def _expand_emotion_curve(self, curve: List[float], target_length: int) -> List[float]:
        """감정 곡선 확장"""
        if not curve:
            # 기본 감정 곡선 생성
            return self._create_default_emotion_curve(target_length)

        if len(curve) >= target_length:
            return curve[:target_length]

        # 선형 보간으로 확장
        result = []
        ratio = len(curve) / target_length if target_length > 0 else 1

        for i in range(target_length):
            # 원본 인덱스 계산
            src_idx = i * ratio
            lower_idx = int(src_idx)
            upper_idx = min(lower_idx + 1, len(curve) - 1)

            # 선형 보간
            fraction = src_idx - lower_idx
            interpolated = curve[lower_idx] * (1 - fraction) + curve[upper_idx] * fraction
            result.append(round(interpolated, 2))

        return result

    def _create_default_emotion_curve(self, length: int) -> List[float]:
        """기본 감정 곡선 생성"""
        if length <= 0:
            return []

        # 0에서 시작 -> 점진적 상승 -> 절정 -> 하강
        curve = []
        for i in range(length):
            progress = i / (length - 1) if length > 1 else 0.5

            # 피크는 70% 지점
            peak_point = 0.7

            if progress < peak_point:
                # 상승 구간
                value = progress / peak_point
            else:
                # 하강 구간
                value = 1.0 - (progress - peak_point) / (1.0 - peak_point) * 0.3

            curve.append(round(value, 2))

        return curve


# ============================================================
# LLM 기반 고급 렌더링
# ============================================================

class LLMFormatRenderEngine(FormatRenderEngine):
    """LLM을 활용한 고급 포맷 변환 엔진"""

    def __init__(self, llm_provider=None):
        super().__init__()
        self.llm_provider = llm_provider

    async def render_with_llm(
        self,
        story_spec: StorySpec,
        target: TargetFormat,
        llm_provider=None
    ) -> RenderedStory:
        """LLM으로 정교한 포맷 변환"""
        provider = llm_provider or self.llm_provider

        # LLM이 없으면 기본 렌더링 사용
        if not provider:
            return self.render(story_spec, target)

        # 동일 포맷이면 그대로 반환
        if story_spec.target == target:
            return RenderedStory(
                story_spec=story_spec,
                format=target,
                total_duration=story_spec.total_duration(),
                scene_count=len(story_spec.scenes)
            )

        # LLM 프롬프트 생성
        constraints = SHORTS_CONSTRAINTS if target == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS

        prompt = f"""
Convert this story from {story_spec.target.value} to {target.value}:

Current scenes: {len(story_spec.scenes)}
Current duration: {story_spec.total_duration()}s

Target constraints:
- Min duration: {constraints['min_duration']}s
- Max duration: {constraints['max_duration']}s
- Min scenes: {constraints['min_scenes']}
- Max scenes: {constraints['max_scenes']}

Story JSON:
{story_spec.to_json()}

Return the adapted story as JSON with the same schema.
Optimize for {target.value} engagement.
Keep the same story structure but adjust pacing, descriptions, and scene count.

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.
"""

        try:
            # LLM 호출
            response = await provider.generate(prompt)

            # JSON 파싱
            import json
            new_spec_dict = json.loads(response)

            # StorySpec 생성
            new_spec = StorySpec.from_dict(new_spec_dict)
            new_spec.target = target

            return RenderedStory(
                story_spec=new_spec,
                format=target,
                total_duration=new_spec.total_duration(),
                scene_count=len(new_spec.scenes),
                compression_ratio=len(story_spec.scenes) / len(new_spec.scenes)
                    if target == TargetFormat.SHORTS and len(new_spec.scenes) > 0 else 1.0,
                expansion_ratio=len(new_spec.scenes) / len(story_spec.scenes)
                    if target == TargetFormat.LONGFORM and len(story_spec.scenes) > 0 else 1.0,
                changes=[f"LLM-optimized conversion to {target.value}"]
            )

        except Exception as e:
            # LLM 실패 시 기본 렌더링으로 폴백
            print(f"LLM rendering failed: {e}, falling back to basic rendering")
            return self.render(story_spec, target)

    def render(self, story_spec: StorySpec, target: TargetFormat) -> RenderedStory:
        """동기 렌더링 (기본 구현 사용)"""
        return super().render(story_spec, target)
