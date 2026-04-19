"""
Checkpoint Manager - 파이프라인 상태 저장/복구

중간 실패 시 재개 가능
"""
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from enum import Enum


class PipelineStep(str, Enum):
    """파이프라인 단계"""
    INIT = "init"
    CHARACTER_EXTRACTION = "character_extraction"
    SCRIPT_GENERATION = "script_generation"
    PROMPT_GENERATION = "prompt_generation"  # NEW
    AUDIO_GENERATION = "audio_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    COMPOSITION = "composition"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CheckpointState:
    """체크포인트 상태"""
    story_id: str
    current_step: PipelineStep
    progress: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 각 단계 결과
    characters: List[Dict] = field(default_factory=list)
    script: Optional[Dict] = None
    prompts: List[Dict] = field(default_factory=list)  # NEW
    audio_paths: List[str] = field(default_factory=list)
    image_paths: List[str] = field(default_factory=list)
    video_paths: List[str] = field(default_factory=list)
    final_video: Optional[str] = None

    # 에러 정보
    error_message: Optional[str] = None
    error_step: Optional[PipelineStep] = None
    retry_count: int = 0

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointState":
        """딕셔너리에서 복원"""
        data["current_step"] = PipelineStep(data["current_step"])
        if data.get("error_step"):
            data["error_step"] = PipelineStep(data["error_step"])
        return cls(**data)

    def update_step(self, step: PipelineStep, progress: int = None):
        """단계 업데이트"""
        self.current_step = step
        self.updated_at = datetime.now().isoformat()
        if progress is not None:
            self.progress = progress


class CheckpointManager:
    """
    파이프라인 체크포인트 관리자

    기능:
    - 각 단계 완료 시 상태 저장
    - 실패 시 저장된 상태에서 재개
    - 최대 재시도 횟수 관리
    """

    DEFAULT_CHECKPOINT_DIR = "data/checkpoints"
    MAX_RETRY_COUNT = 3

    def __init__(self, checkpoint_dir: str = None):
        self.checkpoint_dir = Path(checkpoint_dir or self.DEFAULT_CHECKPOINT_DIR)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, story_id: str) -> Path:
        """체크포인트 파일 경로"""
        return self.checkpoint_dir / f"{story_id}.json"

    async def save(self, state: CheckpointState) -> None:
        """체크포인트 저장"""
        checkpoint_path = self._get_checkpoint_path(state.story_id)

        # 비동기 파일 쓰기
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._write_checkpoint,
            checkpoint_path,
            state.to_dict()
        )

        print(f"[Checkpoint] Saved: {state.current_step} ({state.progress}%)")

    def _write_checkpoint(self, path: Path, data: dict) -> None:
        """동기 파일 쓰기"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def load(self, story_id: str) -> Optional[CheckpointState]:
        """체크포인트 로드"""
        checkpoint_path = self._get_checkpoint_path(story_id)

        if not checkpoint_path.exists():
            return None

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self._read_checkpoint,
                checkpoint_path
            )
            state = CheckpointState.from_dict(data)
            print(f"[Checkpoint] Loaded: {state.current_step} ({state.progress}%)")
            return state
        except Exception as e:
            print(f"[Checkpoint] Load failed: {e}")
            return None

    def _read_checkpoint(self, path: Path) -> dict:
        """동기 파일 읽기"""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def delete(self, story_id: str) -> None:
        """체크포인트 삭제"""
        checkpoint_path = self._get_checkpoint_path(story_id)
        if checkpoint_path.exists():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, checkpoint_path.unlink)
            print(f"[Checkpoint] Deleted: {story_id}")

    async def can_resume(self, story_id: str) -> bool:
        """재개 가능 여부"""
        state = await self.load(story_id)
        if not state:
            return False

        # 실패 상태이고 재시도 횟수 미초과
        if state.current_step == PipelineStep.FAILED:
            return state.retry_count < self.MAX_RETRY_COUNT

        # 완료되지 않은 상태
        return state.current_step != PipelineStep.COMPLETED

    async def get_resume_point(self, story_id: str) -> Optional[PipelineStep]:
        """재개 지점 확인"""
        state = await self.load(story_id)
        if not state:
            return None

        if state.current_step == PipelineStep.FAILED:
            # 실패한 단계에서 재개
            return state.error_step

        # 다음 단계 반환
        steps = list(PipelineStep)
        current_idx = steps.index(state.current_step)
        if current_idx < len(steps) - 1:
            return steps[current_idx + 1]

        return None

    def create_initial_state(self, story_id: str) -> CheckpointState:
        """초기 상태 생성"""
        return CheckpointState(
            story_id=story_id,
            current_step=PipelineStep.INIT,
            progress=0
        )

    async def record_success(
        self,
        state: CheckpointState,
        step: PipelineStep,
        result: Any = None
    ) -> CheckpointState:
        """단계 성공 기록"""
        state.update_step(step)

        # 결과 저장
        if step == PipelineStep.CHARACTER_EXTRACTION and result:
            state.characters = [c if isinstance(c, dict) else c.__dict__ for c in result]
        elif step == PipelineStep.SCRIPT_GENERATION and result:
            state.script = result if isinstance(result, dict) else result.__dict__
        elif step == PipelineStep.PROMPT_GENERATION and result:
            state.prompts = result if isinstance(result, list) else [result]
        elif step == PipelineStep.AUDIO_GENERATION and result:
            state.audio_paths = result
        elif step == PipelineStep.IMAGE_GENERATION and result:
            state.image_paths = result
        elif step == PipelineStep.VIDEO_GENERATION and result:
            state.video_paths = result
        elif step == PipelineStep.COMPOSITION and result:
            state.final_video = result

        await self.save(state)
        return state

    async def record_failure(
        self,
        state: CheckpointState,
        error: Exception
    ) -> CheckpointState:
        """실패 기록"""
        state.current_step = PipelineStep.FAILED
        state.error_step = state.current_step
        state.error_message = str(error)
        state.retry_count += 1
        state.updated_at = datetime.now().isoformat()

        await self.save(state)
        return state

    async def list_checkpoints(self) -> List[Dict]:
        """모든 체크포인트 목록"""
        checkpoints = []

        for path in self.checkpoint_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                checkpoints.append({
                    "story_id": data["story_id"],
                    "step": data["current_step"],
                    "progress": data["progress"],
                    "updated_at": data["updated_at"],
                    "can_resume": data["current_step"] != "completed"
                })
            except:
                continue

        return checkpoints
