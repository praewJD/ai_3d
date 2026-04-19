"""
Stories API Routes

스토리 CRUD 및 영상 생성
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

from core.application.story_service import StoryApplicationService
from core.application.orchestrator import PipelineOrchestrator
from core.domain.entities.story import Story
from interfaces.api.dependencies import get_story_service, get_orchestrator


router = APIRouter()


# Request/Response DTOs
from pydantic import BaseModel


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


class GenerateVideoRequest(BaseModel):
    style_preset_id: Optional[str] = None
    output_dir: str = "outputs"


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


@router.post("/{story_id}/generate")
async def generate_video(
    story_id: str,
    request: GenerateVideoRequest,
    background_tasks: BackgroundTasks,
    service: StoryApplicationService = Depends(get_story_service),
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator)
):
    """영상 생성 요청 (비동기)"""
    story = await service.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # 백그라운드에서 실행
    async def run_pipeline():
        await orchestrator.generate_video(
            story=story,
            preset_id=request.style_preset_id,
            output_dir=request.output_dir
        )

    background_tasks.add_task(run_pipeline)

    return {
        "status": "started",
        "story_id": story_id,
        "message": "Video generation started"
    }


@router.get("/{story_id}/status")
async def get_generation_status(
    story_id: str,
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator)
):
    """생성 상태 조회"""
    task = await orchestrator.task_repo.find_by_story_id(story_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress": task.progress,
        "current_step": task.current_step.value,
        "error_message": task.error_message,
        "output_paths": task.output_paths
    }


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
