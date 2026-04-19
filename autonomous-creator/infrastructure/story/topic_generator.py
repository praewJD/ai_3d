"""
Topic Generator - 조회수 기반 주제 생성기

스토리 입력에서 바이럴 가능성이 높은 주제 생성
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class TopicResult:
    """주제 생성 결과"""
    theme: str  # 핵심 테마 (예: "Sacrifice vs Survival")
    message: str  # 전달 메시지
    conflict: str  # 갈등 요소
    viral_hooks: List[str] = field(default_factory=list)  # 바이럴 가능성 높은 훅들

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "theme": self.theme,
            "message": self.message,
            "conflict": self.conflict,
            "viral_hooks": self.viral_hooks
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicResult":
        """딕셔너리에서 생성"""
        return cls(**data)


class TopicGenerator:
    """조회수 기반 주제 생성기"""

    # 조회수 높은 테마 템플릿
    VIRAL_THEMES = [
        "betrayal and revenge",
        "hidden power awakening",
        "impossible choice",
        "sacrifice for loved ones",
        "underdog rises",
        "dark secret revealed",
        "time running out",
        "forbidden love",
        "survival against odds",
        "identity crisis",
        "redemption arc",
        "truth unveiled",
        "power corrupts",
        "love conquers all",
        "revenge is sweet"
    ]

    # 장르별 선호 테마 매핑
    GENRE_THEMES = {
        "action": ["revenge", "survival", "power", "justice", "redemption"],
        "romance": ["forbidden love", "sacrifice", "second chance", "true love", "heartbreak"],
        "horror": ["dark secret", "survival", "fear", "unknown", "possession"],
        "scifi": ["identity", "technology vs humanity", "unknown", "evolution", "control"],
        "fantasy": ["destiny", "power", "sacrifice", "good vs evil", "transformation"],
        "drama": ["family", "secrets", "redemption", "sacrifice", "truth"],
        "comedy": ["misunderstanding", "irony", "unexpected", "chaos", "transformation"]
    }

    # 갈등 유형 템플릿
    CONFLICT_TEMPLATES = {
        "internal": [
            "wants {goal} but fears {fear}",
            "must choose between {choice_a} and {choice_b}",
            "struggles with {struggle}"
        ],
        "external": [
            "{char_a} vs {char_b}",
            "society vs individual",
            "nature vs survival",
            "past vs future"
        ],
        "interpersonal": [
            "trust betrayed by {char}",
            "love tested by {obstacle}",
            "friendship strained by {secret}"
        ]
    }

    # 바이럴 훅 템플릿
    VIRAL_HOOK_TEMPLATES = {
        "shock": [
            "The moment everything changed...",
            "No one saw this coming...",
            "This changes everything...",
            "Wait for it..."
        ],
        "curiosity": [
            "What would you do if...",
            "The secret they never told you...",
            "Why did {char} do this?",
            "The truth behind..."
        ],
        "emotion": [
            "This will make you cry...",
            "The most heartbreaking moment...",
            "You won't believe this ending...",
            "Love conquers all..."
        ],
        "action": [
            "The chase begins...",
            "One chance to survive...",
            "Against all odds...",
            "The final showdown..."
        ]
    }

    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: LLM Provider (선택적)
        """
        self.llm = llm_provider

    def generate(self, normalized_input) -> TopicResult:
        """
        정제된 입력에서 주제 생성

        Args:
            normalized_input: NormalizedInput 객체

        Returns:
            TopicResult 객체
        """
        # 1. 입력에서 핵심 갈등 찾기
        theme = self._extract_theme(normalized_input)

        # 2. 바이럴 테마와 매칭/강화
        theme = self.enhance_for_virality(theme, normalized_input.genre)

        # 3. 메시지 추출
        message = self._extract_message(normalized_input, theme)

        # 4. 갈등 요소 생성
        characters = normalized_input.characters[:3] if normalized_input.characters else ["protagonist"]
        conflict = self.generate_conflict(theme, characters)

        # 5. 바이럴 훅 생성
        viral_hooks = self.generate_viral_hooks(theme, count=3)

        return TopicResult(
            theme=theme,
            message=message,
            conflict=conflict,
            viral_hooks=viral_hooks
        )

    def _extract_theme(self, normalized_input) -> str:
        """입력에서 핵심 테마 추출"""
        text = normalized_input.raw_text.lower()

        # 키워드 기반 테마 매칭
        theme_keywords = {
            "betrayal": ["betray", "backstab", "traitor", "배신", "반역"],
            "revenge": ["revenge", "vengeance", "retaliate", "복수", "응징"],
            "sacrifice": ["sacrifice", "give up", "forfeit", "희생", "포기"],
            "survival": ["survive", "escape", "flee", "생존", "탈출"],
            "love": ["love", "romance", "heart", "사랑", "연애"],
            "power": ["power", "strength", "control", "권력", "힘"],
            "secret": ["secret", "hidden", "mystery", "비밀", "숨겨진"],
            "identity": ["identity", "who am i", "real self", "정체", "자아"]
        }

        for theme, keywords in theme_keywords.items():
            if any(kw in text for kw in keywords):
                return theme

        # 기본값: 장르 기반
        genre_themes = self.GENRE_THEMES.get(normalized_input.genre, ["destiny"])
        return random.choice(genre_themes)

    def enhance_for_virality(self, theme: str, genre: str) -> str:
        """
        조회수 높게 테마 강화

        Args:
            theme: 기본 테마
            genre: 장르

        Returns:
            강화된 테마
        """
        # 이미 바이럴 테마인지 확인
        for viral_theme in self.VIRAL_THEMES:
            if theme.lower() in viral_theme.lower():
                return viral_theme

        # 장르별 테마와 결합
        genre_themes = self.GENRE_THEMES.get(genre, [])

        # 테마 조합 생성
        if genre_themes:
            secondary = random.choice(genre_themes)
            if secondary.lower() != theme.lower():
                return f"{theme} vs {secondary}"

        return theme

    def generate_conflict(self, theme: str, characters: List[str]) -> str:
        """
        갈등 요소 생성

        Args:
            theme: 테마
            characters: 캐릭터 리스트

        Returns:
            갈등 설명 문자열
        """
        # 테마 기반 갈등 선택
        if theme in ["betrayal", "revenge"]:
            template = random.choice(self.CONFLICT_TEMPLATES["interpersonal"])
            char = characters[1] if len(characters) > 1 else "trusted ally"
            return template.format(char=char, obstacle="betrayal", secret="truth")

        elif theme in ["sacrifice", "survival"]:
            template = random.choice(self.CONFLICT_TEMPLATES["internal"])
            return template.format(
                goal="what they want",
                fear="losing everything",
                choice_a="duty",
                choice_b="desire",
                struggle="an impossible choice"
            )

        elif theme in ["love", "forbidden love"]:
            template = random.choice(self.CONFLICT_TEMPLATES["interpersonal"])
            char = characters[1] if len(characters) > 1 else "loved one"
            return template.format(char=char, obstacle="circumstances", secret="feelings")

        elif theme in ["power", "identity"]:
            template = random.choice(self.CONFLICT_TEMPLATES["external"])
            char_a = characters[0] if characters else "hero"
            char_b = characters[1] if len(characters) > 1 else "antagonist"
            return template.format(char_a=char_a, char_b=char_b)

        else:
            # 기본 갈등
            return f"Internal struggle between {theme} and reality"

    def generate_viral_hooks(self, theme: str, count: int = 3) -> List[str]:
        """
        바이럴 훅 생성

        Args:
            theme: 테마
            count: 생성할 훅 수

        Returns:
            바이럴 훅 리스트
        """
        hooks = []

        # 테마에 맞는 훅 카테고리 선택
        hook_categories = []
        if theme in ["betrayal", "revenge", "secret", "identity"]:
            hook_categories.extend(["shock", "curiosity"])
        elif theme in ["love", "sacrifice"]:
            hook_categories.extend(["emotion"])
        elif theme in ["survival", "power"]:
            hook_categories.extend(["action", "shock"])
        else:
            hook_categories = ["shock", "curiosity", "emotion"]

        # 선택된 카테고리에서 훅 선택
        used_templates = set()
        for _ in range(count):
            category = random.choice(hook_categories)
            templates = self.VIRAL_HOOK_TEMPLATES.get(category, [])

            available = [t for t in templates if t not in used_templates]
            if available:
                template = random.choice(available)
                used_templates.add(template)

                # 템플릿에 테마 적용
                hook = template.format(char="the hero", theme=theme)
                hooks.append(hook)

        return hooks

    def _extract_message(self, normalized_input, theme: str) -> str:
        """메시지 추출"""
        # 테마 기반 메시지 템플릿
        message_templates = {
            "betrayal": "Trust carefully, for not everyone is who they seem.",
            "revenge": "Revenge may satisfy, but it comes at a cost.",
            "sacrifice": "Sometimes we must give up everything for what matters most.",
            "survival": "The human spirit can endure anything.",
            "love": "Love is worth fighting for.",
            "power": "True power comes from within.",
            "secret": "The truth will always find a way out.",
            "identity": "Be true to who you are."
        }

        return message_templates.get(theme, f"Every story teaches us something about {theme}.")


class LLMTopicGenerator(TopicGenerator):
    """LLM 기반 고급 주제 생성기"""

    GENERATE_PROMPT = """You are a viral content strategist specializing in short-form video.

Analyze this story and create:
1. A compelling theme (2-4 words that capture the essence)
2. A clear message (one impactful sentence)
3. A central conflict (who vs what)
4. 3 viral hook ideas optimized for engagement (shock/curiosity/emotion based)

Story Input:
- Raw text: {raw_text}
- Characters: {characters}
- Genre: {genre}
- Tone: {tone}
- Key events: {events}

Return ONLY a valid JSON object:
{{
    "theme": "2-4 word theme",
    "message": "one sentence message",
    "conflict": "description of the central conflict",
    "viral_hooks": ["hook1", "hook2", "hook3"]
}}

Optimize for:
- High engagement potential
- Emotional impact
- Curiosity gap
- Shareability"""

    def __init__(self, llm_provider):
        """
        Args:
            llm_provider: LLM Provider (필수)
        """
        super().__init__(llm_provider)

        if not llm_provider:
            raise ValueError("LLM Provider is required for LLMTopicGenerator")

    async def generate_with_llm(self, normalized_input) -> TopicResult:
        """
        LLM으로 정교한 주제 생성

        Args:
            normalized_input: NormalizedInput 객체

        Returns:
            TopicResult 객체
        """
        try:
            prompt = self.GENERATE_PROMPT.format(
                raw_text=normalized_input.raw_text[:1500],
                characters=", ".join(normalized_input.characters[:5]),
                genre=normalized_input.genre,
                tone=normalized_input.tone,
                events="; ".join(normalized_input.key_events[:3])
            )

            result = await self.llm.generate_json(
                prompt=prompt,
                temperature=0.7  # 창의성을 위해 약간 높게
            )

            return TopicResult(
                theme=result.get("theme", "destiny"),
                message=result.get("message", "Every journey changes us."),
                conflict=result.get("conflict", "Internal struggle"),
                viral_hooks=result.get("viral_hooks", [])
            )

        except Exception as e:
            logger.warning(f"LLM topic generation failed, falling back to rule-based: {e}")
            # LLM 실패 시 규칙 기반으로 폴백
            return self.generate(normalized_input)

    async def generate_alternative_themes(self, normalized_input, count: int = 3) -> List[str]:
        """
        LLM으로 대안 테마 생성

        Args:
            normalized_input: NormalizedInput 객체
            count: 생성할 테마 수

        Returns:
            대안 테마 리스트
        """
        prompt = f"""Based on this story, suggest {count} alternative themes.

Story: {normalized_input.raw_text[:1000]}
Genre: {normalized_input.genre}

Return ONLY a JSON array of {count} theme strings, each 2-4 words.
Themes should be distinct and optimized for viral potential."""

        try:
            result = await self.llm.generate_json(prompt=prompt, temperature=0.8)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"Alternative theme generation failed: {e}")
            return random.sample(self.VIRAL_THEMES, min(count, len(self.VIRAL_THEMES)))

    async def optimize_for_platform(
        self,
        topic_result: TopicResult,
        platform: str = "youtube_shorts"
    ) -> TopicResult:
        """
        플랫폼별 최적화

        Args:
            topic_result: 원본 TopicResult
            platform: 플랫폼 이름 (youtube_shorts, tiktok, instagram_reels)

        Returns:
            최적화된 TopicResult
        """
        platform_guidelines = {
            "youtube_shorts": {
                "max_hook_length": 50,
                "style": "curiosity-driven",
                "focus": "retention"
            },
            "tiktok": {
                "max_hook_length": 30,
                "style": "trend-aware",
                "focus": "engagement"
            },
            "instagram_reels": {
                "max_hook_length": 40,
                "style": "visual-focused",
                "focus": "aesthetics"
            }
        }

        guidelines = platform_guidelines.get(platform, platform_guidelines["youtube_shorts"])

        # 훅 길이 최적화
        optimized_hooks = []
        for hook in topic_result.viral_hooks:
            if len(hook) > guidelines["max_hook_length"]:
                hook = hook[:guidelines["max_hook_length"]-3] + "..."
            optimized_hooks.append(hook)

        return TopicResult(
            theme=topic_result.theme,
            message=topic_result.message,
            conflict=topic_result.conflict,
            viral_hooks=optimized_hooks
        )
