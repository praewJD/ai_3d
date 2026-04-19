"""
Story Application Service

스토리 관련 비즈니스 로직
"""
from typing import List, Optional
from datetime import datetime

from core.domain.entities.story import Story, Language, VideoMode
from infrastructure.persistence.repositories.story_repo import StoryRepository


class StoryApplicationService:
    """
    스토리 애플리케이션 서비스

    - 스토리 CRUD
    - 검색
    - 언어별 조회
    """

    def __init__(self, story_repo: StoryRepository):
        self.story_repo = story_repo

    async def create_story(
        self,
        title: str,
        content: str,
        keywords: List[str],
        language: str = "ko",
        video_mode: str = "ai_images",
        style_preset_id: Optional[str] = None
    ) -> Story:
        """새 스토리 생성"""
        story = Story(
            title=title,
            content=content,
            keywords=keywords,
            language=Language(language),
            video_mode=VideoMode(video_mode),
            style_preset_id=style_preset_id
        )
        return await self.story_repo.save(story)

    async def get_story(self, story_id: str) -> Optional[Story]:
        """스토리 조회"""
        return await self.story_repo.find_by_id(story_id)

    async def list_stories(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Story]:
        """스토리 목록"""
        return await self.story_repo.find_all(limit, offset)

    async def search_stories(
        self,
        query: str,
        limit: int = 20
    ) -> List[Story]:
        """스토리 검색"""
        return await self.story_repo.search(query, limit)

    async def get_stories_by_language(
        self,
        language: str
    ) -> List[Story]:
        """언어별 스토리"""
        return await self.story_repo.find_by_language(language)

    async def update_story(
        self,
        story_id: str,
        **updates
    ) -> Optional[Story]:
        """스토리 수정"""
        story = await self.story_repo.find_by_id(story_id)
        if not story:
            return None

        for key, value in updates.items():
            if hasattr(story, key):
                setattr(story, key, value)

        story.update_timestamp()
        return await self.story_repo.save(story)

    async def delete_story(self, story_id: str) -> bool:
        """스토리 삭제"""
        return await self.story_repo.delete(story_id)
