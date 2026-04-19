"""
Video Validator - 영상 품질 검증

검증 항목:
- 프레임 일관성 (깜빡임, 지터)
- 모션 부드러움
- 얼굴 일관성
- 해상도/비율
- 오디오 싱크
"""
import asyncio
import logging
from typing import Optional, List
from pathlib import Path
import json

from .base_validator import BaseValidator
from .quality_metrics import (
    VideoQualityMetrics,
    ValidationResult,
    QualityLevel
)

logger = logging.getLogger(__name__)


class VideoValidator(BaseValidator):
    """
    영상 품질 검증기
    """

    def __init__(self, strict_mode: bool = False):
        super().__init__(strict_mode)
        self._cv2 = None
        self._np = None

    def _lazy_import(self):
        """지연 import"""
        if self._cv2 is None:
            try:
                import cv2
                import numpy as np
                self._cv2 = cv2
                self._np = np
            except ImportError:
                logger.warning("OpenCV not installed, video validation limited")
                self._cv2 = None
                self._np = None

    async def validate(self, source: str) -> ValidationResult:
        """
        영상 검증

        Args:
            source: 영상 파일 경로

        Returns:
            ValidationResult
        """
        self._lazy_import()

        if not await self.check_exists(source):
            return ValidationResult(
                is_valid=False,
                metrics=VideoQualityMetrics(issues=["Video file not found"]),
                should_regenerate=True,
                regeneration_reason="File not found"
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._validate_sync,
            source
        )

        self._log_result(source, result)
        return result

    def _validate_sync(self, source: str) -> ValidationResult:
        """동기 검증"""
        metrics = VideoQualityMetrics()

        try:
            if self._cv2 is not None:
                metrics = self._validate_with_opencv(source)
            else:
                metrics = self._validate_basic(source)
        except Exception as e:
            logger.error(f"Video validation error: {e}")
            metrics.issues.append(f"Validation error: {str(e)}")

        metrics.overall_score = self._calculate_overall_score(metrics)

        should_regenerate = (
            not metrics.is_acceptable or
            metrics.flickering_detected or
            (metrics.faces_detected > 0 and metrics.face_consistency < 0.5)
        )

        return ValidationResult(
            is_valid=metrics.is_acceptable,
            metrics=metrics,
            should_regenerate=should_regenerate,
            regeneration_reason=self._get_regeneration_reason(metrics),
            suggested_fixes=self._get_suggested_fixes(metrics)
        )

    def _validate_with_opencv(self, source: str) -> VideoQualityMetrics:
        """OpenCV 기반 검증"""
        metrics = VideoQualityMetrics()

        cap = self._cv2.VideoCapture(source)
        if not cap.isOpened():
            metrics.issues.append("Cannot open video file")
            return metrics

        try:
            # 기본 정보
            metrics.width = int(cap.get(self._cv2.CAP_PROP_FRAME_WIDTH))
            metrics.height = int(cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT))
            metrics.fps = cap.get(self._cv2.CAP_PROP_FPS)
            metrics.frame_count = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT))
            metrics.duration = metrics.frame_count / metrics.fps if metrics.fps > 0 else 0

            # 프레임 분석
            frame_scores = []
            prev_frame = None
            frame_diffs = []
            face_counts = []

            frame_cascade = self._load_face_cascade()

            sample_rate = max(1, metrics.frame_count // 30)  # 최대 30프레임 샘플링

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_rate == 0:
                    gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)

                    # 프레임 품질
                    laplacian_var = self._cv2.Laplacian(gray, self._cv2.CV_64F).var()
                    frame_scores.append(min(100, laplacian_var / 2))

                    # 프레임 간 차이 (깜빡임/지터 감지)
                    if prev_frame is not None:
                        diff = self._cv2.absdiff(prev_frame, gray)
                        diff_score = diff.mean()
                        frame_diffs.append(diff_score)

                    prev_frame = gray.copy()

                    # 얼굴 감지
                    if frame_cascade is not None:
                        faces = frame_cascade.detectMultiScale(gray, 1.1, 5)
                        face_counts.append(len(faces))

                frame_idx += 1

            # 메트릭 계산
            if frame_scores:
                metrics.avg_frame_score = sum(frame_scores) / len(frame_scores)
                metrics.min_frame_score = min(frame_scores)
                metrics.max_frame_score = max(frame_scores)

            # 일관성 (프레임 간 차이의 표준편차)
            if frame_diffs:
                diff_array = self._np.array(frame_diffs)
                metrics.consistency_score = max(0, 100 - diff_array.std() * 2)

                # 깜빡임 감지 (급격한 밝기 변화)
                sudden_changes = self._np.sum(diff_array > diff_array.mean() * 3)
                metrics.flickering_detected = sudden_changes > len(frame_diffs) * 0.1

                if metrics.flickering_detected:
                    metrics.issues.append("Flickering detected in video")

                # 지터 감지 (불규칙한 움직임)
                jitter_score = self._np.std(self._np.diff(frame_diffs))
                metrics.jitter_detected = jitter_score > 10
                if metrics.jitter_detected:
                    metrics.issues.append("Jitter/instability detected")

            # 얼굴 일관성
            if face_counts:
                non_zero_faces = [f for f in face_counts if f > 0]
                if non_zero_faces:
                    metrics.faces_detected = int(self._np.mean(non_zero_faces))
                    # 얼굴 수의 일관성
                    face_std = self._np.std(non_zero_faces)
                    metrics.face_consistency = max(0, 1 - face_std / 5)
                else:
                    metrics.faces_detected = 0
                    metrics.face_consistency = 1.0

            # 모션 부드러움
            if frame_diffs and len(frame_diffs) > 1:
                # 연속적인 차이 = 부드러운 모션
                smoothness = 1 - (self._np.diff(frame_diffs).std() / 50)
                metrics.motion_smoothness = max(0, min(100, smoothness * 100))
                metrics.motion_amount = self._np.mean(frame_diffs)

        finally:
            cap.release()

        return metrics

    def _validate_basic(self, source: str) -> VideoQualityMetrics:
        """기본 검증 (OpenCV 없음)"""
        metrics = VideoQualityMetrics()
        metrics.issues.append("Full video validation requires OpenCV")
        metrics.warnings.append("Install opencv-python for detailed analysis")

        # 파일 크기만 체크
        try:
            file_size = Path(source).stat().st_size
            if file_size < 1000:
                metrics.issues.append("Video file too small")
        except:
            pass

        return metrics

    def _load_face_cascade(self):
        """얼굴 감지 로드"""
        try:
            return self._cv2.CascadeClassifier(
                self._cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
        except:
            return None

    def _calculate_overall_score(self, metrics: VideoQualityMetrics) -> float:
        """전체 점수"""
        weights = {
            'frame_quality': 0.30,
            'consistency': 0.25,
            'motion_smoothness': 0.20,
            'stability': 0.15,
            'face_consistency': 0.10
        }

        score = (
            weights['frame_quality'] * metrics.avg_frame_score +
            weights['consistency'] * metrics.consistency_score +
            weights['motion_smoothness'] * metrics.motion_smoothness +
            weights['stability'] * (100 if not metrics.jitter_detected else 50)
        )

        # 얼굴 일관성 조정
        if metrics.faces_detected > 0:
            score = score * 0.9 + weights['face_consistency'] * metrics.face_consistency * 100

        # 문제 감점
        if metrics.flickering_detected:
            score *= 0.7
        if metrics.jitter_detected:
            score *= 0.85

        penalty = len(metrics.issues) * 5
        return max(0, score - penalty)

    def _get_regeneration_reason(self, metrics: VideoQualityMetrics) -> Optional[str]:
        """재생성 사유"""
        if metrics.flickering_detected:
            return "Video has flickering issues"
        if metrics.jitter_detected:
            return "Video has jitter/instability"
        if metrics.face_consistency < 0.5 and metrics.faces_detected > 0:
            return "Face consistency is too low"
        if metrics.avg_frame_score < 30:
            return "Overall frame quality is poor"
        return None

    def _get_suggested_fixes(self, metrics: VideoQualityMetrics) -> List[str]:
        """개선 제안"""
        fixes = []

        if metrics.flickering_detected:
            fixes.append("Use higher generation steps")
            fixes.append("Enable frame interpolation")
        if metrics.jitter_detected:
            fixes.append("Add motion smoothing")
            fixes.append("Reduce motion strength in prompt")
        if metrics.face_consistency < 0.7:
            fixes.append("Use face reference image")
            fixes.append("Enable face consistency mode")
        if metrics.avg_frame_score < 50:
            fixes.append("Increase source image quality")
            fixes.append("Use higher resolution model")

        return fixes

    async def validate_batch(self, sources: list[str]) -> list[ValidationResult]:
        """일괄 검증"""
        results = []
        for source in sources:
            result = await self.validate(source)
            results.append(result)
        return results

    async def compare_videos(
        self,
        sources: list[str]
    ) -> List[tuple[str, float]]:
        """
        여러 영상 품질 비교

        Returns:
            [(경로, 점수)] 정렬된 목록
        """
        results = await self.validate_batch(sources)
        scored = [
            (src, r.metrics.overall_score)
            for src, r in zip(sources, results)
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)
