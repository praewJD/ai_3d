"""
Story Normalizer - 입력 스토리 정제기

자유 형식의 스토리 입력을 구조화된 데이터로 변환
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizedInput:
    """정제된 입력"""
    raw_text: str
    characters: List[str] = field(default_factory=list)  # 추출된 캐릭터 이름들
    genre: str = "drama"  # 추정된 장르
    tone: str = "neutral"  # 밝음/어두움/중립
    setting: str = ""  # 배경
    key_events: List[str] = field(default_factory=list)  # 주요 이벤트
    language: str = "ko"  # ko/en/etc

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "raw_text": self.raw_text,
            "characters": self.characters,
            "genre": self.genre,
            "tone": self.tone,
            "setting": self.setting,
            "key_events": self.key_events,
            "language": self.language
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedInput":
        """딕셔너리에서 생성"""
        return cls(**data)


class StoryNormalizer:
    """입력 스토리 정제기"""

    # 장르 키워드 매핑
    GENRE_KEYWORDS = {
        "action": ["fight", "battle", "combat", "explosion", "chase", "gun", "martial arts",
                   "전투", "싸움", "액션", "총", "폭발", "추격"],
        "romance": ["love", "kiss", "relationship", "heart", "date", "marriage", "passion",
                    "사랑", "연애", "키스", "데이트", "결혼", "로맨스"],
        "horror": ["scary", "ghost", "monster", "death", "blood", "fear", "nightmare", "creepy",
                   "공포", "유령", "괴물", "죽음", "피", "악몽"],
        "scifi": ["space", "future", "robot", "alien", "technology", "cyber", "AI", "spaceship",
                  "우주", "미래", "로봇", "외계인", "기술", "사이버"],
        "fantasy": ["magic", "wizard", "dragon", "kingdom", "spell", "fantasy", "mythical",
                    "마법", "마법사", "용", "왕국", "주문", "판타지"],
        "drama": ["family", "friendship", "life", "emotion", "struggle", "conflict", "secret",
                  "가족", "우정", "인생", "감정", "갈등", "비밀", "드라마"],
        "comedy": ["funny", "laugh", "joke", "humor", "comedy", "silly", "hilarious",
                   "웃기", "유머", "코미디", "재미", "웃음"]
    }

    # 톤 분석 키워드
    BRIGHT_KEYWORDS = ["happy", "joy", "love", "hope", "bright", "sunny", "cheerful", "optimistic",
                       "행복", "기쁨", "사랑", "희망", "밝음", "즐거움", "긍정"]
    DARK_KEYWORDS = ["dark", "sad", "tragic", "death", "fear", "anger", "despair", "gloomy",
                     "어둠", "슬픔", "비극", "죽음", "공포", "분노", "절망", "우울"]

    # 한국어/영어 감지 패턴
    KO_PATTERN = re.compile(r'[가-힣]+')
    EN_PATTERN = re.compile(r'[a-zA-Z]+')

    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: LLM Provider (선택적, 고급 기능용)
        """
        self.llm = llm_provider

    def normalize(self, raw_text: str) -> NormalizedInput:
        """
        자유 형식 입력을 정제

        Args:
            raw_text: 원본 텍스트

        Returns:
            NormalizedInput 객체
        """
        if not raw_text or not raw_text.strip():
            return NormalizedInput(raw_text="")

        # 1. 언어 감지
        language = self.detect_language(raw_text)

        # 2. 캐릭터 추출
        characters = self.extract_characters(raw_text)

        # 3. 장르 추정
        genre = self.detect_genre(raw_text)

        # 4. 톤 분석
        tone = self.analyze_tone(raw_text)

        # 5. 배경 추출
        setting = self.extract_setting(raw_text)

        # 6. 주요 이벤트 추출
        key_events = self.extract_key_events(raw_text)

        return NormalizedInput(
            raw_text=raw_text,
            characters=characters,
            genre=genre,
            tone=tone,
            setting=setting,
            key_events=key_events,
            language=language
        )

    def extract_characters(self, text: str) -> List[str]:
        """
        텍스트에서 캐릭터 이름 추출

        전략:
        1. 따옴표 내 이름 ("철수", 'John')
        2. 대문자로 시작하는 연속 단어 (영어)
        3. 한국어 이름 패턴 (2-4글자 고유명사)
        """
        characters = set()

        # 1. 따옴표 내 이름 추출
        quoted_names = re.findall(r'["\']([A-Za-z가-힣\s]+)["\']', text)
        for name in quoted_names:
            name = name.strip()
            if 1 < len(name) < 20:  # 합리적인 이름 길이
                characters.add(name)

        # 2. 영어 대문자 시작 이름 (연속된 대문자 단어들)
        english_names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        for name in english_names:
            # 일반 명사 필터링
            if name.lower() not in ['the', 'a', 'an', 'this', 'that', 'he', 'she', 'they']:
                characters.add(name)

        # 3. 한국어 이름 패턴 (2-4글자, 보통 명사 아님)
        korean_names = re.findall(r'([가-힣]{2,4})(?:이|가|은|는|을|를|와|과)', text)
        for name in korean_names:
            # 흔한 일반 명사 필터링
            common_words = ['오늘', '내일', '어제', '지금', '이곳', '저곳', '사람', '시간', '이야기']
            if name not in common_words:
                characters.add(name)

        # 최대 10개로 제한
        return list(characters)[:10]

    def detect_genre(self, text: str) -> str:
        """
        장르 감지 (action, romance, horror, scifi, fantasy, drama, comedy)

        키워드 빈도 기반 분석
        """
        text_lower = text.lower()
        scores = {}

        for genre, keywords in self.GENRE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[genre] = score

        if not scores:
            return "drama"  # 기본값

        # 가장 높은 점수의 장르 반환
        return max(scores, key=scores.get)

    def analyze_tone(self, text: str) -> str:
        """
        톤 분석 (bright, dark, neutral)

        감정 키워드 기반 분석
        """
        text_lower = text.lower()

        bright_count = sum(1 for kw in self.BRIGHT_KEYWORDS if kw.lower() in text_lower)
        dark_count = sum(1 for kw in self.DARK_KEYWORDS if kw.lower() in text_lower)

        if bright_count > dark_count + 1:
            return "bright"
        elif dark_count > bright_count + 1:
            return "dark"
        else:
            return "neutral"

    def detect_language(self, text: str) -> str:
        """
        언어 감지

        한국어/영어 비율 기반
        """
        korean_matches = len(self.KO_PATTERN.findall(text))
        english_matches = len(self.EN_PATTERN.findall(text))

        if korean_matches > english_matches:
            return "ko"
        elif english_matches > 0:
            return "en"
        else:
            return "unknown"

    def extract_setting(self, text: str) -> str:
        """
        배경 추출

        장소 키워드 추출
        """
        # 한국어 장소 패턴
        ko_settings = re.findall(
            r'([가-힣]+(?:시|도|군|구|읍|면|동|역|공원|학교|회사|집|병원|카페|식당|호텔|바다|산|숲|마을|성|왕국))',
            text
        )

        # 영어 장소 패턴
        en_settings = re.findall(
            r'(?:in|at|near|inside|outside)\s+([A-Z][a-z]+(?:\s+[a-z]+)?)',
            text,
            re.IGNORECASE
        )

        settings = ko_settings + en_settings
        return settings[0] if settings else ""

    def extract_key_events(self, text: str) -> List[str]:
        """
        주요 이벤트 추출

        문장 단위 분리 후 중요도 평가
        """
        # 문장 분리
        sentences = re.split(r'[.!?。！？\n]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        # 이벤트성 키워드
        event_keywords = [
            "발견", "만나", "떠나", "돌아오", "죽", "살아남", "싸우", "이기", "지",
            "discover", "meet", "leave", "return", "die", "survive", "fight", "win", "lose",
            "reveal", "betray", "save", "destroy", "create", "change"
        ]

        events = []
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in event_keywords):
                events.append(sentence[:100])  # 최대 100자

        return events[:5]  # 최대 5개


class LLMNormalizer(StoryNormalizer):
    """LLM을 사용한 고급 정제"""

    NORMALIZE_PROMPT = """Analyze this story input and extract structured information.

Input: {raw_text}

Return ONLY a valid JSON object with this exact structure:
{{
    "characters": ["list of character names"],
    "genre": "one of: action, romance, horror, scifi, fantasy, drama, comedy",
    "tone": "one of: bright, dark, neutral",
    "setting": "main location/setting description",
    "key_events": ["list of 3-5 key events"],
    "language": "language code (ko, en, etc)"
}}

Important: Return ONLY the JSON, no explanation or markdown."""

    def __init__(self, llm_provider):
        """
        Args:
            llm_provider: LLM Provider (필수)
        """
        super().__init__(llm_provider)

        if not llm_provider:
            raise ValueError("LLM Provider is required for LLMNormalizer")

    async def normalize_with_llm(self, raw_text: str) -> NormalizedInput:
        """
        LLM으로 정제 (더 정확하지만 비용 발생)

        Args:
            raw_text: 원본 텍스트

        Returns:
            NormalizedInput 객체
        """
        if not raw_text or not raw_text.strip():
            return NormalizedInput(raw_text="")

        try:
            # LLM으로 분석
            prompt = self.NORMALIZE_PROMPT.format(raw_text=raw_text[:2000])  # 텍스트 길이 제한

            result = await self.llm.generate_json(
                prompt=prompt,
                temperature=0.3
            )

            return NormalizedInput(
                raw_text=raw_text,
                characters=result.get("characters", []),
                genre=result.get("genre", "drama"),
                tone=result.get("tone", "neutral"),
                setting=result.get("setting", ""),
                key_events=result.get("key_events", []),
                language=result.get("language", "unknown")
            )

        except Exception as e:
            logger.warning(f"LLM normalization failed, falling back to rule-based: {e}")
            # LLM 실패 시 규칙 기반으로 폴백
            return self.normalize(raw_text)

    async def enhance_characters(self, text: str, basic_characters: List[str]) -> List[Dict[str, Any]]:
        """
        LLM으로 캐릭터 정보 보강

        Args:
            text: 원본 텍스트
            basic_characters: 기본 추출된 캐릭터 이름들

        Returns:
            보강된 캐릭터 정보 리스트
        """
        prompt = f"""Based on this story text, provide detailed information about these characters.

Text: {text[:1500]}
Characters: {', '.join(basic_characters)}

Return ONLY a valid JSON array:
[
    {{
        "name": "character name",
        "role": "protagonist/antagonist/supporting",
        "traits": ["trait1", "trait2"],
        "motivation": "what drives this character"
    }}
]"""

        try:
            result = await self.llm.generate_json(prompt=prompt, temperature=0.3)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"Character enhancement failed: {e}")
            return [{"name": name, "role": "unknown"} for name in basic_characters]
