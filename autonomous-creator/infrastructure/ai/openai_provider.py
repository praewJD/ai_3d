"""
OpenAI Provider

GPT-4o 기반 스크립트 생성 (백업)
"""
from typing import List, Optional
import httpx
import json

from core.domain.entities.story import Story, Script, Scene
from core.domain.interfaces.ai_provider import IAIProvider
from config.settings import get_settings


class OpenAIProvider(IAIProvider):
    """
    OpenAI API Provider

    - GPT-4o로 스크립트 생성
    - Claude 백업용
    """

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "openai_api_key", None)

        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self.client = httpx.AsyncClient(timeout=60.0)
        self.model = "gpt-4o"

    async def _call_api(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096
    ) -> str:
        """OpenAI API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
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
        return data["choices"][0]["message"]["content"]

    async def generate_script(
        self,
        story: Story,
        num_scenes: int = 8
    ) -> Script:
        """GPT-4o로 스크립트 생성"""
        # Claude와 동일한 로직, 다른 API
        system_prompt = """당신은 쇼츠/틱톡 영상용 스크립트 작성 전문가입니다.
주어진 스토리를 짧고 임팩트 있는 장면들로 분할하세요.

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
}"""

        user_message = f"""스토리: {story.title}
내용: {story.content}
장면 수: {num_scenes}

스크립트로 변환해주세요."""

        response = await self._call_api(system_prompt, user_message)

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
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
        except:
            return Script(
                scenes=[Scene(
                    description=story.title,
                    narration=story.content[:200],
                    image_prompt=story.content[:100],
                    duration=5.0,
                    order=0
                )],
                total_duration=5.0,
                language=story.language
            )

    async def recommend_next_stories(
        self,
        previous_story: Optional[Story] = None,
        keywords: List[str] = [],
        count: int = 5
    ) -> List[dict]:
        """스토리 추천"""
        # Claude와 유사한 로직
        return []

    async def close(self):
        await self.client.aclose()
