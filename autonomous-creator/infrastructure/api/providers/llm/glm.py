"""
GLM Provider - Zhipu AI GLM 모델 연동

GLM-4, GLM-4-Flash, GLM-5 등 지원
Anthropic 호환 API (z.ai) 및 OpenAI 호환 API 지원
"""
import aiohttp
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GLMResponse:
    """GLM API 응답"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class GLMProvider:
    """
    Zhipu AI GLM Provider

    Anthropic 호환 API (z.ai) 및 OpenAI 호환 API 지원
    """

    PROVIDER_NAME = "glm"
    SUPPORTED_MODELS = [
        "glm-5",           # GLM-5 (최신)
        "glm-4",           # 최고 성능
        "glm-4-flash",     # 빠른 응답 (추천)
        "glm-4-plus",      # 향상된 성능
        "glm-4-air",       # 경제형
        "glm-4-airx",      # 실시간
        "glm-4-long",      # 긴 컨텍스트
    ]
    DEFAULT_MODEL = "glm-5"

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.z.ai/api/anthropic/v1/messages",
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ):
        """
        GLM Provider 초기화

        Args:
            api_key: API Key
            api_url: API 엔드포인트 (z.ai Anthropic 호환)
            model: 모델 이름
            max_tokens: 최대 토큰 수
            temperature: 생성 온도
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.config = kwargs

        # API 타입 감지
        self._is_anthropic_format = "anthropic" in api_url.lower() or "messages" in api_url

    @property
    def model_name(self) -> str:
        """현재 모델 이름"""
        return self.model

    @property
    def provider_name(self) -> str:
        """Provider 이름"""
        return self.PROVIDER_NAME

    def _build_headers(self) -> Dict[str, str]:
        """HTTP 헤더 생성"""
        if self._is_anthropic_format:
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
        else:
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

    def _build_payload(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """API 요청 페이로드 생성"""
        if self._is_anthropic_format:
            # Anthropic Messages API 포맷
            payload = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            if system_prompt:
                payload["system"] = system_prompt
            if temperature is not None:
                payload["temperature"] = temperature
            return payload
        else:
            # OpenAI Chat Completions 포맷
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            return {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
                **kwargs
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> str:
        """
        텍스트 생성 (SceneCompiler 호환)

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            temperature: 생성 온도
            max_tokens: 최대 토큰

        Returns:
            생성된 텍스트
        """
        response = await self.generate_full(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.content

    async def generate_full(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> GLMResponse:
        """
        전체 응답 반환

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            temperature: 생성 온도
            max_tokens: 최대 토큰

        Returns:
            GLMResponse
        """
        headers = self._build_headers()
        payload = self._build_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        logger.debug(f"GLM API request: model={self.model}, format={'anthropic' if self._is_anthropic_format else 'openai'}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GLM API error: {response.status} - {error_text}")
                        raise RuntimeError(f"GLM API error: {response.status} - {error_text}")

                    data = await response.json()

                    # 응답 파싱
                    if self._is_anthropic_format:
                        # Anthropic Messages API 응답
                        content_blocks = data.get("content", [])
                        content = ""
                        for block in content_blocks:
                            if block.get("type") == "text":
                                content += block.get("text", "")

                        usage = data.get("usage", {})
                        finish_reason = data.get("stop_reason", "stop")
                    else:
                        # OpenAI Chat Completions 응답
                        choices = data.get("choices", [])
                        if not choices:
                            raise RuntimeError("GLM API returned no choices")

                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        finish_reason = choices[0].get("finish_reason", "stop")
                        usage = data.get("usage", {})

                    logger.debug(f"GLM API response: tokens={usage.get('input_tokens', 0) + usage.get('output_tokens', 0)}")

                    return GLMResponse(
                        content=content,
                        model=data.get("model", self.model),
                        usage=usage,
                        finish_reason=finish_reason
                    )

        except aiohttp.ClientError as e:
            logger.error(f"GLM API request failed: {e}")
            raise RuntimeError(f"GLM API request failed: {e}")

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        JSON 응답 생성

        Args:
            prompt: 프롬프트
            system_prompt: 시스템 프롬프트

        Returns:
            파싱된 JSON 딕셔너리
        """
        # JSON 형식 강제
        json_system = (system_prompt or "") + "\n\nIMPORTANT: Return ONLY valid JSON, no markdown, no explanation."
        json_prompt = prompt + "\n\nReturn as JSON."

        response = await self.generate(
            prompt=json_prompt,
            system_prompt=json_system,
            temperature=0.3,  # JSON은 낮은 온도
            **kwargs
        )

        # JSON 파싱
        try:
            # 마크다운 코드 블록 제거
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response[:500]}")
            raise ValueError(f"Failed to parse JSON response: {e}")

    async def health_check(self) -> bool:
        """API 연결 확인"""
        try:
            response = await self.generate("Hello", max_tokens=10)
            return len(response) > 0
        except Exception as e:
            logger.warning(f"GLM health check failed: {e}")
            return False

    def get_supported_models(self) -> List[str]:
        """지원 모델 목록"""
        return self.SUPPORTED_MODELS

    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보"""
        return {
            "provider": self.PROVIDER_NAME,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "supported_models": self.SUPPORTED_MODELS
        }


# 편의 함수
def create_glm_provider(
    api_key: str = None,
    model: str = None
) -> GLMProvider:
    """
    GLM Provider 생성 편의 함수

    Args:
        api_key: API 키 (없으면 환경변수에서 로드)
        model: 모델 이름

    Returns:
        GLMProvider 인스턴스
    """
    from infrastructure.api.config.api_config import get_api_config

    config = get_api_config()

    api_key = api_key or config.glm_api_key
    model = model or config.glm_model

    if not api_key:
        raise ValueError("GLM API key not configured. Set GLM_API_KEY environment variable.")

    return GLMProvider(
        api_key=api_key,
        api_url=config.glm_api_url,
        model=model,
        max_tokens=config.glm_max_tokens
    )
