"""
Hook Enhancer + Scoring System

Hook 강화 및 스코어링 시스템 for short-form video
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import re
import json
import random

from .story_spec import SceneSpec, ScenePurpose


@dataclass
class HookScore:
    """Hook 점수"""
    total: float  # 0~10
    curiosity: float  # 호기심 유발 (0~2.5)
    shock: float  # 충격 요소 (0~2.5)
    visual_impact: float  # 시각적 임팩트 (0~2.5)
    conflict: float  # 갈등 암시 (0~2.5)
    details: List[str] = field(default_factory=list)  # 상세 피드백

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "curiosity": self.curiosity,
            "shock": self.shock,
            "visual_impact": self.visual_impact,
            "conflict": self.conflict,
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookScore":
        return cls(**data)


class HookEnhancer:
    """Hook 강화 + 스코어링 시스템"""

    # Hook 강화 키워드
    SHOCK_KEYWORDS = [
        "sudden", "unexpected", "shocking", "impossible",
        "deadly", "catastrophic", "unthinkable", "frozen",
        "vanished", "exploded", "collapsed", "screamed",
        "crashed", "erupted", "shattered", "terrifying",
        "horrifying", "devastating", "instantly", "brutal"
    ]

    CURIOSITY_KEYWORDS = [
        "mysterious", "strange", "unknown", "secret",
        "hidden", "forbidden", "impossible", "question",
        "mystery", "bizarre", "puzzling", "unsolved",
        "curious", "wonder", "discover", "reveal"
    ]

    VISUAL_KEYWORDS = [
        "blood", "fire", "explosion", "tears", "silence",
        "darkness", "light", "shadow", "close-up", "wide shot",
        "flashing", "blazing", "blood-red", "pitch-black",
        "glowing", "shattered", "falling", "rising"
    ]

    CONFLICT_KEYWORDS = [
        "vs", "against", "fight", "danger", "threat", "enemy",
        "must", "battle", "confront", "struggle", "survive",
        "escape", "rescue", "attack", "defend", "kill"
    ]

    # Hook 필수 요소
    REQUIRED_ELEMENTS = ["shock_or_curiosity", "visual_element", "character_or_action"]

    # 최소 점수 임계값
    MIN_PASSING_SCORE = 6.0

    # 강화 템플릿
    ENHANCEMENT_TEMPLATES = {
        "shock": [
            "Suddenly, {text}",
            "Without warning, {text}",
            "In an instant, {text}",
            "Everything changed when {text}",
            "No one expected {text}"
        ],
        "curiosity": [
            "A mysterious {text}",
            "The secret {text}",
            "An unknown {text}",
            "Something strange: {text}",
            "The hidden truth about {text}"
        ],
        "visual": [
            "{text} - close-up shot",
            "{text}, bathed in light",
            "{text}, in the darkness",
            "Blood-red {text}",
            "Shadow reveals {text}"
        ]
    }

    def __init__(self, llm_provider=None):
        self.llm = llm_provider

    def enhance(self, hook_text: str, context: dict = None, force_add_shock: bool = False) -> str:
        """
        Hook 강화 - 키워드 기반 점수 향상

        Args:
            hook_text: 원본 Hook 텍스트
            context: 추가 컨텍스트 (genre, mood 등)
            force_add_shock: 충격 요소 강제 추가 여부

        Returns:
            강화된 Hook 텍스트
        """
        if not hook_text or not hook_text.strip():
            return hook_text

        enhanced = hook_text.strip()
        context = context or {}

        # 1. 현재 Hook 분석
        current_score = self.score(enhanced)

        # 이미 충분히 높으면 그대로 반환
        if current_score.total >= 7.0:
            return enhanced

        # 2. 각 카테고리별 키워드 추가 - 더 컴팩트하게
        additions = []

        # 충격 요소 (간결하게)
        if current_score.shock < 2.0:
            if not any(kw in enhanced.lower() for kw in ["sudden", "unexpected", "shocking"]):
                additions.append("SUDDEN shocking danger:")

        # 호기심 요소 (간결하게)
        if current_score.curiosity < 2.0:
            if not any(kw in enhanced.lower() for kw in ["mysterious", "secret", "hidden"]):
                additions.append("mysterious secret revealed")

        # 시각적 요소 (간결하게)
        if current_score.visual_impact < 2.0:
            if not any(kw in enhanced.lower() for kw in ["blood", "fire", "explosion", "darkness"]):
                additions.append("blood fire darkness explosion")

        # 갈등 요소 (간결하게)
        if current_score.conflict < 2.0:
            if not any(kw in enhanced.lower() for kw in ["fight", "enemy", "threat", "battle"]):
                additions.append("must fight enemy threat")

        # 추가 문장들을 Hook에 병합
        if additions:
            enhanced = f"{enhanced}. {' '.join(additions)}"

        # 5. 길이 제한 (30단어로 증가)
        words = enhanced.split()
        if len(words) > 30:
            enhanced = " ".join(words[:30])

        # 6. 첫 글자 대문자화
        if enhanced:
            enhanced = enhanced[0].upper() + enhanced[1:]

        return enhanced

    def score(self, hook_text: str) -> HookScore:
        """
        Hook 점수 계산

        Args:
            hook_text: Hook 텍스트

        Returns:
            HookScore 객체 (각 항목 0~2.5점, 총 10점 만점)
        """
        if not hook_text:
            return HookScore(
                total=0.0,
                curiosity=0.0,
                shock=0.0,
                visual_impact=0.0,
                conflict=0.0,
                details=["Empty hook text"]
            )

        text = hook_text.lower()

        curiosity = self._score_curiosity(text)
        shock = self._score_shock(text)
        visual = self._score_visual(text)
        conflict = self._score_conflict(text)

        return HookScore(
            total=curiosity + shock + visual + conflict,
            curiosity=curiosity,
            shock=shock,
            visual_impact=visual,
            conflict=conflict,
            details=self._generate_feedback(curiosity, shock, visual, conflict)
        )

    def _score_curiosity(self, text: str) -> float:
        """호기심 점수 (0~2.5)"""
        score = 0.0
        matched_keywords = []

        for keyword in self.CURIOSITY_KEYWORDS:
            if keyword in text:
                score += 0.4
                matched_keywords.append(keyword)

        # 질문표호 보너스
        if "?" in text:
            score += 0.5

        # 미스터리한 시작 보너스
        mystery_starts = ["what", "why", "how", "who", "where", "when", "secret", "mystery"]
        first_words = text.split()[:3] if text.split() else []
        if any(start in first_words for start in mystery_starts):
            score += 0.3

        return min(score, 2.5)

    def _score_shock(self, text: str) -> float:
        """충격 점수 (0~2.5)"""
        score = 0.0
        matched_keywords = []

        for keyword in self.SHOCK_KEYWORDS:
            if keyword in text:
                score += 0.4
                matched_keywords.append(keyword)

        # 긴급성 표현 보너스
        urgency_words = ["now", "instantly", "suddenly", "immediately", "just"]
        if any(word in text for word in urgency_words):
            score += 0.3

        # 강한 감정 단어 보너스
        strong_emotions = ["terror", "horror", "panic", "fear", "death"]
        if any(word in text for word in strong_emotions):
            score += 0.3

        return min(score, 2.5)

    def _score_visual(self, text: str) -> float:
        """시각적 점수 (0~2.5)"""
        score = 0.0
        matched_keywords = []

        for keyword in self.VISUAL_KEYWORDS:
            if keyword in text:
                score += 0.4
                matched_keywords.append(keyword)

        # 카메라 앵글 언급 시 가산점
        camera_terms = ["close-up", "wide", "shot", "angle", "zoom", "pan", "view"]
        if any(cam in text for cam in camera_terms):
            score += 0.5

        # 색상 언급 보너스
        colors = ["red", "black", "white", "dark", "bright", "blood", "golden"]
        if any(color in text for color in colors):
            score += 0.3

        # 감각적 단어 보너스
        sensory_words = ["flashing", "blazing", "glowing", "shattered", "frozen"]
        if any(word in text for word in sensory_words):
            score += 0.2

        return min(score, 2.5)

    def _score_conflict(self, text: str) -> float:
        """갈등 점수 (0~2.5)"""
        score = 0.0
        matched_keywords = []

        for word in self.CONFLICT_KEYWORDS:
            if word in text:
                score += 0.4
                matched_keywords.append(word)

        # 위험/긴장 표현 보너스
        tension_words = ["must", "cannot", "never", "impossible", "deadly", "fatal"]
        if any(word in text for word in tension_words):
            score += 0.3

        # 대립 구조 보너스
        if " vs " in text or " vs. " in text or "against" in text:
            score += 0.4

        return min(score, 2.5)

    def _generate_feedback(self, curiosity: float, shock: float,
                          visual: float, conflict: float) -> List[str]:
        """피드백 생성"""
        feedback = []

        if curiosity < 1.0:
            feedback.append("CRITICAL: Add mystery or question element (curiosity score too low)")
        elif curiosity < 1.5:
            feedback.append("Add mystery or question element")

        if shock < 1.0:
            feedback.append("CRITICAL: Add shock or unexpected element (shock score too low)")
        elif shock < 1.5:
            feedback.append("Add shock or unexpected element")

        if visual < 1.0:
            feedback.append("CRITICAL: Add visual impact words (visual score too low)")
        elif visual < 1.5:
            feedback.append("Add visual impact words")

        if conflict < 1.0:
            feedback.append("CRITICAL: Add conflict or tension (conflict score too low)")
        elif conflict < 1.5:
            feedback.append("Add conflict or tension")

        if not feedback:
            feedback.append("Hook is well-balanced across all dimensions")

        return feedback

    def enhance_and_score(self, hook_text: str, min_score: float = None,
                         max_retries: int = 3) -> Tuple[str, HookScore]:
        """
        강화 + 스코어링

        Args:
            hook_text: 원본 Hook 텍스트
            min_score: 최소 통과 점수 (기본값: MIN_PASSING_SCORE)
            max_retries: 최대 재시도 횟수

        Returns:
            (강화된 Hook, 최종 점수)
        """
        if min_score is None:
            min_score = self.MIN_PASSING_SCORE

        enhanced = hook_text
        score = self.score(enhanced)

        # 이미 충분히 높은 점수면 그대로 반환
        if score.total >= min_score:
            return enhanced, score

        # 점수가 낮으면 재강화
        retry_count = 0
        while score.total < min_score and retry_count < max_retries:
            enhanced = self.enhance(enhanced, force_add_shock=(retry_count > 0))
            score = self.score(enhanced)
            retry_count += 1

        return enhanced, score

    def is_hook_strong(self, hook_text: str) -> bool:
        """
        Hook가 충분히 강한지 확인

        Args:
            hook_text: Hook 텍스트

        Returns:
            통과 여부 (점수 >= MIN_PASSING_SCORE)
        """
        return self.score(hook_text).total >= self.MIN_PASSING_SCORE

    def enhance_scene_hook(self, scene_spec: SceneSpec,
                          min_score: float = None) -> Tuple[SceneSpec, HookScore]:
        """
        SceneSpec의 Hook 씬 강화

        Args:
            scene_spec: 장면 명세
            min_score: 최소 통과 점수

        Returns:
            (강화된 SceneSpec, Hook 점수)
        """
        # purpose가 hook인지 확인
        if scene_spec.purpose != ScenePurpose.HOOK:
            return scene_spec, self.score(scene_spec.action or "")

        # action 텍스트를 Hook로 강화
        original_action = scene_spec.action or ""
        enhanced_action, score = self.enhance_and_score(
            original_action,
            min_score=min_score
        )

        # 새 SceneSpec 생성
        enhanced_scene = SceneSpec(
            id=scene_spec.id,
            purpose=scene_spec.purpose,
            camera=scene_spec.camera,
            mood=scene_spec.mood,
            action=enhanced_action,
            characters=scene_spec.characters,
            location=scene_spec.location,
            dialogue=scene_spec.dialogue,
            narration=scene_spec.narration,
            duration=scene_spec.duration,
            emotion=scene_spec.emotion
        )

        return enhanced_scene, score

    def get_enhancement_suggestions(self, hook_text: str) -> Dict[str, List[str]]:
        """
        Hook 강화 제안 생성

        Args:
            hook_text: Hook 텍스트

        Returns:
            카테고리별 강화 제안
        """
        score = self.score(hook_text)
        suggestions = {
            "curiosity": [],
            "shock": [],
            "visual": [],
            "conflict": []
        }

        if score.curiosity < 1.5:
            suggestions["curiosity"] = random.sample(
                self.CURIOSITY_KEYWORDS, min(3, len(self.CURIOSITY_KEYWORDS))
            )

        if score.shock < 1.5:
            suggestions["shock"] = random.sample(
                self.SHOCK_KEYWORDS, min(3, len(self.SHOCK_KEYWORDS))
            )

        if score.visual_impact < 1.5:
            suggestions["visual"] = random.sample(
                self.VISUAL_KEYWORDS, min(3, len(self.VISUAL_KEYWORDS))
            )

        if score.conflict < 1.5:
            suggestions["conflict"] = random.sample(
                self.CONFLICT_KEYWORDS, min(3, len(self.CONFLICT_KEYWORDS))
            )

        return suggestions


# LLM 기반 고급 강화
class LLMHookEnhancer(HookEnhancer):
    """LLM 기반 Hook 강화기"""

    def __init__(self, llm_provider=None):
        super().__init__(llm_provider)
        self.llm = llm_provider

    async def enhance_with_llm(self, hook_text: str, context: dict = None) -> str:
        """
        LLM으로 Hook 강화

        Args:
            hook_text: 원본 Hook 텍스트
            context: 추가 컨텍스트

        Returns:
            강화된 Hook 텍스트
        """
        if not self.llm:
            # LLM이 없으면 기본 강화 사용
            return self.enhance(hook_text, context)

        context = context or {}
        genre = context.get("genre", "drama")
        mood = context.get("mood", "intense")

        prompt = f"""Make this hook MORE shocking and engaging for short-form video (3 seconds max):

Original: {hook_text}
Genre: {genre}
Mood: {mood}

Requirements:
- Add visual impact (colors, camera angles, lighting)
- Create immediate curiosity or shock
- Keep it under 15 words
- Start with action or unexpected event
- Include at least one of: sudden movement, mystery, danger, visual element

Return ONLY the enhanced hook text, nothing else."""

        try:
            # LLM 호출 (provider에 따라 다름)
            if hasattr(self.llm, 'generate'):
                result = await self.llm.generate(prompt)
            elif hasattr(self.llm, 'complete'):
                result = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'invoke'):
                result = await self.llm.invoke(prompt)
            else:
                # 동기 호출 fallback
                result = self.llm(prompt)

            # 결과 정리
            enhanced = result.strip() if result else hook_text

            # 길이 제한
            words = enhanced.split()
            if len(words) > 15:
                enhanced = " ".join(words[:15])

            return enhanced

        except Exception as e:
            # 에러 시 기본 강화 사용
            print(f"LLM enhancement failed: {e}")
            return self.enhance(hook_text, context)

    async def score_with_llm(self, hook_text: str) -> HookScore:
        """
        LLM으로 정교한 스코어링

        Args:
            hook_text: Hook 텍스트

        Returns:
            HookScore 객체
        """
        if not self.llm:
            # LLM이 없으면 기본 스코어링 사용
            return self.score(hook_text)

        prompt = f"""Score this hook for short-form video (0-10 scale):

Hook: "{hook_text}"

Score each category from 0 to 2.5:
1. Curiosity (0-2.5): Does it make viewers want to know more?
2. Shock (0-2.5): Is it unexpected or shocking?
3. Visual Impact (0-2.5): Can you visualize it strongly?
4. Conflict (0-2.5): Is there tension or danger?

Return ONLY valid JSON in this exact format:
{{"curiosity": 0.0, "shock": 0.0, "visual": 0.0, "conflict": 0.0, "feedback": ["suggestion1", "suggestion2"]}}"""

        try:
            # LLM 호출
            if hasattr(self.llm, 'generate'):
                result = await self.llm.generate(prompt)
            elif hasattr(self.llm, 'complete'):
                result = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'invoke'):
                result = await self.llm.invoke(prompt)
            else:
                result = self.llm(prompt)

            # JSON 파싱
            result_text = result.strip()

            # JSON 추출 (마크다운 코드 블록 제거)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            data = json.loads(result_text.strip())

            return HookScore(
                total=data.get("curiosity", 0) + data.get("shock", 0) +
                      data.get("visual", 0) + data.get("conflict", 0),
                curiosity=float(data.get("curiosity", 0)),
                shock=float(data.get("shock", 0)),
                visual_impact=float(data.get("visual", 0)),
                conflict=float(data.get("conflict", 0)),
                details=data.get("feedback", [])
            )

        except Exception as e:
            # 에러 시 기본 스코어링 사용
            print(f"LLM scoring failed: {e}")
            return self.score(hook_text)

    async def enhance_and_score_with_llm(self, hook_text: str,
                                         min_score: float = None,
                                         max_retries: int = 2) -> Tuple[str, HookScore]:
        """
        LLM 기반 강화 + 스코어링

        Args:
            hook_text: 원본 Hook 텍스트
            min_score: 최소 통과 점수
            max_retries: 최대 재시도 횟수

        Returns:
            (강화된 Hook, 최종 점수)
        """
        if min_score is None:
            min_score = self.MIN_PASSING_SCORE

        enhanced = hook_text
        score = await self.score_with_llm(enhanced)

        if score.total >= min_score:
            return enhanced, score

        retry_count = 0
        while score.total < min_score and retry_count < max_retries:
            enhanced = await self.enhance_with_llm(enhanced)
            score = await self.score_with_llm(enhanced)
            retry_count += 1

        return enhanced, score
