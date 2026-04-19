"""
Stories Web API Routes

스토리 관리 API
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.application.story_service import StoryApplicationService
from interfaces.api.dependencies import get_story_service


router = APIRouter()


# Request/Response DTOs
class CreateStoryRequest(BaseModel):
    title: str
    content: str
    keywords: List[str] = []
    language: str = "ko"
    video_mode: str = "ai_images"
    style_preset_id: Optional[str] = None


class StoryResponse(BaseModel):
    id: str
    title: str
    content: str
    keywords: List[str]
    language: str
    video_mode: str
    style_preset_id: Optional[str]
    created_at: str


@router.post("", response_model=StoryResponse)
async def create_story(
    request: CreateStoryRequest,
    service: StoryApplicationService = Depends(get_story_service)
):
    """새 스토리 생성"""
    story = await service.create_story(
        title=request.title,
        content=request.content,
        keywords=request.keywords,
        language=request.language,
        video_mode=request.video_mode,
        style_preset_id=request.style_preset_id
    )
    return StoryResponse(
        id=story.id,
        title=story.title,
        content=story.content,
        keywords=story.keywords,
        language=story.language.value,
        video_mode=story.video_mode.value,
        style_preset_id=story.style_preset_id,
        created_at=story.created_at.isoformat()
    )


@router.get("", response_model=List[StoryResponse])
async def list_stories(
    limit: int = 100,
    offset: int = 0,
    service: StoryApplicationService = Depends(get_story_service)
):
    """스토리 목록"""
    stories = await service.list_stories(limit, offset)
    return [
        StoryResponse(
            id=s.id,
            title=s.title,
            content=s.content,
            keywords=s.keywords,
            language=s.language.value,
            video_mode=s.video_mode.value,
            style_preset_id=s.style_preset_id,
            created_at=s.created_at.isoformat()
        )
        for s in stories
    ]


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str,
    service: StoryApplicationService = Depends(get_story_service)
):
    """스토리 조회"""
    story = await service.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return StoryResponse(
        id=story.id,
        title=story.title,
        content=story.content,
        keywords=story.keywords,
        language=story.language.value,
        video_mode=story.video_mode.value,
        style_preset_id=story.style_preset_id,
        created_at=story.created_at.isoformat()
    )


@router.delete("/{story_id}")
async def delete_story(
    story_id: str,
    service: StoryApplicationService = Depends(get_story_service)
):
    """스토리 삭제"""
    deleted = await service.delete_story(story_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Story not found")
    return {"status": "deleted", "story_id": story_id}
