"""
Short Drama Compiler - 숏 드라마 전용 스토리 컴파일러

5개 독립 축(Category, Relationship, Secret Type, Event Trigger, Twist Pattern) 기반 조합 구조.
논리 연결 규칙(TRIGGER_SECRET_COMPATIBILITY, TWIST_SECRET_COMPATIBILITY)을 적용하여
의미 있는 조합만 생성합니다.

DB 연동(StoryComponentDB)으로 중복 방지, 성과 학습, 가중치 기반 선택을 지원하며,
DB가 없어도 인메모리 폴백으로 동작합니다.

UnifiedStoryCompiler와 동일한 패턴(CompileResult, StorySpec 반환)을 따릅니다.
"""
import hashlib
import json
import logging
import random
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from .story_spec import (
    StorySpec, SceneSpec, CharacterSpec, ArcSpec,
    TargetFormat, ScenePurpose,
)
from .story_validator import StoryValidator, ValidationResult
from .unified_compiler import CompileResult
from config.api_config import STORY_LANGUAGES
from infrastructure.tts.tts_config import LANGUAGE_NAMES, LANGUAGE_NATIVE_NAMES

logger = logging.getLogger(__name__)


# ============================================================
# 5개 독립 축 정의
# ============================================================

# 축 1: Category (5개, 고정)
CATEGORIES: List[str] = [
    "연애 배신",
    "가족 갈등",
    "친구 배신",
    "직장 권력",
    "돈 이익",
]

# 축 2: Relationship (20개, 카테고리 그룹핑)
# (관계명, 카테고리 그룹) 형식
RELATIONSHIPS: List[Tuple[str, str]] = [
    # 연애 배신 그룹
    ("연인", "연애 배신"),
    ("전연인", "연애 배신"),
    ("삼각관계", "연애 배신"),
    ("썸", "연애 배신"),
    # 가족 갈등 그룹
    ("모녀", "가족 갈등"),
    ("부녀", "가족 갈등"),
    ("형제", "가족 갈등"),
    ("고모/조카", "가족 갈등"),
    # 친구 배신 그룹
    ("절친", "친구 배신"),
    ("동료", "친구 배신"),
    ("룸메이트", "친구 배신"),
    ("학교 친구", "친구 배신"),
    # 직장 권력 그룹
    ("상사/부하", "직장 권력"),
    ("선배/후배", "직장 권력"),
    ("동료", "직장 권력"),
    ("사장/직원", "직장 권력"),
    # 돈 이익 그룹
    ("파트너", "돈 이익"),
    ("친척", "돈 이익"),
    ("이웃", "돈 이익"),
    ("공동투자자", "돈 이익"),
]

# 축 3: Secret Type (12개, 공통 풀)
SECRET_TYPES: List[str] = [
    "바람",
    "거짓말",
    "신분 속임",
    "과거 숨김",
    "돈 문제",
    "배신",
    "몰래카메라",
    "테스트",
    "이중생활",
    "감정 숨김",
    "질병 숨김",
    "가족 비밀",
]

# 축 4: Event Trigger (12개, 공통 풀)
EVENT_TRIGGERS: List[str] = [
    "생일",
    "결혼식",
    "병원",
    "술자리",
    "문자 발견",
    "통화 도청",
    "CCTV",
    "우연한 목격",
    "SNS",
    "유언",
    "이사",
    "다른 사람 고백",
]

# 축 5: Twist Pattern (10개, 공통 풀)
TWIST_PATTERNS: List[str] = [
    "사실 알고 있었다",
    "테스트였다",
    "더 큰 배신 존재",
    "피해자가 가해자",
    "오해였다",
    "제3자가 설계",
    "시간차 진실",
    "주인공 의도적 선택",
    "역할 반전",
    "모두가 알고 있었다",
]


# ============================================================
# 논리 연결 규칙 (핵심)
# ============================================================

# Rule 1: trigger는 secret과 논리적으로 연결
TRIGGER_SECRET_COMPATIBILITY: Dict[str, List[str]] = {
    "바람": ["문자 발견", "통화 도청", "우연한 목격", "술자리", "SNS"],
    "거짓말": ["문자 발견", "통화 도청", "다른 사람 고백", "이사"],
    "신분 속임": ["병원", "유언", "CCTV", "다른 사람 고백"],
    "과거 숨김": ["술자리", "우연한 목격", "이사", "SNS"],
    "돈 문제": ["유언", "결혼식", "이사", "문자 발견"],
    "배신": ["생일", "결혼식", "술자리", "우연한 목격"],
    "몰래카메라": ["CCTV", "SNS", "문자 발견"],
    "테스트": ["생일", "술자리", "결혼식"],
    "이중생활": ["우연한 목격", "이사", "문자 발견", "술자리"],
    "감정 숨김": ["술자리", "병원", "다른 사람 고백", "생일"],
    "질병 숨김": ["병원", "결혼식", "우연한 목격"],
    "가족 비밀": ["유언", "병원", "이사", "CCTV"],
}

# Rule 2: twist는 secret 기반
TWIST_SECRET_COMPATIBILITY: Dict[str, List[str]] = {
    "바람": ["사실 알고 있었다", "더 큰 배신 존재", "피해자가 가해자", "제3자가 설계"],
    "거짓말": ["테스트였다", "오해였다", "시간차 진실", "모두가 알고 있었다"],
    "신분 속임": ["시간차 진실", "더 큰 배신 존재", "역할 반전", "모두가 알고 있었다"],
    "과거 숨김": ["시간차 진실", "오해였다", "주인공 의도적 선택", "제3자가 설계"],
    "돈 문제": ["피해자가 가해자", "더 큰 배신 존재", "제3자가 설계", "역할 반전"],
    "배신": ["사실 알고 있었다", "주인공 의도적 선택", "더 큰 배신 존재", "피해자가 가해자"],
    "몰래카메라": ["제3자가 설계", "피해자가 가해자", "역할 반전"],
    "테스트": ["오해였다", "사실 알고 있었다", "주인공 의도적 선택"],
    "이중생활": ["모두가 알고 있었다", "시간차 진실", "역할 반전", "더 큰 배신 존재"],
    "감정 숨김": ["오해였다", "시간차 진실", "주인공 의도적 선택", "역할 반전"],
    "질병 숨김": ["오해였다", "시간차 진실", "주인공 의도적 선택"],
    "가족 비밀": ["시간차 진실", "더 큰 배신 존재", "피해자가 가해자", "모두가 알고 있었다"],
}


# ============================================================
# 제약 조건
# ============================================================

SHORT_DRAMA_CONSTRAINTS = {
    "min_duration": 45,         # 최소 45초 (고정)
    "max_duration": None,       # 최대 무제한 (스토리에 따라 자연스럽게)
    "min_scenes": 5,            # 최소 5개 (Hook/Setup/Conflict/Twist/Ending)
    "max_scenes": None,         # 최대 무제한
    "scene_duration_range": (3, 15),
}


# ============================================================
# 5단계 구조 정의
# ============================================================

DRAMA_ACTS = {
    "hook": {
        "label": "Hook",
        "time_range": (0, 3),        # 0~3초
        "description": "강제 시청 유도",
    },
    "setup": {
        "label": "Setup",
        "time_range": (3, 15),       # 3~15초
        "description": "관계 + 문제 제시",
    },
    "conflict": {
        "label": "Conflict",
        "time_range": (15, 40),      # 15~40초
        "description": "갈등 폭발 / 감정 / 반전",
    },
    "twist": {
        "label": "Twist",
        "time_range": (40, 55),      # 40~55초
        "description": "반전 or 충격 결말",
    },
    "ending": {
        "label": "Ending",
        "time_range": (55, None),    # 55초~
        "description": "여운 / 댓글 유도",
    },
}


# ============================================================
# 프롬프트 상수
# ============================================================

DRAMA_SYSTEM_PROMPT = """You are a professional short-form drama scriptwriter specializing in relationship conflict stories.
You create emotionally intense, cliffhanger-driven scripts optimized for vertical short-form video (Shorts/TikTok/Reels).

RULES:
1. Return ONLY valid JSON. No markdown, no explanation.
2. Follow the 5-act structure: Hook -> Setup -> Conflict -> Twist -> Ending
3. Characters must be visually distinct and consistent
4. Every scene MUST have clear visual action (for AI image generation)
5. Hook must grab attention within 3 seconds
6. All durations are in seconds
7. Keep emotions INTENSE - this is drama, not documentary
8. Include suggested caption for engagement at the end
9. NEVER describe faces (no "beautiful", "handsome", "pretty", "big eyes" etc.) - use clothing, hairstyle, accessories, body type for visual distinction
10. All dialogue must match the target language specified in the prompt
11. Visual description fields (action, appearance, location, camera, mood) MUST be in English for image generation AI
12. Dialogue, narration, and title should be in the target language specified in the prompt
13. NEVER describe screens, text messages, UI elements, or written content in the "action" field. SDXL cannot render text.
14. Instead of describing what a screen shows, describe the CHARACTER'S REACTION: facial expression, body language, emotion, lighting.
    BAD: "phone screen showing message 'I love you'"
    GOOD: "man's shocked expression illuminated by phone glow in dark room, trembling hands"
    BAD: "KakaoTalk chat log showing messages"
    GOOD: "woman staring at phone with pale face, tears forming in her eyes, dramatic side lighting"
15. Focus "action" on: facial expressions, body language, physical actions, camera angles, lighting, atmosphere."""

DRAMA_USER_PROMPT = """CATEGORY: {category}
FORMULA: {relation} + {secret} + {conflict_event} + {twist}
TONE: {tone}
{hint_section}

Create a compelling short drama script.

Return ONLY this JSON structure:
{{
    "title": "compelling Korean title",
    "category": "{category}",
    "characters": [
        {{
            "id": "char_1",
            "name": "character name",
            "appearance": "concise visual keywords ONLY, max 10 words. Example: 'navy sweater, dark jeans, silver glasses, dark brown hair'. NO full sentences. NO face descriptions. (MUST be in English)",
            "traits": ["trait1", "trait2"],
            "role": "protagonist/antagonist/observer"
        }}
    ],
    "formula": {{
        "relation": "relationship type",
        "secret": "the hidden truth",
        "conflict_event": "what triggers the explosion",
        "twist": "unexpected reversal"
    }},
    "arc": {{
        "hook": "attention-grabbing opening",
        "setup": "relationship + problem introduction",
        "conflict": "conflict explosion / revelation",
        "twist": "unexpected reversal",
        "ending": "emotional aftermath + engagement hook"
    }},
    "scenes": [
        {{
            "id": "scene_1",
            "act": "hook",
            "camera": "close-up|medium_shot|wide_shot|extreme_closeup|low_angle|high_angle|bird_eye",
            "mood": "tense|dark|bright|mysterious|romantic|cheerful|sad|epic",
            "action": "detailed visual description for 3D animation (MUST be in English for image generation. Describe ONLY visual elements: expressions, body language, actions, lighting, atmosphere. NO screens, text messages, UI, or written content - describe character reactions instead.)",
            "characters": ["char_1"],
            "location": "where this scene takes place (in English)",
            "dialogue": "spoken dialogue (Korean)",
            "narration": "voiceover if any",
            "duration": 3.0,
            "emotion": "fear|joy|anger|sadness|surprise|disgust|neutral|tension|hope"
        }}
    ],
    "emotion_curve": [0.8, 0.5, 0.5, 0.9, 0.3],
    "caption": "engagement hook for comments"
}}

SCENE DISTRIBUTION GUIDE (5-act structure):
- 1 Hook scene (act: "hook", 3 seconds, attention-grabbing)
- 1-2 Setup scenes (act: "setup", 3-5 seconds each, introduce characters and situation)
- 2-3 Conflict scenes (act: "conflict", 3-5 seconds each, escalating tension)
- 1-2 Twist scenes (act: "twist", 3-5 seconds each, shocking revelation)
- 1-2 Ending scenes (act: "ending", 3-5 seconds each, emotional aftermath)

IMPORTANT:
- Total duration should be at least 45 seconds
- Minimum 5 scenes (one per act)
- The story language is Korean
- Make emotions INTENSE and dramatic
- Every scene's "action" must be vivid enough for an AI image generator
- Characters should wear distinctive outfits for visual consistency"""

DRAMA_RETRY_PROMPT = """The previous short drama script had validation errors. Fix them.

CATEGORY: {category}
FORMULA: {formula_str}

PREVIOUS OUTPUT:
{previous_json}

VALIDATION ERRORS:
{errors}

Return the CORRECTED JSON with the same structure. Fix ONLY the errors listed above."""


# ============================================================
# act 값을 ScenePurpose로 매핑
# ============================================================

ACT_TO_PURPOSE = {
    "hook": ScenePurpose.HOOK,
    "setup": ScenePurpose.BUILD,
    "conflict": ScenePurpose.CLIMAX,
    "twist": ScenePurpose.CLIMAX,
    "ending": ScenePurpose.RESOLUTION,
}


# ============================================================
# 인메모리 폴백 DB
# ============================================================

class _InMemoryFallbackDB:
    """
    DB 없을 때 사용하는 인메모리 폴백.

    StoryComponentDB의 핵심 API(weighted_select, is_duplicate, save_combination)를
    최소한으로 흉내내어 DB 의존성 없이도 컴파일러가 동작하도록 합니다.
    """

    def __init__(self):
        self._used_hashes: set = set()

    def seed_if_needed(self) -> None:
        """인메모리는 시드 불필요 (상수에서 직접 읽음)"""
        pass

    def is_duplicate(self, combo_hash: str) -> bool:
        return combo_hash in self._used_hashes

    def save_combination(self, combo_hash: str) -> None:
        self._used_hashes.add(combo_hash)

    def get_stats(self) -> dict:
        return {"mode": "in_memory_fallback", "tracked_hashes": len(self._used_hashes)}


# ============================================================
# ShortDramaCompiler
# ============================================================

class ShortDramaCompiler:
    """
    숫 드라마 전용 스토리 컴파일러

    5개 독립 축 기반 조합 + DB 연동 (중복 방지 / 가중치 학습).
    DB가 없으면 인메모리 폴백으로 동작합니다.

    사용법:
        from infrastructure.ai import StoryLLMProvider
        compiler = ShortDramaCompiler(llm_provider=StoryLLMProvider())
        result = await compiler.compile(
            category="연애 배신",
            tone="현실적",
            hint="남자가 여자친구의 비밀을 발견하는 이야기",  # optional
        )
    """

    def __init__(self, llm_provider=None, db=None):
        """
        Args:
            llm_provider: StoryLLMProvider 또는 호환 Provider
                          None이면 StoryLLMProvider 자동 생성
            db: StoryComponentDB 인스턴스. None이면 인메모리 폴백 사용.
        """
        if llm_provider is None:
            from infrastructure.ai import StoryLLMProvider
            llm_provider = StoryLLMProvider()
        self.llm = llm_provider
        self.validator = StoryValidator()

        # DB 연동 (없으면 인메모리 폴백)
        if db is not None:
            self.db = db
            self._use_db = True
        else:
            self.db = _InMemoryFallbackDB()
            self._use_db = False

        # DB 시드 데이터 확인
        self._ensure_components_seeded()

    # ----------------------------------------------------------
    # DB 시드 데이터 관리
    # ----------------------------------------------------------

    def _ensure_components_seeded(self):
        """DB가 비어있으면 시드 데이터 삽입"""
        if not self._use_db:
            # 인메모리 폴백은 시드 불필요
            self.db.seed_if_needed()
            logger.info("인메모리 폴백 모드로 동작")
            return

        try:
            stats = self.db.get_stats()
            # 컴포넌트가 이미 존재하면 스킵
            if stats.get("total_components", 0) > 0:
                logger.info("DB 시드 데이터 이미 존재 (%d개)", stats["total_components"])
                return
        except Exception:
            pass

        # 시드 데이터 삽입
        self._seed_components()
        logger.info("DB 시드 데이터 삽입 완료")

    def _seed_components(self):
        """각 축의 데이터를 DB에 저장"""
        # 축 1: Category
        self.db.add_components_bulk("category", CATEGORIES)

        # 축 2: Relationship (카테고리 그룹핑 포함)
        for relation, group in RELATIONSHIPS:
            self.db.add_component("relationship", relation, category_group=group)

        # 축 3: Secret Type (공통 풀)
        self.db.add_components_bulk("secret", SECRET_TYPES)

        # 축 4: Event Trigger (공통 풀)
        self.db.add_components_bulk("trigger", EVENT_TRIGGERS)

        # 축 5: Twist Pattern (공통 풀)
        self.db.add_components_bulk("twist", TWIST_PATTERNS)

    # ----------------------------------------------------------
    # 조합 생성 (핵심 로직)
    # ----------------------------------------------------------

    def _generate_formula(self, category: str = None) -> dict:
        """
        DB 기반 가중치 조합 생성 (논리 규칙 적용)

        로직:
            1. category 선택 (지정 또는 가중치 랜덤)
            2. relationship 선택 (category 그룹핑)
            3. secret 선택 (공통 풀, 가중치)
            4. trigger = TRIGGER_SECRET_COMPATIBILITY[secret]에서 가중치 선택
            5. twist = TWIST_SECRET_COMPATIBILITY[secret]에서 가중치 선택
            6. 중복 해시 확인 (최대 10회 재시도)

        Args:
            category: 카테고리 (None이면 가중치 랜덤)

        Returns:
            {category, relation, secret, conflict_event, twist, combo_hash}
        """
        for attempt in range(10):
            formula = self._try_generate_formula(category)
            if formula is None:
                continue

            # 중복 해시 확인
            combo_hash = self._compute_hash(formula)
            is_dup = self._check_duplicate(combo_hash)

            if not is_dup:
                formula["combo_hash"] = combo_hash
                logger.info(
                    "조합 생성 성공 (시도 %d): %s + %s + %s + %s + %s",
                    attempt + 1,
                    formula["category"],
                    formula["relation"],
                    formula["secret"],
                    formula["conflict_event"],
                    formula["twist"],
                )
                return formula

            logger.debug("중복 조합 감지, 재시도 (%d/10)", attempt + 1)

        logger.warning("10회 시도 후에도 고유 조합 생성 실패, 마지막 조합 반환")
        formula = self._try_generate_formula(category)
        if formula:
            formula["combo_hash"] = self._compute_hash(formula)
        return formula or {
            "category": category or "연애 배신",
            "relation": "연인",
            "secret": "바람",
            "conflict_event": "문자 발견",
            "twist": "사실 알고 있었다",
            "combo_hash": "fallback",
        }

    def _try_generate_formula(self, category: str = None) -> Optional[dict]:
        """단일 조합 생성 시도"""
        # 1. category 선택
        selected_category = category or self._pick_category()
        if not selected_category:
            return None

        # 2. relationship 선택 (category 그룹핑)
        relation = self._pick_relationship(selected_category)
        if not relation:
            return None

        # 3. secret 선택 (공통 풀)
        secret = self._pick_secret()
        if not secret:
            return None

        # 4. trigger = TRIGGER_SECRET_COMPATIBILITY[secret]에서 선택
        trigger = self._pick_trigger(secret)
        if not trigger:
            return None

        # 5. twist = TWIST_SECRET_COMPATIBILITY[secret]에서 선택
        twist = self._pick_twist(secret)
        if not twist:
            return None

        return {
            "category": selected_category,
            "relation": relation,
            "secret": secret,
            "conflict_event": trigger,
            "twist": twist,
        }

    def _pick_category(self) -> str:
        """카테고리 선택 (DB 가중치 또는 균등 랜덤)"""
        if self._use_db:
            result = self.db.weighted_select("category")
            return result.get("value", random.choice(CATEGORIES))
        return random.choice(CATEGORIES)

    def _pick_relationship(self, category: str) -> str:
        """관계 선택 (category 그룹핑)"""
        if self._use_db:
            result = self.db.weighted_select("relationship", category)
            return result.get("value", self._fallback_relationship(category))
        return self._fallback_relationship(category)

    def _fallback_relationship(self, category: str) -> str:
        """인메모리 폴백: 카테고리 그룹에서 관계 선택"""
        group = [r for r, g in RELATIONSHIPS if g == category]
        if group:
            return random.choice(group)
        # 그룹이 없으면 전체에서 선택
        all_rels = [r for r, g in RELATIONSHIPS]
        return random.choice(all_rels) if all_rels else "연인"

    def _pick_secret(self) -> str:
        """비밀 유형 선택 (공통 풀)"""
        if self._use_db:
            result = self.db.weighted_select("secret")
            return result.get("value", random.choice(SECRET_TYPES))
        return random.choice(SECRET_TYPES)

    def _pick_trigger(self, secret: str) -> str:
        """트리거 선택 (TRIGGER_SECRET_COMPATIBILITY 기반)"""
        compatible = TRIGGER_SECRET_COMPATIBILITY.get(secret, EVENT_TRIGGERS)
        if self._use_db:
            # DB에서 해당 트리거들의 가중치를 조회하여 가중치 선택
            result = self._weighted_pick_from_list("trigger", compatible)
            return result or random.choice(compatible)
        return random.choice(compatible)

    def _pick_twist(self, secret: str) -> str:
        """트위스트 선택 (TWIST_SECRET_COMPATIBILITY 기반)"""
        compatible = TWIST_SECRET_COMPATIBILITY.get(secret, TWIST_PATTERNS)
        if self._use_db:
            result = self._weighted_pick_from_list("twist", compatible)
            return result or random.choice(compatible)
        return random.choice(compatible)

    def _weighted_pick_from_list(self, component_type: str, allowed_values: List[str]) -> Optional[str]:
        """DB에서 특정 값 목록 내 가중치 기반 선택"""
        try:
            all_components = self.db.get_components(component_type)
            # 허용된 값만 필터링
            filtered = [c for c in all_components if c["value"] in allowed_values]
            if not filtered:
                return None
            weights = [c["weight"] for c in filtered]
            chosen = random.choices(filtered, weights=weights, k=1)[0]
            return chosen["value"]
        except Exception:
            return None

    @staticmethod
    def _compute_hash(formula: dict) -> str:
        """조합 해시 계산"""
        raw = (
            f"{formula['category']}|{formula['relation']}|"
            f"{formula['secret']}|{formula['conflict_event']}|{formula['twist']}"
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def _check_duplicate(self, combo_hash: str) -> bool:
        """중복 해시 확인 (DB 또는 인메모리)"""
        return self.db.is_duplicate(combo_hash)

    def _record_combination(self, formula: dict, story_title: str = ""):
        """조합 사용 이력 기록"""
        combo_hash = formula.get("combo_hash", self._compute_hash(formula))
        if self._use_db:
            try:
                self.db.save_combination(
                    {
                        "category": formula["category"],
                        "relationship": formula["relation"],
                        "secret": formula["secret"],
                        "trigger": formula["conflict_event"],
                        "twist": formula["twist"],
                        "hash": combo_hash,
                    },
                    story_title=story_title,
                )
            except Exception as e:
                logger.debug(f"조합 기록 스킵: {e}")
        else:
            self.db.save_combination(combo_hash)

    # ----------------------------------------------------------
    # compile (메인 인터페이스)
    # ----------------------------------------------------------

    async def compile(
        self,
        category: str = None,
        tone: str = "현실적",
        hint: str = None,
        max_retries: int = 2,
        language: str = None,
    ) -> CompileResult:
        """
        숫 드라마 스크립트 생성

        Args:
            category: 카테고리 키 (CATEGORIES 중 하나, None이면 가중치 랜덤)
            tone: 분위기 (현실적 / 자극적 / 감성적)
            hint: 스토리 힌트 (선택)
            max_retries: 검증 실패 시 최대 재시도 횟수

        Returns:
            CompileResult
        """
        # category 검증
        if category and category not in CATEGORIES:
            logger.warning(f"알 수 없는 카테고리: {category}, 랜덤 선택")
            category = None

        # 1. 공식 생성 (5개 독립 축 + 논리 규칙)
        formula = self._generate_formula(category)

        # 2. 프롬프트 구성
        prompt = self._build_prompt(formula["category"], formula, tone, hint, language)

        # 3. LLM 호출
        story_spec = await self._call_llm(prompt)

        if story_spec is None:
            return CompileResult(success=False, error="LLM 응답 파싱 실패")

        # 4. 조합 이력 기록
        self._record_combination(formula, story_spec.title)

        # 5. 검증 + 재시도 루프
        for attempt in range(max_retries + 1):
            validation = self.validator.validate(story_spec)

            if validation.is_valid:
                return CompileResult(
                    success=True,
                    story_spec=story_spec,
                    hook_score=self._extract_hook_score(story_spec),
                    retry_count=attempt,
                )

            # 마지막 시도면 자동 수정 후 반환
            if attempt >= max_retries:
                logger.warning(
                    f"Validation still failing after {max_retries} retries: "
                    f"{[e.message for e in validation.errors]}"
                )
                story_spec = self._auto_fix(story_spec, validation)
                final_validation = self.validator.validate(story_spec)
                return CompileResult(
                    success=final_validation.is_valid,
                    story_spec=story_spec,
                    hook_score=self._extract_hook_score(story_spec),
                    retry_count=attempt + 1,
                    error="" if final_validation.is_valid else "자동 수정 후에도 검증 실패",
                )

            # 재시도: LLM에게 에러 피드백과 함께 재요청
            logger.info(f"Validation failed (attempt {attempt + 1}), retrying...")
            formula_str = (
                f"{formula['relation']} + {formula['secret']} + "
                f"{formula['conflict_event']} + {formula['twist']}"
            )
            retry_prompt = DRAMA_RETRY_PROMPT.format(
                category=formula["category"],
                formula_str=formula_str,
                previous_json=story_spec.to_json(),
                errors=self._format_errors(validation),
            )
            # 재시도에도 언어 지시문 유지
            lang = language or (STORY_LANGUAGES[0] if STORY_LANGUAGES else "ko")
            if lang != "ko":
                lang_name = LANGUAGE_NAMES.get(lang, "Korean")
                lang_native = LANGUAGE_NATIVE_NAMES.get(lang, "한국어")
                retry_prompt += f"\n\nLANGUAGE: Write ALL content in {lang_name} ({lang_native})."
            fixed_spec = await self._call_llm(retry_prompt)
            if fixed_spec is not None:
                story_spec = fixed_spec

        return CompileResult(success=False, error="최대 재시도 초과")

    # ----------------------------------------------------------
    # 프롬프트 구성
    # ----------------------------------------------------------

    def _build_prompt(
        self,
        category_key: str,
        formula: dict,
        tone: str,
        hint: str = None,
        language: str = None,
    ) -> str:
        """LLM 프롬프트 구성"""
        hint_section = ""
        if hint and hint.strip():
            hint_section = f"HINT: {hint.strip()}\n(Use this hint as inspiration but follow the formula structure)"

        base = DRAMA_USER_PROMPT.format(
            category=category_key,
            relation=formula["relation"],
            secret=formula["secret"],
            conflict_event=formula["conflict_event"],
            twist=formula["twist"],
            tone=tone,
            hint_section=hint_section,
        )

        # 언어 지시문 추가
        lang = language or (STORY_LANGUAGES[0] if STORY_LANGUAGES else "ko")
        if lang != "ko":  # ko가 아닌 경우에만 명시적 지시 (기본 프롬프트가 이미 한국어)
            lang_name = LANGUAGE_NAMES.get(lang, "Korean")
            lang_native = LANGUAGE_NATIVE_NAMES.get(lang, "한국어")
            base += f"\n\nLANGUAGE INSTRUCTION: Title, dialogue, and narration MUST be written in {lang_name} ({lang_native}). Visual description fields (action, appearance, location, camera, mood) MUST be in English for image generation AI. Ignore the Korean dialogue rule above - write ALL dialogue in {lang_name}."

        return base

    # ----------------------------------------------------------
    # LLM 호출
    # ----------------------------------------------------------

    async def _call_llm(self, prompt: str) -> Optional[StorySpec]:
        """LLM 호출 및 응답 파싱"""
        if self.llm is None:
            logger.error("LLM Provider가 설정되지 않았습니다.")
            return None

        try:
            response_text = await self.llm._call_api(
                system_prompt=DRAMA_SYSTEM_PROMPT,
                user_message=prompt,
            )
            return self._parse_response(response_text)
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return None

    def _parse_response(self, response: str) -> Optional[StorySpec]:
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
            return self._dict_to_story_spec(data)
        except Exception as e:
            logger.error(f"StorySpec 변환 실패: {e}")
            return None

    def _dict_to_story_spec(self, data: Dict[str, Any]) -> StorySpec:
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

        # 아크 변환 (드라마 5단계 -> ArcSpec 4필드에 매핑)
        arc_data = data.get("arc", {})
        arc = ArcSpec(
            hook=arc_data.get("hook", ""),
            build=arc_data.get("setup", arc_data.get("build", "")),
            climax=arc_data.get("conflict", arc_data.get("climax", "")),
            resolution=arc_data.get("ending", arc_data.get("resolution", "")),
        )

        # 씬 변환 (act -> purpose 매핑)
        scenes = []
        for s in data.get("scenes", []):
            # act 필드를 ScenePurpose로 변환
            act = s.get("act", "setup")
            purpose = ACT_TO_PURPOSE.get(act, ScenePurpose.BUILD)

            # purpose 필드가 있으면 우선 사용 (act가 없는 경우)
            if "purpose" in s and "act" not in s:
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

        # 메타데이터 구성 (드라마 전용 정보 포함)
        metadata = {
            "source": "short_drama_compiler",
            "category": data.get("category", ""),
            "formula": data.get("formula", {}),
            "caption": data.get("caption", ""),
            "hook_score": data.get("hook_score", {}),
        }

        # 총 길이 계산
        total_duration = sum(s.duration for s in scenes) if scenes else 0.0

        return StorySpec(
            title=data.get("title", "Untitled"),
            genre=data.get("genre", "drama"),
            target=TargetFormat.SHORTS,
            duration=total_duration,
            characters=characters,
            arc=arc,
            scenes=scenes,
            emotion_curve=data.get("emotion_curve", []),
            metadata=metadata,
        )

    # ----------------------------------------------------------
    # 검증 보조
    # ----------------------------------------------------------

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

    def _auto_fix(self, spec: StorySpec, validation: ValidationResult) -> StorySpec:
        """검증 실패 시 자동 수정 (숫 드라마 제약에 맞게)"""
        for err in validation.errors:
            # Duration 수정
            if "duration" in err.field.lower():
                total = spec.total_duration() if hasattr(spec, 'total_duration') else sum(s.duration for s in spec.scenes)
                min_d = SHORT_DRAMA_CONSTRAINTS["min_duration"]

                # 최소 길이 미달 시 scale up
                if total < min_d:
                    scale = min_d / max(total, 0.1)
                    for s in spec.scenes:
                        s.duration = round(s.duration * scale, 1)

                # 최대 길이 초과 시 (max_duration이 설정된 경우)
                max_d = SHORT_DRAMA_CONSTRAINTS.get("max_duration")
                if max_d and total > max_d:
                    scale = max_d / max(total, 0.1)
                    for s in spec.scenes:
                        s.duration = max(1.5, round(s.duration * scale, 1))

            # Scene 수 수정
            if "scene" in err.field.lower() and "count" in err.field.lower():
                min_s = SHORT_DRAMA_CONSTRAINTS["min_scenes"]
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

                max_s = SHORT_DRAMA_CONSTRAINTS.get("max_scenes")
                if max_s and len(spec.scenes) > max_s:
                    # CLIMAX purpose 씬은 유지하면서 뒤에서 제거
                    while len(spec.scenes) > max_s:
                        spec.scenes.pop(-2)  # 마지막(resolution)은 유지

        # Duration 재계산
        spec.duration = sum(s.duration for s in spec.scenes)
        return spec

    # ----------------------------------------------------------
    # 유틸리티
    # ----------------------------------------------------------

    @staticmethod
    def list_categories() -> List[str]:
        """사용 가능한 카테고리 목록"""
        return list(CATEGORIES)

    @staticmethod
    def list_relationships(category: str = None) -> List[Tuple[str, str]]:
        """관계 목록 (category로 필터링 가능)"""
        if category:
            return [(r, g) for r, g in RELATIONSHIPS if g == category]
        return list(RELATIONSHIPS)

    @staticmethod
    def list_secret_types() -> List[str]:
        """비밀 유형 목록"""
        return list(SECRET_TYPES)

    @staticmethod
    def list_triggers(secret: str = None) -> List[str]:
        """트리거 목록 (secret으로 필터링 가능)"""
        if secret:
            return list(TRIGGER_SECRET_COMPATIBILITY.get(secret, EVENT_TRIGGERS))
        return list(EVENT_TRIGGERS)

    @staticmethod
    def list_twists(secret: str = None) -> List[str]:
        """트위스트 목록 (secret으로 필터링 가능)"""
        if secret:
            return list(TWIST_SECRET_COMPATIBILITY.get(secret, TWIST_PATTERNS))
        return list(TWIST_PATTERNS)

    def get_db_stats(self) -> dict:
        """DB 통계 조회"""
        return self.db.get_stats()
