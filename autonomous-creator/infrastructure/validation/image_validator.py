"""
Image Validator - 이미지 품질 검증

검증 항목:
- 블러 감지 (Laplacian 분산)
- 밝기/대비
- 얼굴 왜곡 감지
- 해상도/비율
- 색상 품질
"""
import asyncio
import logging
from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass

from .base_validator import BaseValidator
from .quality_metrics import (
    ImageQualityMetrics,
    ValidationResult,
    QualityLevel
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationThresholds:
    """검증 임계값"""
    # 블러 감지 (Laplacian 분산)
    blur_threshold: float = 100.0

    # 밝기
    min_brightness: float = 20.0
    max_brightness: float = 235.0

    # 대비
    min_contrast: float = 30.0

    # 해상도
    min_width: int = 512
    min_height: int = 512
    recommended_width: int = 1024
    recommended_height: int = 1024

    # 얼굴
    face_detection_confidence: float = 0.8
    face_distortion_threshold: float = 0.3


class ImageValidator(BaseValidator):
    """
    이미지 품질 검증기

    OpenCV/PIL을 사용한 실제 품질 측정
    """

    def __init__(
        self,
        thresholds: ValidationThresholds = None,
        strict_mode: bool = False
    ):
        super().__init__(strict_mode)
        self.thresholds = thresholds or ValidationThresholds()
        self._cv2 = None
        self._np = None
        self._PIL = None

    def _lazy_import(self):
        """지연 import (선택적 의존성)"""
        if self._cv2 is None:
            try:
                import cv2
                import numpy as np
                from PIL import Image
                self._cv2 = cv2
                self._np = np
                self._PIL = Image
            except ImportError:
                logger.warning("OpenCV/PIL not installed, using basic validation")
                self._cv2 = None
                self._np = None
                self._PIL = None

    async def validate(self, source: str) -> ValidationResult:
        """
        이미지 검증

        Args:
            source: 이미지 파일 경로

        Returns:
            ValidationResult
        """
        self._lazy_import()

        if not await self.check_exists(source):
            return ValidationResult(
                is_valid=False,
                metrics=ImageQualityMetrics(issues=["File not found"]),
                should_regenerate=True,
                regeneration_reason="File not found"
            )

        # 실제 검증은 CPU 작업이므로 별도 스레드에서
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._validate_sync,
            source
        )

        self._log_result(source, result)
        return result

    def _validate_sync(self, source: str) -> ValidationResult:
        """동기 검증 로직"""
        metrics = ImageQualityMetrics()

        try:
            if self._cv2 is not None:
                # OpenCV 기반 검증
                metrics = self._validate_with_opencv(source)
            elif self._PIL is not None:
                # PIL 기반 기본 검증
                metrics = self._validate_with_pil(source)
            else:
                # 라이브러리 없음 - 기본 검증만
                metrics = self._validate_basic(source)

        except Exception as e:
            logger.error(f"Validation error: {e}")
            metrics.issues.append(f"Validation error: {str(e)}")

        # 전체 점수 계산
        metrics.overall_score = self._calculate_overall_score(metrics)

        # 재생성 필요 여부
        should_regenerate = (
            not metrics.is_acceptable or
            metrics.has_face_distortion or
            len(metrics.issues) > 2
        )

        return ValidationResult(
            is_valid=metrics.is_acceptable,
            metrics=metrics,
            should_regenerate=should_regenerate,
            regeneration_reason=self._get_regeneration_reason(metrics),
            suggested_fixes=self._get_suggested_fixes(metrics)
        )

    def _validate_with_opencv(self, source: str) -> ImageQualityMetrics:
        """OpenCV 기반 상세 검증"""
        metrics = ImageQualityMetrics()

        # 이미지 로드
        img = self._cv2.imread(source)
        if img is None:
            metrics.issues.append("Cannot read image file")
            return metrics

        gray = self._cv2.cvtColor(img, self._cv2.COLOR_BGR2GRAY)
        height, width = img.shape[:2]

        # 해상도
        metrics.width = width
        metrics.height = height
        metrics.aspect_ratio = width / height
        metrics.resolution_score = self._score_resolution(width, height)

        # 블러 감지 (Laplacian 분산)
        laplacian_var = self._cv2.Laplacian(gray, self._cv2.CV_64F).var()
        metrics.sharpness_score = min(100, laplacian_var / 2)
        metrics.is_blurry = laplacian_var < self.thresholds.blur_threshold
        if metrics.is_blurry:
            metrics.issues.append(f"Image is blurry (sharpness: {laplacian_var:.1f})")

        # 밝기
        mean_brightness = gray.mean()
        metrics.brightness_score = self._score_brightness(mean_brightness)
        metrics.is_too_dark = mean_brightness < self.thresholds.min_brightness
        metrics.is_too_bright = mean_brightness > self.thresholds.max_brightness

        if metrics.is_too_dark:
            metrics.issues.append(f"Image is too dark (brightness: {mean_brightness:.1f})")
        if metrics.is_too_bright:
            metrics.issues.append(f"Image is too bright (brightness: {mean_brightness:.1f})")

        # 대비
        contrast = gray.std()
        metrics.contrast_score = min(100, contrast * 2)
        metrics.is_low_contrast = contrast < self.thresholds.min_contrast
        if metrics.is_low_contrast:
            metrics.issues.append(f"Low contrast (contrast: {contrast:.1f})")

        # 색상 품질
        metrics.color_score = self._score_color(img)

        # 얼굴 감지 (선택적)
        try:
            metrics.faces_detected, metrics.face_quality_score, metrics.has_face_distortion = \
                self._detect_faces(gray)
            if metrics.has_face_distortion:
                metrics.issues.append("Face distortion detected")
        except Exception as e:
            logger.debug(f"Face detection skipped: {e}")

        return metrics

    def _validate_with_pil(self, source: str) -> ImageQualityMetrics:
        """PIL 기반 기본 검증"""
        metrics = ImageQualityMetrics()

        try:
            with self._PIL.open(source) as img:
                metrics.width, metrics.height = img.size
                metrics.aspect_ratio = metrics.width / metrics.height
                metrics.resolution_score = self._score_resolution(
                    metrics.width, metrics.height
                )

                # 밝기 (그레이스케일 변환 후)
                gray = img.convert('L')
                import numpy as np
                pixels = np.array(gray)
                mean_brightness = pixels.mean()
                metrics.brightness_score = self._score_brightness(mean_brightness)

                contrast = pixels.std()
                metrics.contrast_score = min(100, contrast * 2)

        except Exception as e:
            metrics.issues.append(f"PIL validation error: {e}")

        return metrics

    def _validate_basic(self, source: str) -> ImageQualityMetrics:
        """라이브러리 없는 기본 검증"""
        metrics = ImageQualityMetrics()
        metrics.issues.append("Full validation requires OpenCV or PIL")
        metrics.warnings.append("Installing opencv-python or pillow recommended")
        return metrics

    def _score_resolution(self, width: int, height: int) -> float:
        """해상도 점수"""
        if width >= self.thresholds.recommended_width and \
           height >= self.thresholds.recommended_height:
            return 100.0
        elif width >= self.thresholds.min_width and \
             height >= self.thresholds.min_height:
            return 70.0
        else:
            return 30.0

    def _score_brightness(self, mean: float) -> float:
        """밝기 점수 (중간값일수록 높음)"""
        optimal = 127.5
        deviation = abs(mean - optimal)
        return max(0, 100 - deviation)

    def _score_color(self, img) -> float:
        """색상 품질 점수"""
        # BGR 채널 분리
        b, g, r = self._cv2.split(img)

        # 채널 간 상관관계 (너무 높으면 단색에 가까움)
        corr_rg = self._np.corrcoef(r.flatten(), g.flatten())[0, 1]
        corr_rb = self._np.corrcoef(r.flatten(), b.flatten())[0, 1]
        corr_gb = self._np.corrcoef(g.flatten(), b.flatten())[0, 1]

        avg_corr = (abs(corr_rg) + abs(corr_rb) + abs(corr_gb)) / 3

        # 적절한 다양성이 있으면 좋은 점수
        # 너무 낮으면 노이즈, 너무 높으면 단색
        if self._np.isnan(avg_corr):
            return 50.0

        # 0.5~0.8 사이가 적당
        if 0.5 <= avg_corr <= 0.8:
            return 100.0
        elif 0.3 <= avg_corr <= 0.9:
            return 70.0
        else:
            return 40.0

    def _detect_faces(self, gray) -> tuple:
        """얼굴 감지"""
        try:
            face_cascade = self._cv2.CascadeClassifier(
                self._cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            num_faces = len(faces)

            if num_faces == 0:
                return 0, 0.0, False

            # 얼굴 품질 점수 (크기 기반)
            face_scores = []
            for (x, y, w, h) in faces:
                # 얼굴이 너무 작거나 크면 감점
                size_score = min(w, h) / 100 * 100
                face_scores.append(min(100, size_score))

            avg_face_quality = sum(face_scores) / len(face_scores)

            # 얼굴 왜곡 감지 (비정상적인 비율)
            distortion_detected = False
            for (x, y, w, h) in faces:
                aspect = w / h
                if aspect < 0.7 or aspect > 1.3:
                    distortion_detected = True
                    break

            return num_faces, avg_face_quality, distortion_detected

        except Exception as e:
            logger.debug(f"Face detection error: {e}")
            return 0, 0.0, False

    def _calculate_overall_score(self, metrics: ImageQualityMetrics) -> float:
        """전체 점수 계산"""
        weights = {
            'sharpness': 0.25,
            'brightness': 0.15,
            'contrast': 0.15,
            'color': 0.15,
            'resolution': 0.20,
            'composition': 0.10
        }

        score = (
            weights['sharpness'] * metrics.sharpness_score +
            weights['brightness'] * metrics.brightness_score +
            weights['contrast'] * metrics.contrast_score +
            weights['color'] * metrics.color_score +
            weights['resolution'] * metrics.resolution_score
        )

        # 얼굴 관련 조정
        if metrics.faces_detected > 0:
            if metrics.has_face_distortion:
                score *= 0.5  # 얼굴 왜곡 시 50% 감점
            else:
                score = score * 0.9 + metrics.face_quality_score * 0.1

        # 문제별 감점
        penalty = len(metrics.issues) * 5
        score = max(0, score - penalty)

        return round(score, 1)

    def _get_regeneration_reason(self, metrics: ImageQualityMetrics) -> Optional[str]:
        """재생성 사유"""
        if not metrics.issues:
            return None

        if metrics.has_face_distortion:
            return "Face distortion detected"
        if metrics.is_blurry:
            return "Image is too blurry"
        if len(metrics.issues) >= 3:
            return "Multiple quality issues detected"

        return None

    def _get_suggested_fixes(self, metrics: ImageQualityMetrics) -> List[str]:
        """개선 제안"""
        fixes = []

        if metrics.is_blurry:
            fixes.append("Increase generation steps for sharper output")
        if metrics.is_too_dark:
            fixes.append("Add 'bright lighting' to prompt")
        if metrics.is_too_bright:
            fixes.append("Add 'soft shadows' to prompt")
        if metrics.is_low_contrast:
            fixes.append("Add 'high contrast' or 'dramatic lighting' to prompt")
        if metrics.resolution_score < 50:
            fixes.append("Generate at higher resolution")

        return fixes

    async def validate_batch(
        self,
        sources: list[str]
    ) -> list[ValidationResult]:
        """일괄 검증"""
        results = []
        for source in sources:
            result = await self.validate(source)
            results.append(result)
        return results

    async def get_best_image(
        self,
        sources: list[str]
    ) -> tuple[Optional[str], ValidationResult]:
        """
        여러 이미지 중 최고 품질 선택

        Returns:
            (최고 이미지 경로, 검증 결과)
        """
        results = await self.validate_batch(sources)

        valid_results = [
            (src, r) for src, r in zip(sources, results)
            if r.is_valid
        ]

        if not valid_results:
            # 모두 실패면 점수 높은 것 선택
            all_results = list(zip(sources, results))
            best = max(all_results, key=lambda x: x[1].metrics.overall_score)
            return best[0], best[1]

        best = max(valid_results, key=lambda x: x[1].metrics.overall_score)
        return best[0], best[1]
