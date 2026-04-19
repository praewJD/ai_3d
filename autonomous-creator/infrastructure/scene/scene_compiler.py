"""
SceneCompiler - 스토리 텍스트를 SceneGraph로 변환

LLM을 사용하여 자연어 스토리를 구조화된 장면 데이터로 변환
"""
import json
import uuid
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from core.domain.entities.scene import (
    SceneGraph,
    SceneNode,
    SceneStyle,
    StyleType,
    DialogueLine,
    CameraAngle,
    ActionType,
    Mood,
    Transition
)
from infrastructure.validation.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


def _extract_json_from_response(response: str) -> str:
    """
    LLM 응답에서 JSON 추출

    마크다운 코드 블록 또는 일반 텍스트에서 JSON 추출
    """
    response = response.strip()

    # 마크다운 코드 블록에서 JSON 추출
    if "```" in response:
        # ```json ... ``` 또는 ``` ... ``` 패턴
        lines = response.split("\n")
        json_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                if in_code_block:
                    break  # 코드 블록 끝
                in_code_block = True
                # ```json 같은 경우 언어 식별자 제거
                continue
            if in_code_block:
                json_lines.append(line)

        if json_lines:
            return "\n".join(json_lines)

    # 중괄호로 시작하는 JSON 찾기
    start_idx = response.find("{")
    if start_idx != -1:
        # 마지막 } 찾기
        end_idx = response.rfind("}")
        if end_idx != -1:
            return response[start_idx:end_idx + 1]

    return response


# JSON Schema for LLM output validation
SCENE_GRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": "string"},
                    "camera_angle": {"type": "string"},
                    "action": {"type": "string"},
                    "mood": {"type": "string"},
                    "dialogue": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "character_id": {"type": "string"},
                                "text": {"type": "string"},
                                "emotion": {"type": "string"}
                            },
                            "required": ["character_id", "text"]
                        }
                    },
                    "narration": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                    "transition_in": {"type": "string"},
                    "transition_out": {"type": "string"}
                },
                "required": ["description"]
            },
            "minItems": 1
        },
        "art_style": {"type": "string"}
    },
    "required": ["scenes"]
}


@dataclass
class CompilationResult:
    """컴파일 결과"""
    success: bool
    scene_graph: Optional[SceneGraph] = None
    raw_response: str = ""
    errors: List[str] = None
    fixes_applied: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SceneCompiler:
    """
    스토리 컴파일러

    자연어 스토리를 SceneGraph로 변환
    """

    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: IAIProvider 구현체
        """
        self.llm = llm_provider
        self.rule_engine = RuleEngine()

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 생성"""
        return """You are a professional story-to-scene converter for animated video production.

Your task is to convert a story text into a structured scene graph for video generation.

## Output Format
Return ONLY valid JSON with this structure:
{
    "title": "Story title",
    "art_style": "Disney 3D animation style, Pixar quality",
    "scenes": [
        {
            "description": "Visual description of the scene",
            "characters": ["character_1", "character_2"],
            "location": "scene location",
            "camera_angle": "medium_shot",
            "action": "walking",
            "mood": "happy",
            "dialogue": [
                {"character_id": "character_1", "text": "Hello!", "emotion": "happy"}
            ],
            "narration": "Narrator text",
            "duration_seconds": 5.0,
            "transition_in": "fade",
            "transition_out": "crossfade"
        }
    ]
}

## Camera Angles
- close-up: Face/emotion focus
- medium_shot: Upper body, conversation
- wide_shot: Full scene, environment
- bird_eye: Aerial view
- low_angle: Dramatic, powerful
- over_shoulder: POV conversation
- pov: First person view

## Actions
- idle, walking, running, talking, fighting, dancing, sitting, standing

## Moods
- happy, sad, neutral, tense, romantic, mysterious, excited, peaceful, scary, dramatic

## Transitions
- cut: Instant change
- fade: Fade to black
- crossfade: Blend scenes
- wipe: Slide transition
- dissolve: Gradual blend
- zoom: Zoom in/out

## Rules
1. Each scene must have a unique description
2. Duration should be 2-10 seconds (default 5)
3. Use appropriate camera angles for the action
4. Ensure smooth transitions between locations
5. Keep dialogue concise (max 2-3 lines per scene)"""

    def _build_user_prompt(self, story_text: str, context: Dict[str, Any] = None) -> str:
        """사용자 프롬프트 생성"""
        prompt = f"Convert this story into a scene graph:\n\n{story_text}"

        if context:
            if context.get("characters"):
                prompt += f"\n\nCharacters: {', '.join(context['characters'])}"
            if context.get("style"):
                prompt += f"\nStyle: {context['style']}"
            if context.get("max_scenes"):
                prompt += f"\nMax scenes: {context['max_scenes']}"

        return prompt

    def _generate_story_id(self) -> str:
        """스토리 ID 생성"""
        return f"story_{uuid.uuid4().hex[:8]}"

    def _validate_json_schema(self, data: Dict[str, Any]) -> List[str]:
        """JSON 스키마 검증"""
        errors = []

        if "scenes" not in data:
            errors.append("Missing required field: scenes")
            return errors

        if not isinstance(data["scenes"], list):
            errors.append("scenes must be an array")
            return errors

        if len(data["scenes"]) == 0:
            errors.append("scenes array cannot be empty")
            return errors

        for i, scene in enumerate(data["scenes"]):
            if not isinstance(scene, dict):
                errors.append(f"Scene {i} must be an object")
                continue

            if "description" not in scene:
                errors.append(f"Scene {i} missing required field: description")

        return errors

    def _parse_scene_node(self, data: Dict[str, Any], index: int) -> SceneNode:
        """SceneNode 파싱"""
        scene_id = f"scene_{index:03d}"

        # Enum 변환 (안전하게)
        try:
            camera = CameraAngle(data.get("camera_angle", "medium_shot"))
        except ValueError:
            camera = CameraAngle.MEDIUM

        try:
            action = ActionType(data.get("action", "idle"))
        except ValueError:
            action = ActionType.IDLE

        try:
            mood = Mood(data.get("mood", "neutral"))
        except ValueError:
            mood = Mood.NEUTRAL

        try:
            transition_in = Transition(data.get("transition_in", "fade"))
        except ValueError:
            transition_in = Transition.FADE

        try:
            transition_out = Transition(data.get("transition_out", "fade"))
        except ValueError:
            transition_out = Transition.FADE

        # Dialogue 파싱
        dialogue = []
        for d in data.get("dialogue", []):
            if isinstance(d, dict):
                dialogue.append(DialogueLine(
                    character_id=d.get("character_id", "unknown"),
                    text=d.get("text", ""),
                    emotion=d.get("emotion", "neutral")
                ))

        return SceneNode(
            scene_id=scene_id,
            description=data.get("description", ""),
            characters=data.get("characters", []),
            location=data.get("location", ""),
            camera_angle=camera,
            action=action,
            mood=mood,
            dialogue=dialogue,
            narration=data.get("narration", ""),
            duration_seconds=float(data.get("duration_seconds", 5.0)),
            transition_in=transition_in,
            transition_out=transition_out,
            order=index
        )

    async def compile(
        self,
        story_text: str,
        context: Dict[str, Any] = None,
        auto_fix: bool = True
    ) -> CompilationResult:
        """
        스토리 텍스트를 SceneGraph로 컴파일

        Args:
            story_text: 스토리 텍스트
            context: 추가 컨텍스트 (characters, style, max_scenes 등)
            auto_fix: 자동 수정 여부

        Returns:
            CompilationResult
        """
        if not self.llm:
            return CompilationResult(
                success=False,
                errors=["LLM provider not configured"]
            )

        try:
            # LLM 호출
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(story_text, context)

            logger.info("Calling LLM for scene compilation...")
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt
            )

            # JSON 파싱
            try:
                # 마크다운 코드 블록에서 JSON 추출
                json_str = _extract_json_from_response(response)
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                logger.debug(f"Raw response: {response[:500]}...")
                return CompilationResult(
                    success=False,
                    raw_response=response,
                    errors=[f"Invalid JSON: {str(e)}"]
                )

            # 스키마 검증
            schema_errors = self._validate_json_schema(data)
            if schema_errors:
                logger.warning(f"Schema validation errors: {schema_errors}")

            # SceneGraph 생성
            story_id = self._generate_story_id()
            scenes = [
                self._parse_scene_node(s, i)
                for i, s in enumerate(data.get("scenes", []))
            ]

            # 아트 스타일 문자열을 SceneStyle로 변환
            art_style_str = data.get("art_style", "Disney 3D animation style, Pixar quality")

            # 스타일 타입 감지
            style_type = StyleType.DISNEY_3D  # 기본값
            if "anime" in art_style_str.lower() or "2d" in art_style_str.lower():
                style_type = StyleType.ANIME
            elif "realistic" in art_style_str.lower() or "photo" in art_style_str.lower():
                style_type = StyleType.REALISTIC

            scene_graph = SceneGraph(
                story_id=story_id,
                title=data.get("title", "Untitled"),
                scenes=scenes,
                default_style=SceneStyle(type=style_type)
            )

            # Rule Engine 검증/수정
            if auto_fix:
                scene_graph, validation = self.rule_engine.validate_and_fix(scene_graph)
                fixes = validation.fixed_count
            else:
                validation = self.rule_engine.validate(scene_graph)
                fixes = 0

            return CompilationResult(
                success=validation.is_valid,
                scene_graph=scene_graph,
                raw_response=response,
                errors=validation.errors if not validation.is_valid else [],
                fixes_applied=fixes
            )

        except Exception as e:
            logger.exception("Compilation failed")
            return CompilationResult(
                success=False,
                errors=[str(e)]
            )

    def compile_from_dict(self, data: Dict[str, Any]) -> CompilationResult:
        """
        딕셔너리에서 SceneGraph 생성

        Args:
            data: 이미 파싱된 딕셔너리

        Returns:
            CompilationResult
        """
        try:
            # 스키마 검증
            schema_errors = self._validate_json_schema(data)
            if schema_errors:
                return CompilationResult(
                    success=False,
                    errors=schema_errors
                )

            # SceneGraph 생성
            story_id = data.get("story_id", self._generate_story_id())
            scenes = [
                self._parse_scene_node(s, i)
                for i, s in enumerate(data.get("scenes", []))
            ]

            scene_graph = SceneGraph(
                story_id=story_id,
                title=data.get("title", "Untitled"),
                scenes=scenes,
                art_style=data.get("art_style", "Disney 3D animation style, Pixar quality")
            )

            # 검증
            scene_graph, validation = self.rule_engine.validate_and_fix(scene_graph)

            return CompilationResult(
                success=validation.is_valid,
                scene_graph=scene_graph,
                errors=validation.errors if not validation.is_valid else [],
                fixes_applied=validation.fixed_count
            )

        except Exception as e:
            logger.exception("Compilation from dict failed")
            return CompilationResult(
                success=False,
                errors=[str(e)]
            )


# 편의 함수
async def compile_story(
    story_text: str,
    llm_provider=None,
    context: Dict[str, Any] = None
) -> SceneGraph:
    """
    스토리 컴파일 편의 함수

    Args:
        story_text: 스토리 텍스트
        llm_provider: LLM 제공자
        context: 추가 컨텍스트

    Returns:
        SceneGraph

    Raises:
        ValueError: 컴파일 실패 시
    """
    compiler = SceneCompiler(llm_provider)
    result = await compiler.compile(story_text, context)

    if not result.success:
        raise ValueError(f"Compilation failed: {result.errors}")

    return result.scene_graph
