"""
Recommend Use Case

AI 추천 비즈니스 로직을 캡슐화
"""
from typing import Optional, List
from dataclasses import dataclass

from ..interfaces.ai_provider import IAIProvider
from ..entities.story import Story, Language


@dataclass
class RecommendRequest:
    """추천 요청"""
    topic: Optional[str] = None
    language: Language = Language.KO
    count: int = 5
    context: Optional[str] = None


@dataclass
class StoryRecommendation:
    """스토리 추천 결과"""
    title: str
    description: str
    angle: str  # 접근 각도
    hook: str   # 후킹 문구
    estimated_engagement: str  # 예상 참여도
    target_audience: str


@dataclass
class RecommendResponse:
    """추천 응답"""
    success: bool
    recommendations: List[StoryRecommendation]
    message: str = ""


class RecommendUseCase:
    """
    AI 추천 유스케이스

    Responsibility:
    - 트렌드 기반 스토리 추천
    - 언어별 최적화된 추천
    - 참여도 예측
    """

    def __init__(self, ai_provider: IAIProvider):
        self._ai_provider = ai_provider

    async def execute(self, request: RecommendRequest) -> RecommendResponse:
        """
        추천 실행

        Args:
            request: 추천 요청

        Returns:
            RecommendResponse: 추천 결과
        """
        try:
            recommendations = await self._ai_provider.recommend_stories(
                topic=request.topic,
                language=request.language,
                count=request.count,
                context=request.context
            )

            return RecommendResponse(
                success=True,
                recommendations=[
                    StoryRecommendation(**rec) for rec in recommendations
                ],
                message=f"{len(recommendations)}개의 추천을 생성했습니다."
            )
        except Exception as e:
            return RecommendResponse(
                success=False,
                recommendations=[],
                message=f"추천 생성 실패: {str(e)}"
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
        return await self._ai_provider.improve_story(
            story=story,
            focus_area=focus_area
        )

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
        return await self._ai_provider.analyze_trends(
            niche=niche,
            language=language
        )
