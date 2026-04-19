"""Metrics Collector - 스토리 생성 메트릭 수집 및 저장"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json
import os


@dataclass
class StoryMetrics:
    """스토리 생성 메트릭"""
    story_id: str
    hook_score: float = 0.0  # 0~10
    arc_quality: float = 0.0
    scene_consistency: float = 0.0
    scene_count: int = 0
    total_duration: float = 0.0
    retry_count: int = 0
    generation_cost: float = 0.0
    total_time_seconds: float = 0.0
    target_format: str = "shorts"
    created_at: str = ""
    completed_at: str = ""
    errors: List[str] = field(default_factory=list)
    stages: Dict[str, float] = field(default_factory=dict)  # stage_name -> duration

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


class MetricsCollector:
    """메트릭 수집 및 저장"""

    def __init__(self, output_dir: str = "data/metrics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, StoryMetrics] = {}
        self._start_times: Dict[str, Dict[str, datetime]] = {}

    def start_story(self, story_id: str, target: str = "shorts") -> StoryMetrics:
        """새 스토리 메트릭 시작"""
        metrics = StoryMetrics(
            story_id=story_id,
            target_format=target,
            created_at=datetime.now().isoformat()
        )
        self.metrics[story_id] = metrics
        self._start_times[story_id] = {"_story": datetime.now()}
        return metrics

    def start_stage(self, story_id: str, stage: str):
        """단계 시작 시간 기록"""
        if story_id not in self._start_times:
            self._start_times[story_id] = {}
        self._start_times[story_id][stage] = datetime.now()

    def end_stage(self, story_id: str, stage: str):
        """단계 종료 및 소요 시간 기록"""
        if story_id not in self._start_times:
            return
        if stage not in self._start_times[story_id]:
            return
        if story_id not in self.metrics:
            return

        start_time = self._start_times[story_id].pop(stage, None)
        if start_time:
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics[story_id].stages[stage] = duration

    def record_hook_score(self, story_id: str, score: float):
        """Hook 점수 기록 (0~10)"""
        if story_id in self.metrics:
            self.metrics[story_id].hook_score = max(0.0, min(10.0, score))

    def record_arc_quality(self, story_id: str, quality: float):
        """아크 품질 기록 (0~10)"""
        if story_id in self.metrics:
            self.metrics[story_id].arc_quality = max(0.0, min(10.0, quality))

    def record_scene_consistency(self, story_id: str, consistency: float):
        """장면 일관성 기록 (0~10)"""
        if story_id in self.metrics:
            self.metrics[story_id].scene_consistency = max(0.0, min(10.0, consistency))

    def record_scene_count(self, story_id: str, count: int):
        """장면 수 기록"""
        if story_id in self.metrics:
            self.metrics[story_id].scene_count = count

    def record_retry(self, story_id: str, reason: str):
        """재시도 기록"""
        if story_id in self.metrics:
            self.metrics[story_id].retry_count += 1

    def record_cost(self, story_id: str, cost: float):
        """비용 기록 (누적)"""
        if story_id in self.metrics:
            self.metrics[story_id].generation_cost += cost

    def record_error(self, story_id: str, error: str):
        """에러 기록"""
        if story_id in self.metrics:
            self.metrics[story_id].errors.append(error)

    def complete_story(self, story_id: str, duration: float = None) -> Optional[StoryMetrics]:
        """스토리 완료 처리"""
        if story_id not in self.metrics:
            return None

        metrics = self.metrics[story_id]
        metrics.completed_at = datetime.now().isoformat()

        # 총 소요 시간 계산
        if story_id in self._start_times and "_story" in self._start_times[story_id]:
            start = self._start_times[story_id]["_story"]
            metrics.total_time_seconds = (datetime.now() - start).total_seconds()
        elif duration is not None:
            metrics.total_time_seconds = duration

        # 정리
        if story_id in self._start_times:
            del self._start_times[story_id]

        return metrics

    def save(self, story_id: str) -> bool:
        """JSON으로 저장"""
        if story_id not in self.metrics:
            return False

        metrics = self.metrics[story_id]
        file_path = self.output_dir / f"{story_id}.json"

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(metrics.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save metrics: {e}")
            return False

    def load(self, story_id: str) -> Optional[StoryMetrics]:
        """저장된 메트릭 로드"""
        file_path = self.output_dir / f"{story_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            metrics = StoryMetrics(**data)
            self.metrics[story_id] = metrics
            return metrics
        except Exception as e:
            print(f"Failed to load metrics: {e}")
            return None

    def get_metrics(self, story_id: str) -> Optional[StoryMetrics]:
        """메트릭 조회"""
        return self.metrics.get(story_id)

    def get_summary(self) -> Dict[str, Any]:
        """전체 요약 통계"""
        if not self.metrics:
            return {
                "total_stories": 0,
                "message": "No metrics collected"
            }

        total = len(self.metrics)
        completed = sum(1 for m in self.metrics.values() if m.completed_at)
        total_cost = sum(m.generation_cost for m in self.metrics.values())
        total_retries = sum(m.retry_count for m in self.metrics.values())
        total_errors = sum(len(m.errors) for m in self.metrics.values())
        avg_hook = sum(m.hook_score for m in self.metrics.values()) / total
        avg_arc = sum(m.arc_quality for m in self.metrics.values()) / total
        avg_consistency = sum(m.scene_consistency for m in self.metrics.values()) / total
        avg_time = sum(m.total_time_seconds for m in self.metrics.values()) / total

        return {
            "total_stories": total,
            "completed_stories": completed,
            "total_cost": total_cost,
            "total_retries": total_retries,
            "total_errors": total_errors,
            "averages": {
                "hook_score": round(avg_hook, 2),
                "arc_quality": round(avg_arc, 2),
                "scene_consistency": round(avg_consistency, 2),
                "time_seconds": round(avg_time, 2)
            }
        }

    def save_summary(self) -> bool:
        """요약 저장"""
        summary = self.get_summary()
        file_path = self.output_dir / "summary.json"

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save summary: {e}")
            return False

    def clear(self, story_id: str = None):
        """메트릭 정리"""
        if story_id:
            self.metrics.pop(story_id, None)
            self._start_times.pop(story_id, None)
        else:
            self.metrics.clear()
            self._start_times.clear()
