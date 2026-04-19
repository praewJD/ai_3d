"""
Quality Metrics - 품질 점수 데이터클래스

이미지/영상의 품질을 수치화
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class QualityLevel(str, Enum):
    """품질 등급"""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"           # 70-89
    ACCEPTABLE = "acceptable"  # 50-69
    POOR = "poor"           # 30-49
    BAD = "bad"             # 0-29


@dataclass
class ImageQualityMetrics:
    """이미지 품질 메트릭"""
    # 전체 점수
    overall_score: float = 0.0  # 0-100

    # 세부 점수
    sharpness_score: float = 0.0      # 선명도
    contrast_score: float = 0.0       # 대비
    brightness_score: float = 0.0     # 밝기 적절성
    color_score: float = 0.0          # 색상 품질
    composition_score: float = 0.0    # 구도

    # 감지된 문제
    is_blurry: bool = False
    is_too_dark: bool = False
    is_too_bright: bool = False
    is_low_contrast: bool = False
    has_noise: bool = False
    has_artifacts: bool = False

    # 얼굴 관련
    faces_detected: int = 0
    face_quality_score: float = 0.0
    has_face_distortion: bool = False

    # 해상도
    width: int = 0
    height: int = 0
    aspect_ratio: float = 0.0
    resolution_score: float = 0.0

    # 문제 목록
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def quality_level(self) -> QualityLevel:
        """품질 등급 반환"""
        if self.overall_score >= 90:
            return QualityLevel.EXCELLENT
        elif self.overall_score >= 70:
            return QualityLevel.GOOD
        elif self.overall_score >= 50:
            return QualityLevel.ACCEPTABLE
        elif self.overall_score >= 30:
            return QualityLevel.POOR
        else:
            return QualityLevel.BAD

    @property
    def is_acceptable(self) -> bool:
        """사용 가능한 품질인지"""
        return self.overall_score >= 50 and not self.has_face_distortion

    @property
    def resolution_str(self) -> str:
        """해상도 문자열"""
        return f"{self.width}x{self.height}"


@dataclass
class VideoQualityMetrics:
    """영상 품질 메트릭"""
    # 전체 점수
    overall_score: float = 0.0

    # 프레임 품질
    avg_frame_score: float = 0.0
    min_frame_score: float = 0.0
    max_frame_score: float = 0.0

    # 일관성
    consistency_score: float = 0.0      # 프레임 간 일관성
    flickering_detected: bool = False   # 깜빡임 감지
    jitter_detected: bool = False       # 지터 감지

    # 모션
    motion_smoothness: float = 0.0      # 모션 부드러움
    motion_amount: float = 0.0          # 모션 양

    # 안정성
    stability_score: float = 0.0        # 화면 안정성

    # 오디오 싱크
    audio_sync_score: float = 0.0       # 오디오 동기화

    # 해상도
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    frame_count: int = 0

    # 얼굴
    faces_detected: int = 0
    face_consistency: float = 0.0       # 얼굴 일관성

    # 문제
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def quality_level(self) -> QualityLevel:
        """품질 등급"""
        if self.overall_score >= 90:
            return QualityLevel.EXCELLENT
        elif self.overall_score >= 70:
            return QualityLevel.GOOD
        elif self.overall_score >= 50:
            return QualityLevel.ACCEPTABLE
        elif self.overall_score >= 30:
            return QualityLevel.POOR
        else:
            return QualityLevel.BAD

    @property
    def is_acceptable(self) -> bool:
        """사용 가능 여부"""
        return (
            self.overall_score >= 50 and
            not self.flickering_detected and
            self.face_consistency >= 0.7
        )


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    metrics: ImageQualityMetrics | VideoQualityMetrics
    should_regenerate: bool = False
    regeneration_reason: Optional[str] = None
    suggested_fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "is_valid": self.is_valid,
            "should_regenerate": self.should_regenerate,
            "regeneration_reason": self.regeneration_reason,
            "suggested_fixes": self.suggested_fixes,
            "metrics": {
                "overall_score": self.metrics.overall_score,
                "quality_level": self.metrics.quality_level.value,
                "issues": self.metrics.issues,
                "warnings": self.metrics.warnings
            }
        }
