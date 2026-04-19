"""
Scene Generator - Arc to Scene List Converter

4-Act Arc를 Scene 리스트로 변환하는 모듈
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import time
import random
import logging

from .story_spec import (
    SceneSpec, ScenePurpose, TargetFormat,
    SHORTS_CONSTRAINTS, LONGFORM_CONSTRAINTS
)
from .arc_builder import ArcResult
from .budget_planner import BudgetPlan
from .normalizer import NormalizedInput
from .topic_generator import TopicResult

logger = logging.getLogger(__name__)


@dataclass
class SceneGenerationResult:
    """씬 생성 결과"""
    scenes: List[SceneSpec]
    total_duration: float
    scene_count: int
    generation_time: float
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "scenes": [s.to_dict() for s in self.scenes],
            "total_duration": self.total_duration,
            "scene_count": self.scene_count,
            "generation_time": self.generation_time,
            "errors": self.errors
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneGenerationResult":
        """딕셔너리에서 생성"""
        scenes = [SceneSpec.from_dict(s) for s in data.get("scenes", [])]
        return cls(
            scenes=scenes,
            total_duration=data.get("total_duration", 0.0),
            scene_count=data.get("scene_count", 0),
            generation_time=data.get("generation_time", 0.0),
            errors=data.get("errors", [])
        )


class SceneGenerator:
    """Arc -> Scene List 변환"""

    # 감정 -> 카메라 매핑
    EMOTION_CAMERA_MAP = {
        "shock": "close-up",
        "tension": "medium",
        "action": "wide",
        "sadness": "close-up",
        "joy": "medium",
        "fear": "close-up",
        "mystery": "medium",
        "climax": "wide",
        "anger": "close-up",
        "surprise": "close-up",
        "love": "close-up",
        "hope": "medium",
        "despair": "close-up",
        "neutral": "medium"
    }

    # 감정 -> 무드 매핑
    EMOTION_MOOD_MAP = {
        "shock": "dramatic",
        "tension": "dark",
        "action": "intense",
        "sadness": "melancholic",
        "joy": "bright",
        "fear": "scary",
        "mystery": "mysterious",
        "climax": "epic",
        "anger": "intense",
        "surprise": "dramatic",
        "love": "romantic",
        "hope": "bright",
        "despair": "dark",
        "neutral": "neutral"
    }

    # 목적별 기본 duration
    PURPOSE_DURATIONS = {
        ScenePurpose.HOOK: 3,
        ScenePurpose.BUILD: 4,
        ScenePurpose.CLIMAX: 3,
        ScenePurpose.RESOLUTION: 4
    }

    # 액션 동사 리스트
    ACTION_VERBS = [
        "fight", "run", "jump", "fall", "explode", "speak", "look", "move",
        "walk", "sit", "stand", "turn", "reach", "grab", "throw", "catch",
        "hide", "reveal", "point", "shake", "nod", "smile", "cry", "laugh",
        "idle"
    ]

    def __init__(self, llm_provider=None):
        """
        초기화

        Args:
            llm_provider: LLM 제공자 (선택적)
        """
        self.llm = llm_provider

    def generate(
        self,
        arc: ArcResult,
        budget: BudgetPlan,
        topic: TopicResult,
        normalized: NormalizedInput
    ) -> SceneGenerationResult:
        """
        아크를 씬 리스트로 변환

        Args:
            arc: 아크 결과
            budget: 예산 계획
            topic: 주제 결과
            normalized: 정규화된 입력

        Returns:
            SceneGenerationResult: 생성된 씬 결과
        """
        start_time = time.time()
        scenes = []
        errors = []

        try:
            # 1. Hook 씬 생성
            hook_scenes = self._generate_hook_scenes(arc.hook, budget.hook_scenes, normalized)
            scenes.extend(hook_scenes)

            # 2. Build 씬 생성
            build_scenes = self._generate_build_scenes(arc.build, budget.build_scenes, normalized)
            scenes.extend(build_scenes)

            # 3. Climax 씬 생성
            climax_scenes = self._generate_climax_scenes(arc.climax, budget.climax_scenes, normalized)
            scenes.extend(climax_scenes)

            # 4. Resolution 씬 생성
            resolution_scenes = self._generate_resolution_scenes(arc.resolution, budget.resolution_scenes, normalized)
            scenes.extend(resolution_scenes)

            # 5. ID 및 순서 부여
            for i, scene in enumerate(scenes):
                scene.id = str(i + 1)

            # 6. 예산에 맞게 조정
            scenes = self.adjust_to_budget(scenes, budget)

        except Exception as e:
            errors.append(f"Scene generation error: {str(e)}")
            logger.error(f"Scene generation failed: {e}")

        generation_time = time.time() - start_time

        return SceneGenerationResult(
            scenes=scenes,
            total_duration=sum(s.duration for s in scenes),
            scene_count=len(scenes),
            generation_time=generation_time,
            errors=errors
        )

    def _generate_hook_scenes(self, hook_text: str, count: int, normalized: NormalizedInput) -> List[SceneSpec]:
        """
        Hook 씬 생성 (항상 강하게)

        Args:
            hook_text: Hook 텍스트
            count: 생성할 씬 수
            normalized: 정규화된 입력

        Returns:
            List[SceneSpec]: Hook 씬 리스트
        """
        scenes = []

        for i in range(count):
            # Hook는 항상 강한 임팩트
            emotion = "shock"
            camera = self.EMOTION_CAMERA_MAP.get(emotion, "close-up")
            mood = "dramatic"

            scene = SceneSpec(
                id="0",  # 나중에 재설정
                purpose=ScenePurpose.HOOK,
                camera=camera,
                mood=mood,
                action=self._extract_action(hook_text),
                characters=normalized.characters[:2] if normalized.characters else [],
                location=normalized.setting,
                duration=self.PURPOSE_DURATIONS[ScenePurpose.HOOK],
                emotion=emotion
            )
            scene.description = hook_text
            scenes.append(scene)

        return scenes

    def _generate_build_scenes(self, build_text: str, count: int, normalized: NormalizedInput) -> List[SceneSpec]:
        """
        Build 씬 생성 (갈등 고조)

        Args:
            build_text: Build 텍스트
            count: 생성할 씬 수
            normalized: 정규화된 입력

        Returns:
            List[SceneSpec]: Build 씬 리스트
        """
        scenes = []

        # Build 단계에서 감정 변화 (점점 긴장감 증가)
        build_emotions = ["mystery", "tension", "tension", "fear"]

        for i in range(count):
            # 인덱스에 따라 감정 선택 (순환)
            emotion = build_emotions[i % len(build_emotions)]
            camera = self._determine_camera(ScenePurpose.BUILD, emotion)
            mood = self._determine_mood(emotion)

            scene = SceneSpec(
                id="0",
                purpose=ScenePurpose.BUILD,
                camera=camera,
                mood=mood,
                action=self._extract_action(build_text),
                characters=self._select_characters(normalized.characters, i),
                location=normalized.setting,
                duration=self.PURPOSE_DURATIONS[ScenePurpose.BUILD] + (i * 0.5),  # 점점 길어짐
                emotion=emotion
            )
            scene.description = self._generate_description(build_text, i, count)
            scenes.append(scene)

        return scenes

    def _generate_climax_scenes(self, climax_text: str, count: int, normalized: NormalizedInput) -> List[SceneSpec]:
        """
        Climax 씬 생성 (절정)

        Args:
            climax_text: Climax 텍스트
            count: 생성할 씬 수
            normalized: 정규화된 입력

        Returns:
            List[SceneSpec]: Climax 씬 리스트
        """
        scenes = []

        # Climax는 강렬한 감정
        climax_emotions = ["action", "climax", "shock"]

        for i in range(count):
            emotion = climax_emotions[i % len(climax_emotions)]
            camera = self._determine_camera(ScenePurpose.CLIMAX, emotion)
            mood = self._determine_mood(emotion)

            scene = SceneSpec(
                id="0",
                purpose=ScenePurpose.CLIMAX,
                camera=camera,
                mood=mood,
                action=self._extract_action(climax_text),
                characters=normalized.characters if normalized.characters else [],
                location=normalized.setting,
                duration=self.PURPOSE_DURATIONS[ScenePurpose.CLIMAX],
                emotion=emotion
            )
            scene.description = self._generate_description(climax_text, i, count)
            scenes.append(scene)

        return scenes

    def _generate_resolution_scenes(self, resolution_text: str, count: int, normalized: NormalizedInput) -> List[SceneSpec]:
        """
        Resolution 씬 생성 (해결/여운)

        Args:
            resolution_text: Resolution 텍스트
            count: 생성할 씬 수
            normalized: 정규화된 입력

        Returns:
            List[SceneSpec]: Resolution 씬 리스트
        """
        scenes = []

        # Resolution은 안정감/여운
        resolution_emotions = ["hope", "joy", "sadness", "neutral"]

        for i in range(count):
            emotion = resolution_emotions[i % len(resolution_emotions)]
            camera = self._determine_camera(ScenePurpose.RESOLUTION, emotion)
            mood = self._determine_mood(emotion)

            scene = SceneSpec(
                id="0",
                purpose=ScenePurpose.RESOLUTION,
                camera=camera,
                mood=mood,
                action=self._extract_action(resolution_text),
                characters=normalized.characters[:2] if normalized.characters else [],
                location=normalized.setting,
                duration=self.PURPOSE_DURATIONS[ScenePurpose.RESOLUTION],
                emotion=emotion
            )
            scene.description = self._generate_description(resolution_text, i, count)
            scenes.append(scene)

        return scenes

    def _extract_action(self, text: str) -> str:
        """
        텍스트에서 액션 추출

        Args:
            text: 원본 텍스트

        Returns:
            str: 추출된 액션
        """
        if not text:
            return "idle"

        text_lower = text.lower()
        for verb in self.ACTION_VERBS:
            if verb in text_lower:
                return verb
        return "idle"

    def _determine_camera(self, purpose: ScenePurpose, emotion: str) -> str:
        """
        목적과 감정에 따른 카메라 결정

        Args:
            purpose: 씬 목적
            emotion: 감정

        Returns:
            str: 카메라 타입
        """
        # 감정 기반 매핑 우선
        if emotion in self.EMOTION_CAMERA_MAP:
            return self.EMOTION_CAMERA_MAP[emotion]

        # 목적 기반 기본값
        if purpose == ScenePurpose.HOOK:
            return "close-up"
        elif purpose == ScenePurpose.BUILD:
            return "medium"
        elif purpose == ScenePurpose.CLIMAX:
            return "wide"
        elif purpose == ScenePurpose.RESOLUTION:
            return "medium"

        return "medium"

    def _determine_mood(self, emotion: str) -> str:
        """
        감정에 따른 무드 결정

        Args:
            emotion: 감정

        Returns:
            str: 무드
        """
        return self.EMOTION_MOOD_MAP.get(emotion, "neutral")

    def _select_characters(self, characters: List[str], index: int) -> List[str]:
        """
        인덱스에 따라 캐릭터 선택

        Args:
            characters: 캐릭터 리스트
            index: 현재 인덱스

        Returns:
            List[str]: 선택된 캐릭터들
        """
        if not characters:
            return []

        # 2명 이하면 전체 반환
        if len(characters) <= 2:
            return characters

        # 인덱스에 따라 다양한 조합
        if index % 2 == 0:
            return characters[:2]
        else:
            return characters[1:3] if len(characters) > 2 else characters[:2]

    def _generate_description(self, text: str, index: int, total: int) -> str:
        """
        씬 설명 생성

        Args:
            text: 원본 텍스트
            index: 현재 인덱스
            total: 전체 씬 수

        Returns:
            str: 생성된 설명
        """
        if not text:
            return ""

        # 텍스트가 길면 분할
        if len(text) > 100 and total > 1:
            # 간단한 분할 로직
            chunk_size = len(text) // total
            start = index * chunk_size
            end = start + chunk_size if index < total - 1 else len(text)
            return text[start:end].strip()

        return text

    def adjust_to_budget(self, scenes: List[SceneSpec], budget: BudgetPlan) -> List[SceneSpec]:
        """
        예산에 맞게 씬 조정

        Args:
            scenes: 원본 씬 리스트
            budget: 예산 계획

        Returns:
            List[SceneSpec]: 조정된 씬 리스트
        """
        if not scenes:
            return scenes

        # 씬이 너무 많으면 압축
        if len(scenes) > budget.scene_count:
            return self._compress_scenes(scenes, budget.scene_count)
        # 씬이 너무 적으면 확장
        elif len(scenes) < budget.scene_count:
            return self._expand_scenes(scenes, budget.scene_count)

        return scenes

    def _compress_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """
        씬 압축

        Args:
            scenes: 원본 씬 리스트
            target: 목표 씬 수

        Returns:
            List[SceneSpec]: 압축된 씬 리스트
        """
        if target <= 0 or len(scenes) <= target:
            return scenes

        compressed = []

        # 목적별로 그룹화
        purpose_groups = {
            ScenePurpose.HOOK: [],
            ScenePurpose.BUILD: [],
            ScenePurpose.CLIMAX: [],
            ScenePurpose.RESOLUTION: []
        }

        for scene in scenes:
            purpose_groups[scene.purpose].append(scene)

        # 각 목적에서 최소 1개는 유지
        for purpose, group in purpose_groups.items():
            if group:
                # 여러 씬이 있으면 병합
                if len(group) > 1:
                    merged = self._merge_scenes(group)
                    compressed.append(merged)
                else:
                    compressed.append(group[0])

        # ID 재부여
        for i, scene in enumerate(compressed):
            scene.id = str(i + 1)

        return compressed[:target]

    def _expand_scenes(self, scenes: List[SceneSpec], target: int) -> List[SceneSpec]:
        """
        씬 확장

        Args:
            scenes: 원본 씬 리스트
            target: 목표 씬 수

        Returns:
            List[SceneSpec]: 확장된 씬 리스트
        """
        if target <= len(scenes):
            return scenes

        expanded = scenes.copy()
        needed = target - len(scenes)

        # 기존 씬을 복제하여 확장
        for i in range(needed):
            # 원본 씬 선택 (순환)
            source_idx = i % len(scenes)
            source = scenes[source_idx]

            # 복제 및 변형
            new_scene = SceneSpec(
                id="0",
                purpose=source.purpose,
                camera=source.camera,
                mood=source.mood,
                action=source.action,
                characters=source.characters.copy(),
                location=source.location,
                duration=source.duration * 0.8,  # 약간 짧게
                emotion=source.emotion
            )
            new_scene.description = source.description if hasattr(source, 'description') else ""
            expanded.append(new_scene)

        # ID 재부여
        for i, scene in enumerate(expanded):
            scene.id = str(i + 1)

        return expanded

    def _merge_scenes(self, scenes: List[SceneSpec]) -> SceneSpec:
        """
        여러 씬을 하나로 병합

        Args:
            scenes: 병합할 씬 리스트

        Returns:
            SceneSpec: 병합된 씬
        """
        if not scenes:
            return None

        if len(scenes) == 1:
            return scenes[0]

        # 첫 번째 씬을 기반으로 병합
        base = scenes[0]

        # duration 합산
        total_duration = sum(s.duration for s in scenes)

        # 캐릭터 통합
        all_characters = []
        for s in scenes:
            all_characters.extend(s.characters)
        unique_characters = list(dict.fromkeys(all_characters))  # 순서 유지하며 중복 제거

        merged = SceneSpec(
            id=base.id,
            purpose=base.purpose,
            camera=base.camera,
            mood=base.mood,
            action=base.action,
            characters=unique_characters[:3],  # 최대 3명
            location=base.location,
            duration=total_duration,
            emotion=base.emotion
        )

        return merged


class LLMSceneGenerator(SceneGenerator):
    """LLM 기반 고급 씬 생성기"""

    SCENE_GENERATION_PROMPT = """You are a professional video director creating scenes for short-form content.

Create detailed scenes from this story arc:

Hook: {hook}
Build: {build}
Climax: {climax}
Resolution: {resolution}

Characters: {characters}
Setting: {setting}
Genre: {genre}

Target scene count: {scene_count}
Target format: {target_format}

Generate {scene_count} scenes with these fields for each:
- purpose: one of "hook", "build", "climax", "resolution"
- camera: one of "close-up", "medium", "wide", "bird_eye", "low_angle"
- mood: one of "dramatic", "dark", "bright", "mysterious", "intense", "romantic", "epic", "neutral"
- action: one of "idle", "walking", "running", "talking", "fighting", "sitting", "standing"
- description: visual description (1-2 sentences)
- duration: duration in seconds (2-5 for shorts, 3-8 for longform)
- emotion: the emotional tone of this scene

Return ONLY a valid JSON array of scene objects.
Example: [{{"purpose": "hook", "camera": "close-up", "mood": "dramatic", ...}}]

Important:
- Distribute scenes across all 4 purposes based on the arc
- Hook scenes must be attention-grabbing
- Ensure smooth emotional progression
- Make descriptions visual and actionable"""

    def __init__(self, llm_provider):
        """
        초기화

        Args:
            llm_provider: LLM 제공자 (필수)
        """
        super().__init__(llm_provider)

        if not llm_provider:
            raise ValueError("LLM Provider is required for LLMSceneGenerator")

    async def generate_with_llm(
        self,
        arc: ArcResult,
        budget: BudgetPlan,
        topic: TopicResult,
        normalized: NormalizedInput
    ) -> SceneGenerationResult:
        """
        LLM으로 정교한 씬 생성

        Args:
            arc: 아크 결과
            budget: 예산 계획
            topic: 주제 결과
            normalized: 정규화된 입력

        Returns:
            SceneGenerationResult: 생성된 씬 결과
        """
        import json

        start_time = time.time()
        errors = []

        try:
            # 프롬프트 구성
            prompt = self._build_prompt(arc, budget, topic, normalized)

            # LLM 호출
            llm_response = await self._call_llm(prompt)

            # 응답 파싱
            scene_data = self._parse_llm_response(llm_response)

            # SceneSpec 리스트로 변환
            scenes = []
            for i, data in enumerate(scene_data):
                try:
                    scene = self._create_scene_from_data(data, i + 1)
                    scenes.append(scene)
                except Exception as e:
                    errors.append(f"Failed to create scene {i + 1}: {str(e)}")

            # 예산에 맞게 조정
            scenes = self.adjust_to_budget(scenes, budget)

            generation_time = time.time() - start_time

            return SceneGenerationResult(
                scenes=scenes,
                total_duration=sum(s.duration for s in scenes),
                scene_count=len(scenes),
                generation_time=generation_time,
                errors=errors
            )

        except Exception as e:
            logger.warning(f"LLM scene generation failed, falling back to rule-based: {e}")
            errors.append(f"LLM generation failed: {str(e)}")

            # LLM 실패 시 기본 생성기로 폴백
            return self.generate(arc, budget, topic, normalized)

    def _build_prompt(
        self,
        arc: ArcResult,
        budget: BudgetPlan,
        topic: TopicResult,
        normalized: NormalizedInput
    ) -> str:
        """LLM 프롬프트 구성"""
        return self.SCENE_GENERATION_PROMPT.format(
            hook=arc.hook,
            build=arc.build,
            climax=arc.climax,
            resolution=arc.resolution,
            characters=", ".join(normalized.characters[:5]) if normalized.characters else "protagonist",
            setting=normalized.setting or "unknown location",
            genre=normalized.genre or "drama",
            scene_count=budget.scene_count,
            target_format=budget.target_format
        )

    async def _call_llm(self, prompt: str) -> str:
        """LLM API 호출"""
        if hasattr(self.llm, 'generate'):
            return await self.llm.generate(prompt)
        elif hasattr(self.llm, 'ainvoke'):
            return await self.llm.ainvoke(prompt)
        elif hasattr(self.llm, 'invoke'):
            return self.llm.invoke(prompt)
        else:
            raise ValueError("LLM provider does not have a valid generation method")

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """LLM 응답 파싱"""
        import json

        try:
            # JSON 블록 추출 시도
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                # 대괄호로 찾기
                start = response.find("[")
                end = response.rfind("]") + 1
                json_str = response[start:end]

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []

    def _create_scene_from_data(self, data: Dict[str, Any], scene_id: int) -> SceneSpec:
        """데이터로부터 SceneSpec 생성"""
        # purpose 변환
        purpose_str = data.get("purpose", "build").lower()
        try:
            purpose = ScenePurpose(purpose_str)
        except ValueError:
            purpose = ScenePurpose.BUILD

        scene = SceneSpec(
            id=str(scene_id),
            purpose=purpose,
            camera=data.get("camera", "medium"),
            mood=data.get("mood", "neutral"),
            action=data.get("action", "idle"),
            characters=data.get("characters", []),
            location=data.get("location", ""),
            duration=float(data.get("duration", 3.0)),
            emotion=data.get("emotion", "neutral")
        )
        scene.description = data.get("description", "")

        return scene

    async def enhance_scenes(
        self,
        scenes: List[SceneSpec],
        feedback: str = ""
    ) -> List[SceneSpec]:
        """
        기존 씬을 LLM으로 강화

        Args:
            scenes: 기존 씬 리스트
            feedback: 개선 피드백

        Returns:
            List[SceneSpec]: 강화된 씬 리스트
        """
        if not scenes:
            return scenes

        prompt = f"""Enhance these scenes for better engagement:

Current scenes:
{self._scenes_to_json(scenes)}

Feedback: {feedback if feedback else "Make scenes more visually compelling and emotionally engaging"}

Return improved scenes as JSON array with the same structure."""

        try:
            response = await self._call_llm(prompt)
            enhanced_data = self._parse_llm_response(response)

            enhanced_scenes = []
            for i, data in enumerate(enhanced_data):
                scene = self._create_scene_from_data(data, i + 1)
                enhanced_scenes.append(scene)

            return enhanced_scenes if enhanced_scenes else scenes

        except Exception as e:
            logger.warning(f"Scene enhancement failed: {e}")
            return scenes

    def _scenes_to_json(self, scenes: List[SceneSpec]) -> str:
        """씬 리스트를 JSON 문자열로 변환"""
        import json
        return json.dumps(
            [s.to_dict() for s in scenes],
            ensure_ascii=False,
            indent=2
        )
