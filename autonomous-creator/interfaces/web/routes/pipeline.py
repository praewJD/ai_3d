"""
Pipeline Web API Routes

영상 생성 파이프라인 API + WebSocket
"""
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.application.story_service import StoryApplicationService
from core.application.orchestrator import PipelineOrchestrator
from core.domain.entities.task import TaskStep
from interfaces.api.dependencies import get_story_service, get_orchestrator


router = APIRouter()


# Request/Response DTOs
class GenerateVideoRequest(BaseModel):
    style_preset_id: Optional[str] = None
    output_dir: str = "outputs"


class TaskStatusResponse(BaseModel):
    task_id: str
    story_id: str
    status: str
    progress: int
    current_step: str
    error_message: Optional[str] = None
    output_paths: list[str] = []


# 진행 상황 브로드캐스트 매니저
class ProgressBroadcaster:
    """WebSocket 진행 상황 브로드캐스터"""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict):
        """모든 연결에 메시지 브로드캐스트"""
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


# 전역 브로드캐스터
broadcaster = ProgressBroadcaster()


@router.post("/{story_id}/generate", response_model=TaskStatusResponse)
async def generate_video(
    story_id: str,
    request: GenerateVideoRequest,
    service: StoryApplicationService = Depends(get_story_service),
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator)
):
    """영상 생성 요청 (비동기)"""
    story = await service.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # 진행 콜백 설정
    async def progress_callback(task):
        await broadcaster.broadcast({
            "type": "progress",
            "task_id": task.id,
            "story_id": task.story_id,
            "status": task.status.value,
            "progress": task.progress,
            "current_step": task.current_step.value
        })

    orchestrator.set_progress_callback(progress_callback)

    # 백그라운드에서 파이프라인 실행
    task = await orchestrator.generate_video(
        story=story,
        preset=None,  # TODO: preset_id로 Preset 조회
        output_dir=request.output_dir
    )

    return TaskStatusResponse(
        task_id=task.id,
        story_id=task.story_id,
        status=task.status.value,
        progress=task.progress,
        current_step=task.current_step.value,
        error_message=task.error_message,
        output_paths=task.output_paths
    )


@router.get("/{story_id}/status", response_model=TaskStatusResponse)
async def get_generation_status(
    story_id: str,
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator)
):
    """생성 상태 조회"""
    task = await orchestrator.task_repo.find_by_story_id(story_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.id,
        story_id=task.story_id,
        status=task.status.value,
        progress=task.progress,
        current_step=task.current_step.value,
        error_message=task.error_message,
        output_paths=task.output_paths
    )


@router.websocket("/ws/{client_id}")
async def websocket_progress(websocket: WebSocket, client_id: str):
    """
    WebSocket 진행 상황 스트리밍

    클라이언트 연결 → 진행 상황 실시간 수신
    """
    await broadcaster.connect(websocket)
    try:
        # 연결 확인 메시지
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "message": "WebSocket connected"
        })

        # 연결 유지 (클라이언트에서 메시지 올 때까지 대기)
        while True:
            try:
                # heartbeat 또는 클라이언트 메시지 대기
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )

                # ping/pong 처리
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # 타임아웃시 ping 전송
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        broadcaster.disconnect(websocket)
