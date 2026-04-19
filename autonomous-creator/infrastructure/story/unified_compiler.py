"""
Unified Story Compiler - LLM 1회 호출로 전체 스토리 컴파일

기존 6개 모듈(normalizer, topic_generator, arc_builder,
budget_planner, hook_enhancer, scene_generator)을
단일 LLM 호출로 대체.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .story_spec import (
    StorySpec, SceneSpec, CharacterSpec, ArcSpec,
    TargetFormat, ScenePurpose,
    SHORTS_CONSTRAINTS, LONGFORM_CONSTRAINTS,
)
from .story_validator import StoryValidator, ValidationResult, RetryPolicy, RetryLoop
from config.api_config import STORY_LANGUAGES
from infrastructure.tts.tts_config import LANGUAGE_NAMES, LANGUAGE_NATIVE_NAMES

logger = logging.getLogger(__name__)


@dataclass
class CompileResult:
    """컴파일 결과"""
    success: bool
    story_spec: Optional[StorySpec] = None
    hook_score: float = 0.0
    retry_count: int = 0
    error: str = ""


# ============================================================
# 프롬프트 상수
# ============================================================

SYSTEM_PROMPT = """You are a professional short-form video scriptwriter and story architect.
You transform rough story ideas into production-ready video scripts.

RULES:
1. Return ONLY valid JSON. No markdown, no explanation.
2. Fill in ANY missing details creatively — characters, settings, emotions, dialogue.
3. Every scene MUST have a clear visual description (action field).
4. Hook (first scene) must grab attention within 3 seconds.
5. All durations are in seconds.
6. Visual description fields (action, appearance, location, camera, mood) MUST be in English for image generation AI.
7. Dialogue, narration, and title should be in the target language specified in the prompt.
8. NEVER describe screens, text messages, UI elements, or written content in the "action" field. SDXL cannot render text.
9. Instead of describing what a screen shows, describe the CHARACTER'S REACTION: facial expression, body language, emotion, lighting.
   BAD: "phone screen showing message 'I love you'"
   GOOD: "man's shocked expression illuminated by phone glow in dark room, trembling hands"
   BAD: "KakaoTalk chat log showing messages"
   GOOD: "woman staring at phone with pale face, tears forming in her eyes, dramatic side lighting"
10. Focus "action" on: facial expressions, body language, physical actions, camera angles, lighting, atmosphere."""

SHORTS_PROMPT = """Given this rough story idea, create a complete video script for YouTube Shorts (vertical short-form video).

INPUT STORY:
{raw_story}

TARGET: YouTube Shorts
CONSTRAINTS:
- Total duration: 20~35 seconds
- Scene count: 6~10 scenes
- Each scene: 2~4 seconds
- First scene (Hook): exactly 3 seconds, must be attention-grabbing
- Hook must score ≥6.0/10 on: curiosity(2.5) + shock(2.5) + visual_impact(2.5) + conflict(2.5)

Return ONLY this JSON structure:
{{
    "title": "compelling title in the story's language",
    "genre": "action|romance|horror|scifi|fantasy|drama|comedy",
    "characters": [
        {{
            "id": "char_1",
            "name": "character name",
            "appearance": "concise visual keywords ONLY, max 10 words. Example: 'navy sweater, dark jeans, silver glasses, dark brown hair'. NO full sentences. (MUST be in English)",
            "traits": ["trait1", "trait2"]
        }}
    ],
    "arc": {{
        "hook": "0-3 second attention grabber description",
        "build": "tension/conflict buildup",
        "climax": "peak moment",
        "resolution": "ending with emotional impact"
    }},
    "hook_score": {{
        "curiosity": 0.0,
        "shock": 0.0,
        "visual_impact": 0.0,
        "conflict": 0.0,
        "total": 0.0,
        "reasoning": "why this score"
    }},
    "scenes": [
        {{
            "id": "scene_1",
            "purpose": "hook",
            "camera": "close-up|medium_shot|wide_shot|extreme_closeup|low_angle|high_angle|bird_eye",
            "mood": "tense|dark|bright|mysterious|romantic|cheerful|sad|epic",
            "action": "detailed visual description of what happens (MUST be in English for image generation. Describe ONLY visual elements: expressions, body language, actions, lighting, atmosphere. NO screens, text messages, UI, or written content - describe character reactions instead.)",
            "characters": ["char_1"],
            "location": "where this scene takes place (in English)",
            "dialogue": "any spoken dialogue (empty string if none)",
            "narration": "voiceover text if any (empty string if none)",
            "duration": 3.0,
            "emotion": "fear|joy|anger|sadness|surprise|disgust|neutral|tension|hope"
        }}
    ],
    "emotion_curve": [0.8, 0.5, 0.5, 0.6, 1.0, 0.3]
}}

SCENE DISTRIBUTION GUIDE:
- 1 Hook scene (purpose: "hook", 3 seconds)
- 2-3 Build scenes (purpose: "build", 2-4 seconds each)
- 2-3 Climax scenes (purpose: "climax", 2-3 seconds each)
- 1 Resolution scene (purpose: "resolution", 3-4 seconds)

IMPORTANT:
- If the input is vague, CREATIVE fill-in is expected. Add characters, settings, and plot details.
- The story language should match the input language.
- Make the hook IRRESISTIBLE — use mystery, shock, visual spectacle, or conflict.
- Every scene's "action" must be vivid enough for an AI image generator."""

LONGFORM_PROMPT = """Given this rough story idea, create a complete video script for a long-form video (2-8 minutes).

INPUT STORY:
{raw_story}

TARGET: Long-form video
CONSTRAINTS:
- Total duration: 120~480 seconds
- Scene count: 20~60 scenes
- Each scene: 3~15 seconds
- First scene (Hook): 5 seconds, must grab attention
- Include subplots and character development

Return ONLY this JSON structure:
{{
    "title": "compelling title in the story's language",
    "genre": "action|romance|horror|scifi|fantasy|drama|comedy",
    "characters": [
        {{
            "id": "char_1",
            "name": "character name",
            "appearance": "concise visual keywords ONLY, max 10 words. Example: 'navy sweater, dark jeans, silver glasses, dark brown hair'. NO full sentences. (MUST be in English)",
            "traits": ["trait1", "trait2"]
        }}
    ],
    "arc": {{
        "hook": "attention grabber",
        "build": "tension/conflict buildup",
        "climax": "peak moment",
        "resolution": "ending with emotional impact"
    }},
    "hook_score": {{
        "curiosity": 0.0,
        "shock": 0.0,
        "visual_impact": 0.0,
        "conflict": 0.0,
        "total": 0.0,
        "reasoning": "why this score"
    }},
    "scenes": [
        {{
            "id": "scene_1",
            "purpose": "hook",
            "camera": "close-up|medium_shot|wide_shot|extreme_closeup|low_angle|high_angle|bird_eye",
            "mood": "tense|dark|bright|mysterious|romantic|cheerful|sad|epic",
            "action": "detailed visual description (MUST be in English for image generation. Describe ONLY visual elements: expressions, body language, actions, lighting, atmosphere. NO screens, text messages, UI, or written content - describe character reactions instead.)",
            "characters": ["char_1"],
            "location": "scene location (in English)",
            "dialogue": "spoken dialogue",
            "narration": "voiceover text",
            "duration": 5.0,
            "emotion": "fear|joy|anger|sadness|surprise|disgust|neutral|tension|hope"
        }}
    ],
    "emotion_curve": [0.8, 0.5, 0.6, 0.7, 1.0, 0.4]
}}

IMPORTANT:
- If the input is vague, CREATIVE fill-in is expected.
- Match the input language.
- Build rich character arcs and subplots."""

RETRY_FIX_PROMPT = """The previous story script had validation errors. Fix them.

ORIGINAL INPUT:
{raw_story}

PREVIOUS OUTPUT:
{previous_json}

VALIDATION ERRORS:
{errors}

Return the CORRECTED JSON with the same structure. Fix ONLY the errors listed above."""


class UnifiedStoryCompiler:
    """
    LLM 1회 호출 통합 스토리 컴파일러

    사용법:
        from infrastructure.ai import StoryLLMProvider
        compiler = UnifiedStoryCompiler(llm_provider=StoryLLMProvider())
        result = await compiler.compile("호랑이가 마을에 나타났다")
        # result.story_spec → 완전한 StorySpec
    """

    MAX_RETRIES = 2

    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: StoryLLMProvider 또는 호환 Provider
                          None이면 StoryLLMProvider 자동 생성
        """
        if llm_provider is None:
            from infrastructure.ai import StoryLLMProvider
            llm_provider = StoryLLMProvider()
        self.llm = llm_provider
        self.validator = StoryValidator()

    async def compile(
        self,
        raw_story: str,
        target_format: TargetFormat = TargetFormat.SHORTS,
        max_retries: int = 2,
        language: str = None,
    ) -> CompileResult:
        """
        원시 스토리를 완전한 StorySpec으로 컴파일

        Args:
            raw_story: 사용자 입력 스토리 (자유 형식)
            target_format: 타겟 포맷 (SHORTS / LONGFORM)
            max_retries: 검증 실패 시 최대 재시도 횟수

        Returns:
            CompileResult
        """
        if not raw_story or not raw_story.strip():
            return CompileResult(success=False, error="스토리가 비어있습니다.")

        # 1. LLM 호출
        prompt = self._build_prompt(raw_story, target_format, language)
        story_spec = await self._call_llm(prompt, target_format)

        if story_spec is None:
            return CompileResult(success=False, error="LLM 응답 파싱 실패")

        # 2. 검증 + 재시도 루프
        for attempt in range(max_retries + 1):
            validation = self.validator.validate(story_spec)

            if validation.is_valid:
                hook_score = self._extract_hook_score(story_spec)
                return CompileResult(
                    success=True,
                    story_spec=story_spec,
                    hook_score=hook_score,
                    retry_count=attempt,
                )

            # 마지막 시도면 재시도 없이 반환
            if attempt >= max_retries:
                logger.warning(
                    f"Validation still failing after {max_retries} retries: "
                    f"{[e.message for e in validation.errors]}"
                )
                # 자동 수정 시도
                story_spec = self._auto_fix(story_spec, validation, target_format)
                final_validation = self.validator.validate(story_spec)
                hook_score = self._extract_hook_score(story_spec)
                return CompileResult(
                    success=final_validation.is_valid,
                    story_spec=story_spec,
                    hook_score=hook_score,
                    retry_count=attempt + 1,
                    error="" if final_validation.is_valid else "자동 수정 후에도 검증 실패",
                )

            # 재시도: LLM에게 에러 피드백과 함께 재요청
            logger.info(f"Validation failed (attempt {attempt + 1}), retrying...")
            retry_prompt = RETRY_FIX_PROMPT.format(
                raw_story=raw_story[:1000],
                previous_json=story_spec.to_json(),
                errors=self._format_errors(validation),
            )
            # 재시도에도 언어 지시문 추가
            lang = language or (STORY_LANGUAGES[0] if STORY_LANGUAGES else "ko")
            lang_name = LANGUAGE_NAMES.get(lang, "Korean")
            lang_native = LANGUAGE_NATIVE_NAMES.get(lang, "한국어")
            retry_prompt += f"\nLANGUAGE: Write ALL content in {lang_name} ({lang_native})."
            fixed_spec = await self._call_llm(retry_prompt, target_format)
            if fixed_spec is not None:
                story_spec = fixed_spec

        return CompileResult(success=False, error="최대 재시도 초과")

    def _build_prompt(self, raw_story: str, target_format: TargetFormat, language: str = None) -> str:
        """타겟 포맷에 맞는 프롬프트 생성"""
        lang = language or (STORY_LANGUAGES[0] if STORY_LANGUAGES else "ko")
        lang_name = LANGUAGE_NAMES.get(lang, "Korean")
        lang_native = LANGUAGE_NATIVE_NAMES.get(lang, "한국어")

        # 언어 지시문 생성 (시각 묘사는 영어, 대사/내레이션은 타겟 언어)
        lang_instruction = f"\nLANGUAGE INSTRUCTION: Title, dialogue, and narration MUST be written in {lang_name} ({lang_native}). Visual description fields (action, appearance, location, camera, mood) MUST be in English for image generation AI."

        if target_format == TargetFormat.SHORTS:
            base = SHORTS_PROMPT.format(raw_story=raw_story[:3000])
            return base + lang_instruction
        else:
            base = LONGFORM_PROMPT.format(raw_story=raw_story[:5000])
            return base + lang_instruction

    async def _call_llm(self, prompt: str, target_format: TargetFormat) -> Optional[StorySpec]:
        """LLM 호출 및 응답 파싱"""
        if self.llm is None:
            logger.error("LLM Provider가 설정되지 않았습니다.")
            return None

        try:
            response_text = await self.llm._call_api(
                system_prompt=SYSTEM_PROMPT,
                user_message=prompt,
            )
            return self._parse_response(response_text, target_format)
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return None

    def _parse_response(self, response: str, target_format: TargetFormat) -> Optional[StorySpec]:
        """LLM 응답 텍스트를 StorySpec으로 파싱"""
        # JSON 블록 추출
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return None

        try:
            return self._dict_to_story_spec(data, target_format)
        except Exception as e:
            logger.error(f"StorySpec 변환 실패: {e}")
            return None

    def _dict_to_story_spec(self, data: Dict[str, Any], target_format: TargetFormat) -> StorySpec:
        """딕셔너리를 StorySpec으로 변환"""
        # 캐릭터 변환
        characters = []
        for c in data.get("characters", []):
            characters.append(CharacterSpec(
                id=c.get("id", f"char_{len(characters)+1}"),
                name=c.get("name", "Unknown"),
                appearance=c.get("appearance", ""),
                traits=c.get("traits", []),
            ))

        # 아크 변환
        arc_data = data.get("arc", {})
        arc = ArcSpec(
            hook=arc_data.get("hook", ""),
            build=arc_data.get("build", ""),
            climax=arc_data.get("climax", ""),
            resolution=arc_data.get("resolution", ""),
        )

        # 씬 변환
        scenes = []
        for s in data.get("scenes", []):
            purpose_str = s.get("purpose", "build")
            try:
                purpose = ScenePurpose(purpose_str)
            except ValueError:
                purpose = ScenePurpose.BUILD

            scenes.append(SceneSpec(
                id=s.get("id", f"scene_{len(scenes)+1}"),
                purpose=purpose,
                camera=s.get("camera", "medium_shot"),
                mood=s.get("mood", "neutral"),
                action=s.get("action", ""),
                characters=s.get("characters", []),
                location=s.get("location", ""),
                dialogue=s.get("dialogue", ""),
                narration=s.get("narration", ""),
                duration=float(s.get("duration", 3.0)),
                emotion=s.get("emotion", "neutral"),
            ))

        # Hook 스코어는 metadata에 저장
        hook_score_data = data.get("hook_score", {})
        metadata = {
            "hook_score": hook_score_data,
            "source": "unified_compiler",
        }

        # 총 길이 계산
        total_duration = sum(s.duration for s in scenes) if scenes else 0.0

        return StorySpec(
            title=data.get("title", "Untitled"),
            genre=data.get("genre", "drama"),
            target=target_format,
            duration=total_duration,
            characters=characters,
            arc=arc,
            scenes=scenes,
            emotion_curve=data.get("emotion_curve", []),
            metadata=metadata,
        )

    def _extract_hook_score(self, spec: StorySpec) -> float:
        """StorySpec metadata에서 hook score 추출"""
        hook_score = spec.metadata.get("hook_score", {})
        return float(hook_score.get("total", 0.0))

    def _format_errors(self, validation: ValidationResult) -> str:
        """검증 에러를 LLM이 이해할 수 있는 텍스트로 변환"""
        lines = []
        for err in validation.errors:
            lines.append(f"- [{err.severity}] {err.field}: {err.message}")
        return "\n".join(lines)

    def _auto_fix(self, spec: StorySpec, validation: ValidationResult, target_format: TargetFormat) -> StorySpec:
        """검증 실패 시 자동 수정"""
        constraints = SHORTS_CONSTRAINTS if target_format == TargetFormat.SHORTS else LONGFORM_CONSTRAINTS

        for err in validation.errors:
            # Duration 수정
            if "duration" in err.field.lower():
                current = spec.total_duration() if hasattr(spec, 'total_duration') else sum(s.duration for s in spec.scenes)
                min_d = constraints["min_duration"]
                max_d = constraints["max_duration"]

                if current < min_d:
                    scale = min_d / max(current, 0.1)
                    for s in spec.scenes:
                        s.duration = round(s.duration * scale, 1)
                elif current > max_d:
                    scale = max_d / max(current, 0.1)
                    for s in spec.scenes:
                        s.duration = max(1.5, round(s.duration * scale, 1))

            # Scene 수 수정
            if "scene" in err.field.lower() and "count" in err.field.lower():
                min_s = constraints["min_scenes"]
                max_s = constraints["max_scenes"]
                current_count = len(spec.scenes)

                if current_count < min_s:
                    # 마지막 씬을 복제해서 추가
                    while len(spec.scenes) < min_s:
                        last = spec.scenes[-1]
                        new_scene = SceneSpec(
                            id=f"scene_{len(spec.scenes)+1}",
                            purpose=last.purpose,
                            camera=last.camera,
                            mood=last.mood,
                            action=last.action,
                            characters=last.characters,
                            location=last.location,
                            dialogue="",
                            narration="",
                            duration=last.duration,
                            emotion=last.emotion,
                        )
                        spec.scenes.append(new_scene)
                elif current_count > max_s:
                    # BUILD purpose 씬부터 제거
                    spec.scenes = [
                        s for s in spec.scenes
                        if s.purpose != ScenePurpose.BUILD or len([x for x in spec.scenes if x.purpose == ScenePurpose.BUILD]) <= max_s
                    ]
                    # 여전히 초과하면 뒤에서 제거
                    while len(spec.scenes) > max_s:
                        spec.scenes.pop(-2)  # 마지막(resolution)은 유지

        # Duration 재계산
        spec.duration = sum(s.duration for s in spec.scenes)
        return spec
