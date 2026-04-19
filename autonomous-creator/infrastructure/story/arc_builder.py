"""
Arc Builder - 4-Act Story Arc Construction

4-Act 구조 (기승전결 압축)를 생성하는 빌더 모듈
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import json

from .story_spec import ArcSpec


@dataclass
class ArcResult:
    """아크 생성 결과"""
    hook: str  # 0~3초 임팩트
    build: str  # 갈등 고조
    climax: str  # 절정
    resolution: str  # 해결/여운

    def to_arc_spec(self) -> ArcSpec:
        """ArcSpec으로 변환"""
        return ArcSpec(
            hook=self.hook,
            build=self.build,
            climax=self.climax,
            resolution=self.resolution
        )

    def to_dict(self) -> Dict[str, str]:
        """딕셔너리로 변환"""
        return {
            "hook": self.hook,
            "build": self.build,
            "climax": self.climax,
            "resolution": self.resolution
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ArcResult":
        """딕셔너리에서 생성"""
        return cls(
            hook=data.get("hook", ""),
            build=data.get("build", ""),
            climax=data.get("climax", ""),
            resolution=data.get("resolution", "")
        )


class ArcBuilder:
    """4-Act 구조 빌더 (기승전결 압축)"""

    # 아크 템플릿
    ARC_TEMPLATES = {
        "action": {
            "hook": "sudden attack / danger appears",
            "build": "struggle escalates / allies join",
            "climax": "final confrontation / power unleashed",
            "resolution": "victory / sacrifice / cliffhanger"
        },
        "mystery": {
            "hook": "strange discovery / question raised",
            "build": "clues found / suspects emerge",
            "climax": "truth revealed / twist",
            "resolution": "answer / new mystery"
        },
        "drama": {
            "hook": "emotional shock / relationship crisis",
            "build": "tension rises / choices made",
            "climax": "confrontation / breakdown",
            "resolution": "reconciliation / goodbye / growth"
        },
        "comedy": {
            "hook": "awkward situation / misunderstanding",
            "build": "chaos escalates / funny complications",
            "climax": "peak absurdity / reveal moment",
            "resolution": "laugh / relief / setup for more"
        },
        "horror": {
            "hook": "creepy occurrence / wrong feeling",
            "build": "fear grows / threats multiply",
            "climax": "terror peak / confrontation with horror",
            "resolution": "escape / trap / lingering dread"
        },
        "romance": {
            "hook": "unexpected encounter / spark",
            "build": "connection deepens / obstacles appear",
            "climax": "confession / grand gesture",
            "resolution": "together / apart / open ending"
        },
        "thriller": {
            "hook": "suspicious event / immediate danger",
            "build": "chase / investigation / stakes rise",
            "climax": "confrontation / revelation",
            "resolution": "solved / escaped / twist ending"
        },
        "default": {
            "hook": "attention-grabbing opening / question raised",
            "build": "development / conflict introduction",
            "climax": "peak moment / turning point",
            "resolution": "conclusion / aftermath / hook for next"
        }
    }

    # Hook 필수 요소 키워드
    HOOK_KEYWORDS = ["shock", "curiosity", "danger", "question", "sudden", "unexpected",
                     "mystery", "conflict", "crisis", "surprise", "discover"]

    def __init__(self, llm_provider=None):
        """
        초기화

        Args:
            llm_provider: LLM 제공자 (선택적, LLMArcBuilder에서 사용)
        """
        self.llm = llm_provider

    def build(self, topic_result: Optional[Dict[str, Any]] = None,
              normalized_input: Optional[Dict[str, Any]] = None) -> ArcResult:
        """
        주제와 입력에서 4-Act 구조 생성

        Args:
            topic_result: 주제 분석 결과
            normalized_input: 정규화된 입력 데이터

        Returns:
            ArcResult: 생성된 아크
        """
        # 1. 장르에 맞는 템플릿 선택
        genre = self._extract_genre(topic_result, normalized_input)
        template = self.select_template(genre)

        # 2. 캐릭터/설정 주입
        characters = self._extract_characters(normalized_input)
        setting = self._extract_setting(normalized_input)

        # 3. 각 단계 구체화
        hook = self._customize_act(template["hook"], "hook", characters, setting, topic_result)
        build = self._customize_act(template["build"], "build", characters, setting, topic_result)
        climax = self._customize_act(template["climax"], "climax", characters, setting, topic_result)
        resolution = self._customize_act(template["resolution"], "resolution", characters, setting, topic_result)

        # 4. Hook 임팩트 강화
        hook = self.ensure_hook_impact(hook)

        return ArcResult(
            hook=hook,
            build=build,
            climax=climax,
            resolution=resolution
        )

    def select_template(self, genre: str) -> dict:
        """
        장르별 템플릿 선택

        Args:
            genre: 장르명

        Returns:
            dict: 선택된 템플릿
        """
        genre_lower = genre.lower() if genre else "default"
        return self.ARC_TEMPLATES.get(genre_lower, self.ARC_TEMPLATES["default"])

    def ensure_hook_impact(self, hook: str) -> str:
        """
        Hook가 충분히 임팩트 있는지 확인/강화

        Args:
            hook: 원본 hook 문장

        Returns:
            str: 강화된 hook
        """
        if not hook:
            return "Something unexpected happens that changes everything."

        # Hook 필수 요소 확인: shock, curiosity, danger, question
        hook_lower = hook.lower()
        has_impact = any(kw in hook_lower for kw in self.HOOK_KEYWORDS)

        if not has_impact:
            # 임팩트 키워드 추가
            impact_prefixes = [
                "Suddenly, ",
                "Unexpectedly, ",
                "Without warning, ",
                "In a shocking moment, "
            ]
            import random
            prefix = random.choice(impact_prefixes)
            hook = f"{prefix}{hook[0].lower()}{hook[1:]}" if len(hook) > 1 else f"{prefix}{hook}"

        return hook

    def validate_arc(self, arc: ArcResult) -> List[str]:
        """
        아크 검증, 문제점 목록 반환

        Args:
            arc: 검증할 아크

        Returns:
            List[str]: 문제점 목록
        """
        errors = []

        # Hook 검증
        if not arc.hook or len(arc.hook.split()) < 5:
            errors.append("Hook too short or empty - needs more impact")
        if not self._has_hook_impact(arc.hook):
            errors.append("Hook lacks impact keywords (shock, curiosity, danger, question)")

        # Build 검증
        if not arc.build or len(arc.build.split()) < 5:
            errors.append("Build section too short - needs conflict escalation")

        # Climax 검증
        if not arc.climax or len(arc.climax.split()) < 5:
            errors.append("Climax too short - needs peak emotional moment")

        # Resolution 검증
        if not arc.resolution:
            errors.append("Resolution is empty")

        # 전체 구조 검증
        total_words = sum(len(getattr(arc, act).split()) for act in ["hook", "build", "climax", "resolution"])
        if total_words < 30:
            errors.append("Overall arc too brief - needs more detail")

        return errors

    def _extract_genre(self, topic_result, normalized_input) -> str:
        """장르 추출"""
        # topic_result가 dataclass인 경우
        if topic_result:
            if hasattr(topic_result, 'genre'):
                return topic_result.genre
            elif isinstance(topic_result, dict) and "genre" in topic_result:
                return topic_result["genre"]
        # normalized_input이 dataclass인 경우
        if normalized_input:
            if hasattr(normalized_input, 'genre'):
                return normalized_input.genre
            elif isinstance(normalized_input, dict) and "genre" in normalized_input:
                return normalized_input["genre"]
        return "default"

    def _extract_characters(self, normalized_input) -> List[str]:
        """캐릭터 목록 추출"""
        if not normalized_input:
            return []
        # dataclass인 경우
        if hasattr(normalized_input, 'characters'):
            characters = normalized_input.characters
            if isinstance(characters, list):
                return [str(c) for c in characters]
        # dict인 경우
        elif isinstance(normalized_input, dict):
            characters = normalized_input.get("characters", [])
            if isinstance(characters, list):
                return [c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in characters]
        return []

    def _extract_setting(self, normalized_input) -> str:
        """설정 추출"""
        if not normalized_input:
            return ""
        # dataclass인 경우
        if hasattr(normalized_input, 'setting'):
            return normalized_input.setting or ""
        # dict인 경우
        elif isinstance(normalized_input, dict):
            return normalized_input.get("setting", normalized_input.get("location", ""))
        return ""

    def _customize_act(self, template: str, act_name: str, characters: List[str],
                       setting: str, topic_result) -> str:
        """각 단계 구체화"""
        result = template

        # 캐릭터 이름이 있으면 주입
        if characters:
            main_char = characters[0] if characters else "the protagonist"
            result = result.replace("the protagonist", main_char)
            result = result.replace("The protagonist", main_char)

        # 설정이 있으면 반영
        if setting and act_name == "hook":
            result = f"In {setting}, {result[0].lower()}{result[1:]}" if result else f"In {setting}, something happens."

        # 주제 결과에서 추가 정보 반영
        if topic_result:
            # dataclass 또는 dict 처리
            theme = None
            if hasattr(topic_result, 'theme'):
                theme = topic_result.theme
            elif isinstance(topic_result, dict):
                theme = topic_result.get('theme')

            if theme and act_name == "resolution":
                result = f"{result} - {theme}"

        return result

    def _has_hook_impact(self, hook: str) -> bool:
        """Hook가 임팩트 키워드를 포함하는지 확인"""
        if not hook:
            return False
        hook_lower = hook.lower()
        return any(kw in hook_lower for kw in self.HOOK_KEYWORDS)


class LLMArcBuilder(ArcBuilder):
    """LLM 기반 고급 아크 빌더"""

    def __init__(self, llm_provider):
        """
        초기화

        Args:
            llm_provider: LLM 제공자 (필수)
        """
        super().__init__(llm_provider)
        if not self.llm:
            raise ValueError("LLM provider is required for LLMArcBuilder")

    async def build_with_llm(self, topic_result: Optional[Dict[str, Any]] = None,
                             normalized_input: Optional[Dict[str, Any]] = None) -> ArcResult:
        """
        LLM으로 정교한 아크 생성

        Args:
            topic_result: 주제 분석 결과
            normalized_input: 정규화된 입력 데이터

        Returns:
            ArcResult: LLM이 생성한 아크
        """
        # 장르 및 컨텍스트 추출
        genre = self._extract_genre(topic_result, normalized_input)
        characters = self._extract_characters(normalized_input)
        setting = self._extract_setting(normalized_input)
        theme = topic_result.get("theme", "") if topic_result else ""

        # 프롬프트 구성
        prompt = self._build_prompt(genre, characters, setting, theme)

        # LLM 호출
        try:
            response = await self._call_llm(prompt)
            arc_data = self._parse_llm_response(response)

            # ArcResult 생성 및 검증
            arc = ArcResult.from_dict(arc_data)
            errors = self.validate_arc(arc)

            if errors:
                # 검증 실패 시 기본 빌더로 폴백
                return self.build(topic_result, normalized_input)

            return arc

        except Exception as e:
            # LLM 실패 시 기본 빌더로 폴백
            return self.build(topic_result, normalized_input)

    def _build_prompt(self, genre: str, characters: List[str], setting: str, theme: str) -> str:
        """LLM 프롬프트 구성"""
        char_info = f"Main characters: {', '.join(characters)}" if characters else ""
        setting_info = f"Setting: {setting}" if setting else ""
        theme_info = f"Theme: {theme}" if theme else ""

        return f"""
Create a 4-act story arc optimized for short-form video:

1. HOOK (0-3 seconds): Must create immediate shock/curiosity
2. BUILD: Escalate tension, develop conflict
3. CLIMAX: Peak emotional moment
4. RESOLUTION: Satisfying ending or cliffhanger

Genre: {genre}
{char_info}
{setting_info}
{theme_info}

Requirements:
- Each act should be 1-2 sentences
- Visual and action-oriented
- Clear emotional progression
- Hook must grab attention instantly

Return as JSON: {{"hook": "", "build": "", "climax": "", "resolution": ""}}
"""

    async def _call_llm(self, prompt: str) -> str:
        """LLM API 호출"""
        if hasattr(self.llm, 'generate'):
            return await self.llm.generate(prompt)
        elif hasattr(self.llm, 'ainvoke'):
            return await self.llm.ainvoke(prompt)
        elif hasattr(self.llm, 'invoke'):
            # 동기 메서드인 경우
            return self.llm.invoke(prompt)
        else:
            raise ValueError("LLM provider does not have a valid generation method")

    def _parse_llm_response(self, response: str) -> Dict[str, str]:
        """LLM 응답 파싱"""
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
                # 중괄호로 찾기
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]

            return json.loads(json_str)

        except json.JSONDecodeError:
            # 파싱 실패 시 기본값 반환
            return {
                "hook": "Something unexpected happens.",
                "build": "The situation escalates.",
                "climax": "The peak moment arrives.",
                "resolution": "The story concludes."
            }

    async def enhance_arc(self, arc: ArcResult, feedback: str = "") -> ArcResult:
        """
        기존 아크를 LLM으로 강화

        Args:
            arc: 기존 아크
            feedback: 개선 피드백

        Returns:
            ArcResult: 강화된 아크
        """
        prompt = f"""
Enhance this story arc for short-form video:

Current arc:
- Hook: {arc.hook}
- Build: {arc.build}
- Climax: {arc.climax}
- Resolution: {arc.resolution}

Feedback: {feedback if feedback else "Make it more engaging and impactful"}

Return improved version as JSON: {{"hook": "", "build": "", "climax": "", "resolution": ""}}
"""

        try:
            response = await self._call_llm(prompt)
            arc_data = self._parse_llm_response(response)
            return ArcResult.from_dict(arc_data)
        except Exception:
            return arc
