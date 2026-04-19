"""
Story LLM Provider - 대본 생성 전용 LLM 호출

config/api_config.py에서 STORY_API_* 설정을 읽어 API 호출.
모든 대본 생성 단계(1차 컴파일, 2차 재시도)에서 동일한 키 사용.
"""
import httpx
import logging

from config.api_config import STORY_API_KEY, STORY_API_URL, STORY_MODEL, STORY_MAX_TOKENS

logger = logging.getLogger(__name__)


class StoryLLMProvider:
    """
    대본 생성 전용 LLM Provider

    config/api_config.py의 STORY_API_KEY/URL/MODEL을 사용.
    UnifiedStoryCompiler, ShortDramaCompiler 모두 이 Provider를 사용.

    사용법:
        from infrastructure.ai import StoryLLMProvider
        provider = StoryLLMProvider()  # .env에서 자동 로드
        compiler = UnifiedStoryCompiler(llm_provider=provider)
    """

    def __init__(self):
        if not STORY_API_KEY:
            raise ValueError(
                "STORY_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 STORY_API_KEY를 추가하세요."
            )

        self.api_key = STORY_API_KEY
        self.api_url = STORY_API_URL
        self.model = STORY_MODEL
        self.max_tokens = STORY_MAX_TOKENS
        self.client = httpx.AsyncClient(timeout=120.0)

        logger.info(f"StoryLLMProvider 초기화: model={self.model}, url={self.api_url}")

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "story_llm"

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = None,
    ) -> str:
        """
        LLM API 호출

        Args:
            system_prompt: 시스템 프롬프트
            user_message: 사용자 메시지
            max_tokens: 최대 토큰 수 (기본값: config에서 로드)

        Returns:
            LLM 응답 텍스트
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ],
        }

        response = await self.client.post(
            self.api_url,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

        data = response.json()

        # MiniMax API 호환: content 배열에서 type="text" 요소 찾기
        content = data.get("content", [])
        for item in content:
            if item.get("type") == "text":
                return item.get("text", "")

        # 폴백: 첫 번째 요소가 text 타입인 경우
        if content and "text" in content[0]:
            return content[0]["text"]

        return ""

    # 기존 컴파일러 호환용 (_call_api 인터페이스)
    async def _call_api(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> str:
        """기존 컴파일러 코드 호환용"""
        return await self.generate(system_prompt, user_message, max_tokens)

    async def close(self):
        """연결 종료"""
        await self.client.aclose()
