"""
Tasks API Routes

작업 상태 관리
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from infrastructure.persistence.repositories.task_repo import TaskRepository
from interfaces.api.dependencies import get_task_repo


router = APIRouter()


@router.get("")
async def list_tasks(
    limit: int = 50,
    repo: TaskRepository = Depends(get_task_repo)
):
    """최근 작업 목록"""
    tasks = await repo.find_recent(limit)
    return [
        {
            "id": t.id,
            "story_id": t.story_id,
            "status": t.status.value,
            "progress": t.progress,
            "current_step": t.current_step.value,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None
        }
        for t in tasks
    ]


@router.get("/pending")
async def list_pending_tasks(
    repo: TaskRepository = Depends(get_task_repo)
):
    """대기 중인 작업"""
    tasks = await repo.find_pending()
    return [
        {
            "id": t.id,
            "story_id": t.story_id,
            "status": t.status.value,
            "created_at": t.created_at.isoformat()
        }
        for t in tasks
    ]


@router.get("/running")
async def list_running_tasks(
    repo: TaskRepository = Depends(get_task_repo)
):
    """실행 중인 작업"""
    tasks = await repo.find_running()
    return [
        {
            "id": t.id,
            "story_id": t.story_id,
            "progress": t.progress,
            "current_step": t.current_step.value,
            "started_at": t.started_at.isoformat() if t.started_at else None
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    repo: TaskRepository = Depends(get_task_repo)
):
    """작업 상세 조회"""
    task = await repo.find_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "story_id": task.story_id,
        "status": task.status.value,
        "progress": task.progress,
        "current_step": task.current_step.value,
        "error_message": task.error_message,
        "error_stack": task.error_stack,
        "output_paths": task.output_paths,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "duration_seconds": task.duration_seconds
    }


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    repo: TaskRepository = Depends(get_task_repo)
):
    """작업 삭제"""
    deleted = await repo.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "task_id": task_id}
