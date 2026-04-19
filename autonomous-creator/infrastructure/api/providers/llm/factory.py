"""
LLM Factory - 설정 기반 LLM Provider 생성

환경 설정에 따라 자동으로 적절한 LLM Provider를 선택
"""
import logging
from typing import Optional, Protocol, runtime_checkable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """LLM Provider가 구현해야 하는 프로토콜"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """텍스트 생성"""
        ...

    @property
    def model_name(self) -> str:
        """모델 이름"""
        ...

    @property
    def provider_name(self) -> str:
        """Provider 이름"""
        ...


@dataclass
class LLMConfig:
    """LLM 설정"""
    provider: str = "glm"  # glm, claude, openai
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7


def create_llm_provider(
    provider: str = None,
    api_key: str = None,
    model: str = None,
    **kwargs
) -> LLMProviderProtocol:
    """
    LLM Provider 생성

    Args:
        provider: Provider 이름 (glm, claude, openai)
        api_key: API 키 (없으면 설정에서 로드)
        model: 모델 이름
        **kwargs: 추가 설정

    Returns:
        LLM Provider 인스턴스

    Examples:
        # GLM 사용
        llm = create_llm_provider("glm")

        # Claude 사용
        llm = create_llm_provider("claude")

        # 설정에서 자동 선택
        llm = create_llm_provider()  # GLM > Claude > OpenAI 순서
    """
    from infrastructure.api.config.api_config import get_api_config

    config = get_api_config()
    provider = provider or config.get_recommended_llm_provider()

    if provider == "glm":
        from .glm import GLMProvider, create_glm_provider
        return create_glm_provider(api_key=api_key, model=model)

    elif provider == "claude":
        # Claude Provider 구현 필요
        raise NotImplementedError(
            "Claude provider not implemented yet. "
            "Use GLM provider or implement ClaudeProvider."
        )

    elif provider == "openai":
        # OpenAI Provider 구현 필요
        raise NotImplementedError(
            "OpenAI provider not implemented yet. "
            "Use GLM provider or implement OpenAIProvider."
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def create_llm_for_scene_compiler(
    provider: str = None,
    **kwargs
) -> LLMProviderProtocol:
    """
    SceneCompiler용 LLM Provider 생성

    SceneCompiler는 generate(prompt, system_prompt) 메서드를 필요로 함

    Args:
        provider: Provider 이름
        **kwargs: 추가 설정

    Returns:
        LLM Provider

    Example:
        from infrastructure.api.providers.llm import create_llm_for_scene_compiler
        from infrastructure.scene import SceneCompiler

        llm = create_llm_for_scene_compiler("glm")
        compiler = SceneCompiler(llm_provider=llm)

        graph = await compiler.compile("숲속에서 길 잃은 소녀 이야기...")
    """
    return create_llm_provider(provider=provider, **kwargs)


# 모듈 레벨 편의 함수
async def generate_text(
    prompt: str,
    system_prompt: str = None,
    provider: str = None,
    **kwargs
) -> str:
    """
    텍스트 생성 편의 함수

    Args:
        prompt: 프롬프트
        system_prompt: 시스템 프롬프트
        provider: Provider 이름
        **kwargs: 추가 설정

    Returns:
        생성된 텍스트
    """
    llm = create_llm_provider(provider=provider)
    return await llm.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
