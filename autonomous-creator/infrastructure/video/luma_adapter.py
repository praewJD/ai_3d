"""
Luma Video Adapter - Luma API를 파이프라인에 통합

HybridVideoManager와 LumaProvider 연결
비용 최적화 설정 지원
"""
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging

from core.domain.entities.story import Scene
from core.domain.entities.video import VideoSegment
from infrastructure.api.providers.video.base import (
    VideoGenerationRequest,
    VideoResolution
)
from infrastructure.api.providers.video.luma import LumaProvider, create_luma_provider
from infrastructure.api.config.api_config import get_api_config, VideoGenerationStrategy
from config.settings import get_settings

logger = logging.getLogger(__name__)


class VideoProviderType(str, Enum):
    """비디오 생성 프로바이더"""
    LUMA = "luma"
    LOCAL = "local"  # FramePack/SVD
    AUTO = "auto"    # 자동 선택


@dataclass
class LumaAdapterConfig:
    """Luma 어댑터 설정"""
    # 프로바이더 선택
    default_provider: VideoProviderType = VideoProviderType.AUTO

    # Luma 설정
    luma_model: str = "kling-2.6"
    luma_resolution: str = "1080p"

    # 폴백 설정
    fallback_to_local: bool = True
    max_retries: int = 2

    # 장면 분류
    key_scene_threshold: float = 0.7  # 핵심 장면 기준
    use_luma_for_key_scenes: bool = True
    use_luma_for_all: bool = False

    # 💰 비용 최적화
    monthly_budget_usd: float = 100.0
    auto_cost_saving: bool = True
    key_scene_ratio: float = 0.3

    # 사용량 추적
    current_month_usage_usd: float = 0.0
    current_month_credits: int = 0

    @classmethod
    def from_api_config(cls) -> "LumaAdapterConfig":
        """API 설정에서 생성"""
        api_config = get_api_config()

        # 전략에 따른 설정
        strategy = api_config.video_generation_strategy

        if strategy == VideoGenerationStrategy.ALL_API:
            use_for_all = True
            use_for_key = True
        elif strategy == VideoGenerationStrategy.KEY_SCENES_API:
            use_for_all = False
            use_for_key = True
        elif strategy == VideoGenerationStrategy.LOCAL_FIRST:
            use_for_all = False
            use_for_key = False
        else:  # SMART_HYBRID
            use_for_all = False
            use_for_key = True

        return cls(
            default_provider=VideoProviderType.AUTO,
            luma_model=api_config.luma_default_model,
            luma_resolution=api_config.luma_default_resolution,
            fallback_to_local=True,
            use_luma_for_key_scenes=use_for_key,
            use_luma_for_all=use_for_all,
            monthly_budget_usd=api_config.monthly_budget_usd or 100.0,
            auto_cost_saving=api_config.auto_cost_saving,
            key_scene_ratio=api_config.key_scene_ratio
        )


class LumaVideoAdapter:
    """
    Luma API 비디오 어댑터

    HybridVideoManager와 함께 작동하여:
    - 핵심 장면: Luma API 사용 (고품질)
    - 일반 장면: 로컬 모델 사용 (비용 절감)
    - 비용 최적화: 설정에 따라 자동 조절
    """

    def __init__(
        self,
        config: LumaAdapterConfig = None,
        luma_provider: LumaProvider = None
    ):
        # 설정 로드 (API config에서 자동)
        self.config = config or LumaAdapterConfig.from_api_config()
        self._luma_provider = luma_provider
        self._local_generator = None
        self.settings = get_settings()

        # 사용량 추적
        self._usage_log: List[Dict] = []

    @property
    def luma_provider(self) -> Optional[LumaProvider]:
        """Luma 프로바이더 (지연 초기화)"""
        if self._luma_provider is None:
            try:
                self._luma_provider = create_luma_provider()
                logger.info("Luma provider initialized")
            except ValueError as e:
                logger.warning(f"Luma provider not available: {e}")
        return self._luma_provider

    @property
    def is_luma_available(self) -> bool:
        """Luma 사용 가능 여부"""
        return self.luma_provider is not None

    @property
    def is_budget_exceeded(self) -> bool:
        """예산 초과 여부"""
        if self.config.monthly_budget_usd is None:
            return False
        return self.config.current_month_usage_usd >= self.config.monthly_budget_usd

    @property
    def usage_ratio(self) -> float:
        """예산 사용 비율"""
        if self.config.monthly_budget_usd is None or self.config.monthly_budget_usd == 0:
            return 0.0
        return self.config.current_month_usage_usd / self.config.monthly_budget_usd

    def _should_use_luma(self, is_key_scene: bool) -> bool:
        """Luma 사용 여부 결정"""
        # 예산 초과 시 자동 절감
        if self.is_budget_exceeded and self.config.auto_cost_saving:
            logger.info("Budget exceeded, falling back to local")
            return False

        # 모든 장면에 사용
        if self.config.use_luma_for_all:
            return True

        # 핵심 장면만 사용
        if self.config.use_luma_for_key_scenes and is_key_scene:
            return True

        return False

    async def generate_video(
        self,
        scene: Scene,
        image_path: str,
        output_path: str,
        is_key_scene: bool = False,
        audio_path: str = None,
    ) -> VideoSegment:
        """
        장면 비디오 생성

        Args:
            scene: 장면 엔티티
            image_path: 입력 이미지 경로
            output_path: 출력 경로
            is_key_scene: 핵심 장면 여부
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)

        Returns:
            VideoSegment
        """
        provider = self._select_provider(is_key_scene)

        # audio_path 검증 (립싱크 오디오)
        effective_audio_path = None
        if audio_path:
            if Path(audio_path).exists():
                effective_audio_path = audio_path
                logger.info(f"립싱크 오디오 활성화: {audio_path}")
            else:
                logger.warning(f"오디오 파일 없음, 오디오 없이 진행: {audio_path}")

        if provider == VideoProviderType.LUMA and self.is_luma_available:
            return await self._generate_with_luma(
                scene, image_path, output_path, audio_path=effective_audio_path
            )
        else:
            return await self._generate_with_local(
                scene, image_path, output_path, audio_path=effective_audio_path
            )

    def _select_provider(self, is_key_scene: bool) -> VideoProviderType:
        """프로바이더 선택"""
        # 설정이 AUTO가 아니면 설정 따름
        if self.config.default_provider != VideoProviderType.AUTO:
            return self.config.default_provider

        # Luma를 모든 장면에 사용
        if self.config.use_luma_for_all and self.is_luma_available:
            return VideoProviderType.LUMA

        # 핵심 장면만 Luma
        if self.config.use_luma_for_key_scenes and is_key_scene and self.is_luma_available:
            return VideoProviderType.LUMA

        # 나머지는 로컬
        return VideoProviderType.LOCAL

    async def _generate_with_luma(
        self,
        scene: Scene,
        image_path: str,
        output_path: str,
        audio_path: str = None,
    ) -> VideoSegment:
        """Luma로 생성 (audio_path: TTS 립싱크 오디오, 향후 구현 예정)"""
        segment = VideoSegment(
            id=f"luma_{scene.id}",
            scene_id=scene.id,
            image_path=image_path,
            duration=scene.duration or 5
        )

        try:
            # 프롬프트 준비
            prompt = getattr(scene, 'video_prompt', None) or scene.description

            # 요청 생성
            request = VideoGenerationRequest(
                image_path=image_path,
                prompt=prompt,
                model=self.config.luma_model,
                resolution=VideoResolution(self.config.luma_resolution),
                duration=int(scene.duration or 5)
            )

            # Luma 호출
            result = await self.luma_provider.generate_and_wait(
                request,
                timeout=300,
                poll_interval=10
            )

            if result.is_complete:
                # 다운로드
                await self.luma_provider.download(result, output_path)
                segment.video_path = output_path
                segment.metadata = {
                    "provider": "luma",
                    "model": self.config.luma_model,
                    "generation_id": result.id,
                    "credits_used": result.credits_used
                }
                segment.effects.append("luma_generated")
                logger.info(f"Luma video generated: {output_path}")
            else:
                raise RuntimeError(f"Luma generation failed: {result.error_message}")

        except Exception as e:
            logger.error(f"Luma generation error: {e}")
            segment.error = str(e)

            # 폴백
            if self.config.fallback_to_local:
                logger.info("Falling back to local generation")
                return await self._generate_with_local(scene, image_path, output_path, audio_path=audio_path)

        return segment

    async def _generate_with_local(
        self,
        scene: Scene,
        image_path: str,
        output_path: str,
        audio_path: str = None,
    ) -> VideoSegment:
        """로컬 모델로 생성 (FramePack/SVD, audio_path: TTS 립싱크 오디오)"""
        segment = VideoSegment(
            id=f"local_{scene.id}",
            scene_id=scene.id,
            image_path=image_path,
            duration=scene.duration or 5
        )

        try:
            # 로컬 생성기 지연 로드
            if self._local_generator is None:
                from infrastructure.video.svd_generator import SVDGenerator
                self._local_generator = SVDGenerator()

            # 로컬 생성
            await self._local_generator.generate_with_preset(
                image_path,
                output_path,
                preset=getattr(scene, 'motion_type', 'default'),
                audio_path=audio_path,
            )

            segment.video_path = output_path
            segment.metadata = {
                "provider": "local",
                "model": "svd"
            }
            segment.effects.append("local_generated")

        except Exception as e:
            logger.error(f"Local generation error: {e}")
            segment.error = str(e)
            # 로컬도 실패하면 Ken Burns 효과
            segment.effects.append("ken_burns_fallback")

        return segment

    async def generate_batch(
        self,
        scenes: List[Scene],
        image_paths: List[str],
        output_dir: str,
        key_scene_indices: List[int] = None,
        audio_paths: List[str] = None,
    ) -> List[VideoSegment]:
        """
        일괄 생성

        Args:
            scenes: 장면 목록
            image_paths: 이미지 경로 목록
            output_dir: 출력 디렉토리
            key_scene_indices: 핵심 장면 인덱스
            audio_paths: TTS 오디오 경로 목록 (립싱크용, None이면 오디오 없이 생성)

        Returns:
            VideoSegment 목록
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if key_scene_indices is None:
            # 자동 감지: 처음, 중간, 끝
            total = len(scenes)
            key_scene_indices = {0, total // 3, total * 2 // 3, total - 1}

        segments = []
        tasks = []

        for i, (scene, image_path) in enumerate(zip(scenes, image_paths)):
            output_path = f"{output_dir}/scene_{i:03d}.mp4"
            is_key = i in key_scene_indices
            audio = audio_paths[i] if audio_paths and i < len(audio_paths) else None

            task = self.generate_video(scene, image_path, output_path, is_key, audio_path=audio)
            tasks.append(task)

        # 병렬 실행 (Luma는 rate limit 고려해 순차)
        if self.config.use_luma_for_all:
            segments = []
            for task in tasks:
                seg = await task
                segments.append(seg)
                # Rate limit 대기
                await asyncio.sleep(2)
        else:
            segments = await asyncio.gather(*tasks)

        return segments

    def get_cost_estimate(
        self,
        scenes: List[Scene],
        key_scene_indices: List[int] = None
    ) -> Dict[str, Any]:
        """
        비용 추정

        Returns:
            예상 크레딧 및 USD
        """
        total = len(scenes)
        if key_scene_indices is None:
            key_count = min(4, total)
        else:
            key_count = len(key_scene_indices)

        local_count = total - key_count

        # 모델별 크레딧 계산
        credits_per_second = LumaProvider.CREDITS_PER_SECOND.get(
            self.config.luma_model, {}
        ).get(self.config.luma_resolution, 50)

        # 평균 영상 길이
        avg_duration = sum(s.duration or 5 for s in scenes) / total if scenes else 5

        luma_credits = key_count * credits_per_second * avg_duration

        # Luma Pro 플랜: $90/월 = 약 9000 크레딧 가정
        usd_per_credit = 0.01

        return {
            "total_scenes": total,
            "luma_scenes": key_count,
            "local_scenes": local_count,
            "estimated_credits": luma_credits,
            "estimated_usd": luma_credits * usd_per_credit,
            "breakdown": {
                "luma": {
                    "scenes": key_count,
                    "credits": luma_credits
                },
                "local": {
                    "scenes": local_count,
                    "credits": 0,
                    "note": "Free (local GPU)"
                }
            }
        }
