"""
AI Provider Interface

AI 서비스 추상화 인터페이스 - 의존성 역전 원칙 적용
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Any
from dataclasses import dataclass

from ..entities.story import Story, Script, Language


@dataclass
class StoryRecommendation:
    """스토리 추천 데이터"""
    title: str
    description: str
    angle: str
    hook: str
    estimated_engagement: str
    target_audience: str


@dataclass
class TrendAnalysis:
    """트렌드 분석 결과"""
    niche: str
    trending_topics: List[str]
    recommended_angles: List[str]
    competitor_insights: List[str]
    best_posting_times: List[str]


@dataclass
class StoryImprovement:
    """스토리 개선 제안"""
    original_score: float
    improved_score: float
    suggestions: List[str]
    rewritten_hook: Optional[str] = None
    rewritten_intro: Optional[str] = None


class IAIProvider(ABC):
    """
    AI Provider 인터페이스

    Claude, GPT-4 등 다양한 AI 백엔드를 추상화합니다.
    의존성 역전 원칙을 통해 도메인이 구현체에 직접 의존하지 않도록 합니다.
    """

    @abstractmethod
    async def generate_script(
        self,
        story: Story,
        style: str = "engaging",
        max_length: int = 500
    ) -> Script:
        """
        스토리로부터 스크립트 생성

        Args:
            story: 원본 스토리
            style: 스크립트 스타일 (engaging, informative, dramatic)
            max_length: 최대 길이

        Returns:
            Script: 생성된 스크립트
        """
        pass

    @abstractmethod
    async def recommend_stories(
        self,
        topic: Optional[str] = None,
        language: Language = Language.KO,
        count: int = 5,
        context: Optional[str] = None
    ) -> List[dict]:
        """
        스토리 추천 생성

        Args:
            topic: 주제 (선택)
            language: 언어
            count: 추천 개수
            context: 추가 컨텍스트

        Returns:
            List[dict]: 추천 스토리 목록
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def generate_image_prompts(
        self,
        story: Story,
        style_preset: Optional[dict] = None
    ) -> List[str]:
        """
        스토리로부터 이미지 프롬프트 생성

        Args:
            story: 스토리
            style_preset: 스타일 프리셋

        Returns:
            List[str]: 장면별 이미지 프롬프트
        """
        pass

    @abstractmethod
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
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """사용 중인 모델 이름"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 이름 (claude, openai, etc.)"""
        pass
