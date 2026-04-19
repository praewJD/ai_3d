"""
Execution Log Layer - 실행 결과 저장 및 재현

DB 대신 파일 기반 로그 시스템
나중에 DB로 교체 가능한 인터페이스 구조
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import hashlib
import logging
import aiofiles

logger = logging.getLogger(__name__)


# ============================================================
# 데이터 구조
# ============================================================

@dataclass
class SceneOutput:
    """단일 장면 출력 결과"""
    scene_id: str
    order: int

    # 생성 결과
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None

    # 프롬프트
    image_prompt: str = ""
    video_prompt: str = ""

    # 메타데이터
    generation_time_ms: int = 0
    api_cost_usd: float = 0.0
    success: bool = True
    error_message: str = ""


@dataclass
class RunResult:
    """실행 결과 전체"""
    run_id: str
    story_id: str
    title: str = ""

    # 입력
    input_story: str = ""

    # 중간 결과
    scene_raw: Dict[str, Any] = field(default_factory=dict)
    scene_validated: Dict[str, Any] = field(default_factory=dict)
    prompts: Dict[str, Any] = field(default_factory=dict)

    # 출력
    outputs: List[SceneOutput] = field(default_factory=list)

    # 최종 결과
    final_video_path: Optional[str] = None

    # 메타데이터
    started_at: str = ""
    completed_at: str = ""
    total_time_ms: int = 0
    total_cost_usd: float = 0.0
    success: bool = False
    error_message: str = ""

    # 설정
    style_type: str = "3d_disney"
    strategy: str = "smart_hybrid"

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunResult":
        """딕셔너리에서 생성"""
        # outputs 변환
        if "outputs" in data and isinstance(data["outputs"], list):
            data["outputs"] = [
                SceneOutput(**o) if isinstance(o, dict) else o
                for o in data["outputs"]
            ]
        return cls(**data)

    def calculate_hash(self) -> str:
        """입력 기반 해시 (캐싱용)"""
        hash_input = json.dumps({
            "story": self.input_story,
            "style": self.style_type,
            "strategy": self.strategy,
        }, sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    cache_key: str
    run_id: str
    created_at: str
    hit_count: int = 0


# ============================================================
# Repository 인터페이스
# ============================================================

class IProjectRepository:
    """프로젝트 저장소 인터페이스 (나중에 DB로 교체 가능)"""

    async def save_run(self, run: RunResult) -> str:
        """실행 결과 저장"""
        raise NotImplementedError

    async def load_run(self, run_id: str) -> Optional[RunResult]:
        """실행 결과 로드"""
        raise NotImplementedError

    async def find_by_story_hash(self, hash_key: str) -> Optional[RunResult]:
        """해시로 이전 실행 찾기 (캐싱용)"""
        raise NotImplementedError

    async def list_runs(self, limit: int = 10) -> List[RunResult]:
        """실행 목록"""
        raise NotImplementedError

    async def save_cache(self, entry: CacheEntry) -> None:
        """캐시 저장"""
        raise NotImplementedError

    async def get_cache(self, cache_key: str) -> Optional[CacheEntry]:
        """캐시 조회"""
        raise NotImplementedError


# ============================================================
# 파일 기반 구현
# ============================================================

class FileProjectRepository(IProjectRepository):
    """파일 기반 프로젝트 저장소"""

    def __init__(self, base_path: str = "data/runs"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.base_path / "cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def _get_run_dir(self, run_id: str) -> Path:
        """실행 디렉토리 경로"""
        return self.base_path / run_id

    async def save_run(self, run: RunResult) -> str:
        """실행 결과 저장"""
        run_dir = self._get_run_dir(run.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # 메인 메타데이터
        metadata_path = run_dir / "metadata.json"
        async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))

        # 입력 스토리
        if run.input_story:
            story_path = run_dir / "input_story.txt"
            async with aiofiles.open(story_path, 'w', encoding='utf-8') as f:
                await f.write(run.input_story)

        # Raw SceneGraph
        if run.scene_raw:
            raw_path = run_dir / "scene_raw.json"
            async with aiofiles.open(raw_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(run.scene_raw, ensure_ascii=False, indent=2))

        # Validated SceneGraph
        if run.scene_validated:
            validated_path = run_dir / "scene_validated.json"
            async with aiofiles.open(validated_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(run.scene_validated, ensure_ascii=False, indent=2))

        # Prompts
        if run.prompts:
            prompts_path = run_dir / "prompts.json"
            async with aiofiles.open(prompts_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(run.prompts, ensure_ascii=False, indent=2))

        logger.info(f"Run saved: {run.run_id}")
        return str(run_dir)

    async def load_run(self, run_id: str) -> Optional[RunResult]:
        """실행 결과 로드"""
        run_dir = self._get_run_dir(run_id)
        metadata_path = run_dir / "metadata.json"

        if not metadata_path.exists():
            return None

        async with aiofiles.open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())

        return RunResult.from_dict(data)

    async def find_by_story_hash(self, hash_key: str) -> Optional[RunResult]:
        """해시로 이전 실행 찾기"""
        cache_entry = await self.get_cache(hash_key)
        if cache_entry:
            return await self.load_run(cache_entry.run_id)
        return None

    async def list_runs(self, limit: int = 10) -> List[RunResult]:
        """실행 목록"""
        runs = []

        for run_dir in sorted(self.base_path.iterdir(), reverse=True):
            if run_dir.is_dir() and run_dir.name != "cache":
                metadata = run_dir / "metadata.json"
                if metadata.exists():
                    async with aiofiles.open(metadata, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                        runs.append(RunResult.from_dict(data))

                if len(runs) >= limit:
                    break

        return runs

    async def save_cache(self, entry: CacheEntry) -> None:
        """캐시 저장"""
        cache_file = self.cache_path / f"{entry.cache_key}.json"
        async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(asdict(entry), ensure_ascii=False, indent=2))

    async def get_cache(self, cache_key: str) -> Optional[CacheEntry]:
        """캐시 조회"""
        cache_file = self.cache_path / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())

        # hit count 증가
        entry = CacheEntry(**data)
        entry.hit_count += 1
        await self.save_cache(entry)

        return entry


# ============================================================
# 실행 로그 매니저
# ============================================================

class ExecutionLogger:
    """실행 로그 관리자"""

    def __init__(self, repository: IProjectRepository = None):
        self.repository = repository or FileProjectRepository()
        self._current_run: Optional[RunResult] = None

    def start_run(
        self,
        story_id: str,
        input_story: str,
        style_type: str = "3d_disney",
        strategy: str = "smart_hybrid"
    ) -> RunResult:
        """새 실행 시작"""
        from datetime import datetime
        import uuid

        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        self._current_run = RunResult(
            run_id=run_id,
            story_id=story_id,
            input_story=input_story,
            style_type=style_type,
            strategy=strategy,
            started_at=datetime.now().isoformat(),
        )

        return self._current_run

    def save_scene_raw(self, scene_graph_dict: Dict[str, Any]) -> None:
        """Raw SceneGraph 저장"""
        if self._current_run:
            self._current_run.scene_raw = scene_graph_dict

    def save_scene_validated(self, scene_graph_dict: Dict[str, Any]) -> None:
        """Validated SceneGraph 저장"""
        if self._current_run:
            self._current_run.scene_validated = scene_graph_dict

    def save_prompts(self, prompts_dict: Dict[str, Any]) -> None:
        """프롬프트 저장"""
        if self._current_run:
            self._current_run.prompts = prompts_dict

    def add_scene_output(self, output: SceneOutput) -> None:
        """장면 출력 추가"""
        if self._current_run:
            self._current_run.outputs.append(output)
            self._current_run.total_cost_usd += output.api_cost_usd

    def complete_run(
        self,
        final_video_path: str = None,
        success: bool = True,
        error_message: str = ""
    ) -> RunResult:
        """실행 완료"""
        from datetime import datetime

        if not self._current_run:
            raise ValueError("No active run")

        self._current_run.completed_at = datetime.now().isoformat()
        self._current_run.final_video_path = final_video_path
        self._current_run.success = success
        self._current_run.error_message = error_message

        # 시작-끝 시간 계산
        if self._current_run.started_at and self._current_run.completed_at:
            start = datetime.fromisoformat(self._current_run.started_at)
            end = datetime.fromisoformat(self._current_run.completed_at)
            self._current_run.total_time_ms = int((end - start).total_seconds() * 1000)

        return self._current_run

    async def save_and_cache(self) -> str:
        """저장 및 캐시 등록"""
        if not self._current_run:
            raise ValueError("No active run")

        # 저장
        run_dir = await self.repository.save_run(self._current_run)

        # 캐시 등록
        cache_key = self._current_run.calculate_hash()
        await self.repository.save_cache(CacheEntry(
            cache_key=cache_key,
            run_id=self._current_run.run_id,
            created_at=self._current_run.started_at,
        ))

        return run_dir

    async def check_cache(self, input_story: str, style_type: str, strategy: str) -> Optional[RunResult]:
        """캐시 확인"""
        temp_run = RunResult(
            run_id="temp",
            story_id="temp",
            input_story=input_story,
            style_type=style_type,
            strategy=strategy,
        )
        cache_key = temp_run.calculate_hash()

        cached = await self.repository.find_by_story_hash(cache_key)
        if cached:
            logger.info(f"Cache hit: {cache_key}")
        return cached


# ============================================================
# 편의 함수
# ============================================================

_logger: Optional[ExecutionLogger] = None


def get_execution_logger() -> ExecutionLogger:
    """싱글톤 로거"""
    global _logger
    if _logger is None:
        _logger = ExecutionLogger()
    return _logger
