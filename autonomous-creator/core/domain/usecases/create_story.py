"""
Create Story Use Case

스토리 생성 비즈니스 로직을 캡슐화
"""
from typing import Optional
from dataclasses import dataclass

from ..entities.story import Story, Scene, Script, Language
from ..interfaces.repository import IStoryRepository


@dataclass
class CreateStoryRequest:
    """스토리 생성 요청"""
    title: str
    content: str
    language: Language = Language.KO
    style_preset_id: Optional[str] = None


@dataclass
class CreateStoryResponse:
    """스토리 생성 응답"""
    story: Story
    success: bool
    message: str = ""


class CreateStoryUseCase:
    """
    스토리 생성 유스케이스

    Responsibility:
    - 스토리 제목/내용 검증
    - Scene 자동 분할 (문단 기준)
    - 스토리 저장
    """

    def __init__(self, story_repository: IStoryRepository):
        self._story_repository = story_repository

    async def execute(self, request: CreateStoryRequest) -> CreateStoryResponse:
        """
        스토리 생성 실행

        Args:
            request: 스토리 생성 요청 데이터

        Returns:
            CreateStoryResponse: 생성된 스토리 및 결과
        """
        # 1. 입력 검증
        if not request.title or len(request.title.strip()) == 0:
            return CreateStoryResponse(
                story=None,
                success=False,
                message="스토리 제목이 필요합니다."
            )

        if not request.content or len(request.content.strip()) < 10:
            return CreateStoryResponse(
                story=None,
                success=False,
                message="스토리 내용은 최소 10자 이상이어야 합니다."
            )

        # 2. Scene 분할 (문단 기준)
        scenes = self._split_into_scenes(request.content)

        # 3. 스토리 엔티티 생성
        story = Story(
            title=request.title,
            content=request.content,
            language=request.language,
            style_preset_id=request.style_preset_id,
            scenes=scenes
        )

        # 4. 저장
        saved_story = await self._story_repository.save(story)

        return CreateStoryResponse(
            story=saved_story,
            success=True,
            message=f"스토리가 성공적으로 생성되었습니다. ({len(scenes)}개 장면)"
        )

    def _split_into_scenes(self, content: str) -> list[Scene]:
        """
        내용을 장면으로 분할

        Args:
            content: 스토리 전체 내용

        Returns:
            list[Scene]: 분할된 장면 목록
        """
        # 문단 분할 (빈 줄 기준)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        scenes = []
        for i, paragraph in enumerate(paragraphs):
            scene = Scene(
                id=f"scene_{i+1}",
                description=paragraph,
                narration_text=paragraph,
                duration_estimate=len(paragraph) / 20  # 대략 20자/초
            )
            scenes.append(scene)

        # 최소 1개 장면 보장
        if not scenes:
            scenes.append(Scene(
                id="scene_1",
                description=content,
                narration_text=content,
                duration_estimate=len(content) / 20
            ))

        return scenes
