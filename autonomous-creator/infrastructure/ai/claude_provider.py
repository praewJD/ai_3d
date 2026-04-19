"""
Claude AI Provider

Claude API를 사용한 스크립트 생성 및 추천
"""
import httpx
from typing import List, Optional
import json

from core.domain.entities.story import Story, Script, Scene, Language
from core.domain.interfaces.ai_provider import IAIProvider
from config.settings import get_settings


class ClaudeProvider(IAIProvider):
    """
    Claude API Provider

    IAIProvider 인터페이스 구현:
    - 스크립트 생성
    - 스토리 추천
    - 장면 분할
    - 프롬프트 생성
    - 번역
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.claude_api_key

        if not self.api_key:
            raise ValueError("Claude API key required")

        self.client = httpx.AsyncClient(timeout=60.0)
        self._model_name = "claude-sonnet-4-20250514"

    @property
    def model_name(self) -> str:
        """사용 중인 모델 이름"""
        return self._model_name

    @property
    def provider_name(self) -> str:
        """Provider 이름"""
        return "claude"

    async def _call_api(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096
    ) -> str:
        """Claude API 호출"""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }

        response = await self.client.post(
            self.API_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        return data["content"][0]["text"]

    async def generate_script(
        self,
        story: Story,
        num_scenes: int = 8
    ) -> Script:
        """
        스토리에서 스크립트 생성

        Args:
            story: 스토리 엔티티
            num_scenes: 장면 수

        Returns:
            생성된 스크립트
        """
        system_prompt = """당신은 쇼츠/틱톡 영상용 스크립트 작성 전문가입니다.
주어진 스토리를 짧고 임팩트 있는 장면들로 분할하고, 각 장면에 대한 내레이션과 이미지 프롬프트를 생성하세요.

출력 형식 (JSON):
{
  "scenes": [
    {
      "description": "장면 설명",
      "narration": "내레이션 텍스트",
      "image_prompt": "이미지 생성용 영어 프롬프트",
      "duration": 3.5
    }
  ],
  "total_duration": 28.0
}

규칙:
- 각 장면은 2~5초
- 내레이션은 자연스럽고 듣기 좋은 문체
- 이미지 프롬프트는 영어로, 스타일 일관성 유지
- 전체 영상은 30~60초"""

        user_message = f"""스토리 제목: {story.title}
스토리 내용: {story.content}
키워드: {', '.join(story.keywords)}
언어: {story.language.value}
장면 수: {num_scenes}

위 스토리를 쇼츠용 스크립트로 변환해주세요."""

        response = await self._call_api(system_prompt, user_message)

        # JSON 파싱
        try:
            # 마크다운 코드 블록 제거
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())

            scenes = [
                Scene(
                    description=s.get("description", ""),
                    narration=s.get("narration", ""),
                    image_prompt=s.get("image_prompt", ""),
                    duration=s.get("duration", 3.0),
                    order=i
                )
                for i, s in enumerate(data.get("scenes", []))
            ]

            return Script(
                scenes=scenes,
                total_duration=data.get("total_duration", sum(s.duration for s in scenes)),
                language=story.language
            )

        except json.JSONDecodeError:
            # 파싱 실패 시 기본 스크립트
            return Script(
                scenes=[
                    Scene(
                        description=story.title,
                        narration=story.content[:200],
                        image_prompt=story.content[:100],
                        duration=5.0,
                        order=0
                    )
                ],
                total_duration=5.0,
                language=story.language
            )

    async def recommend_next_stories(
        self,
        previous_story: Optional[Story] = None,
        keywords: List[str] = [],
        count: int = 5
    ) -> List[dict]:
        """
        다음 스토리 추천

        Args:
            previous_story: 이전 스토리
            keywords: 키워드 목록
            count: 추천 개수

        Returns:
            추천 스토리 목록
        """
        system_prompt = """당신은 크리에이티브 스토리 추천 전문가입니다.
쇼츠/틱톡용 인기 스토리 아이디어를 추천하세요.

출력 형식 (JSON):
[
  {
    "title": "스토리 제목",
    "description": "스토리 설명 (2~3문장)",
    "keywords": ["키워드1", "키워드2"],
    "genre": "장르"
  }
]

규칙:
- 흥미롭고 바이럴 가능성 높은 주제
- 다양한 장르 포함
- 트렌드 반영"""

        context = ""
        if previous_story:
            context += f"이전 스토리: {previous_story.title}\n"
            context += f"키워드: {', '.join(previous_story.keywords)}\n"
        if keywords:
            context += f"관심 키워드: {', '.join(keywords)}"

        user_message = f"""{context}
{count}개의 스토리 아이디어를 추천해주세요."""

        response = await self._call_api(system_prompt, user_message)

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return []

    async def enhance_prompt(
        self,
        base_prompt: str,
        style: str = "anime"
    ) -> str:
        """이미지 프롬프트 개선"""
        system_prompt = """당신은 AI 이미지 생성 프롬프트 전문가입니다.
주어진 프롬프트를 Stable Diffusion 3.5에 최적화된 프롬프트로 개선하세요.

규칙:
- 영어로 작성
- 스타일 키워드 추가
- 품질 향상 키워드 추가
- 100단어 이내"""

        response = await self._call_api(
            system_prompt,
            f"프롬프트: {base_prompt}\n스타일: {style}",
            max_tokens=200
        )
        return response.strip()

    # === IAIProvider 인터페이스 구현 ===

    async def recommend_stories(
        self,
        topic: Optional[str] = None,
        language: Language = Language.KO,
        count: int = 5,
        context: Optional[str] = None
    ) -> List[dict]:
        """
        스토리 추천 (IAIProvider 인터페이스)

        Args:
            topic: 주제 (선택)
            language: 언어
            count: 추천 개수
            context: 추가 컨텍스트

        Returns:
            List[dict]: 추천 스토리 목록
        """
        return await self.recommend_next_stories(
            previous_story=None,
            keywords=[topic] if topic else [],
            count=count
        )

    async def improve_story(
        self,
        story: Story,
        focus_area: str = "engagement"
    ) -> dict:
        """
        스토리 개선 제안

        Args:
            story: 개선할 스토리
            focus_area: 개선 초점 (engagement, clarity, emotion)

        Returns:
            dict: 개선 제안
        """
        system_prompt = f"""당신은 스토리 개선 전문가입니다.
주어진 스토리를 분석하고 개선 제안을 제공하세요.

초점 영역: {focus_area}
- engagement: 참여도 및 바이럴 가능성
- clarity: 명확성 및 이해도
- emotion: 감정적 임팩트

출력 형식 (JSON):
{{
  "score": 7.5,
  "strengths": ["강점1", "강점2"],
  "weaknesses": ["약점1", "약점2"],
  "suggestions": ["제안1", "제안2", "제안3"],
  "improved_content": "개선된 내용 (선택)"
}}"""

        user_message = f"""제목: {story.title}
내용: {story.content}
키워드: {', '.join(story.keywords)}

개선 제안을 해주세요."""

        response = await self._call_api(system_prompt, user_message)

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {
                "score": 5.0,
                "strengths": [],
                "weaknesses": [],
                "suggestions": ["API 응답 파싱 실패"]
            }

    async def generate_image_prompts(
        self,
        story: Story,
        style_preset: Optional[str] = None
    ) -> List[str]:
        """
        스토리로부터 이미지 프롬프트 생성

        Args:
            story: 스토리
            style_preset: 스타일 프리셋

        Returns:
            List[str]: 장면별 이미지 프롬프트
        """
        prompts = []
        for scene in story.scenes:
            base_prompt = scene.image_prompt or scene.description
            enhanced = await self.enhance_prompt(base_prompt, style_preset or "anime")
            prompts.append(enhanced)
        return prompts

    async def translate_content(
        self,
        content: str,
        source_language: Language,
        target_language: Language
    ) -> str:
        """
        콘텐츠 번역

        Args:
            content: 원본 콘텐츠
            source_language: 원본 언어
            target_language: 대상 언어

        Returns:
            str: 번역된 콘텐츠
        """
        language_names = {
            Language.KO: "한국어",
            Language.ENGLISH: "English",
            Language.JAPANESE: "日本語",
            Language.CHINESE: "中文",
            Language.THAI: "ไทย"
        }

        system_prompt = f"""당신은 전문 번역가입니다.
{language_names.get(source_language, source_language.value)}에서 {language_names.get(target_language, target_language.value)}로 번역하세요.

규칙:
- 자연스러운 표현
- 문화적 뉘앙스 유지
- 원본 톤 앤 매너 보존"""

        response = await self._call_api(
            system_prompt,
            content,
            max_tokens=2000
        )
        return response.strip()

    async def analyze_trends(
        self,
        niche: str,
        language: Language = Language.KO
    ) -> dict:
        """
        트렌드 분석

        Args:
            niche: 분석할 분야
            language: 언어

        Returns:
            dict: 트렌드 분석 결과
        """
        system_prompt = """당신은 소셜 미디어 트렌드 분석 전문가입니다.
주어진 분야의 최신 트렌드를 분석하세요.

출력 형식 (JSON):
{
  "niche": "분야명",
  "trending_topics": ["토픽1", "토픽2", "토픽3"],
  "recommended_angles": ["접근각1", "접근각2"],
  "competitor_insights": ["인사이트1", "인사이트2"],
  "best_posting_times": ["시간대1", "시간대2"]
}"""

        response = await self._call_api(
            system_prompt,
            f"분야: {niche}\n언어: {language.value}\n\n트렌드 분석을 해주세요."
        )

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {
                "niche": niche,
                "trending_topics": [],
                "recommended_angles": [],
                "competitor_insights": [],
                "best_posting_times": []
            }

    async def close(self):
        """연결 종료"""
        await self.client.aclose()
