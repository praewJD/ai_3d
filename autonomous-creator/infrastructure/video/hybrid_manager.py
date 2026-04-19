"""
Hybrid Video Manager

SVD + 이미지 시퀀스 하이브리드 영상 생성
+ Luma API 통합 (v2.1)
"""
from typing import List, Tuple, Optional
from pathlib import Path
import logging

from .svd_generator import SVDGenerator
from .moviepy_composer import MoviePyComposer
from .luma_adapter import LumaVideoAdapter, LumaAdapterConfig, VideoProviderType
from core.domain.entities.story import Scene
from core.domain.entities.video import VideoSegment
from config.settings import get_settings

logger = logging.getLogger(__name__)


class HybridVideoManager:
    """
    하이브리드 비디오 관리자

    전략 (v2.1):
    - 핵심 장면: Luma API 우선 (고품질)
    - 일반 장면: SVD 또는 Ken Burns
    - 폴백: Luma 실패 시 자동으로 로컬
    """

    def __init__(
        self,
        svd_generator: Optional[SVDGenerator] = None,
        composer: Optional[MoviePyComposer] = None,
        luma_adapter: Optional[LumaVideoAdapter] = None,
        use_luma: bool = True
    ):
        self.svd = svd_generator or SVDGenerator()
        self.composer = composer or MoviePyComposer()
        self._svd_available: Optional[bool] = None

        # [v2.1] Luma 어댑터
        self._luma_adapter = luma_adapter
        self._use_luma = use_luma
        self.settings = get_settings()

    @property
    def luma_adapter(self) -> Optional[LumaVideoAdapter]:
        """Luma 어댑터 (지연 초기화)"""
        if self._luma_adapter is None and self._use_luma:
            config = LumaAdapterConfig(
                default_provider=VideoProviderType.AUTO,
                use_luma_for_key_scenes=True,
                fallback_to_local=True
            )
            self._luma_adapter = LumaVideoAdapter(config)
        return self._luma_adapter

    async def is_svd_available(self) -> bool:
        """SVD 사용 가능 여부 캐싱"""
        if self._svd_available is None:
            self._svd_available = await self.svd.is_available()
        return self._svd_available

    async def classify_scenes(
        self,
        scenes: List[Scene]
    ) -> Tuple[List[Scene], List[Scene]]:
        """
        장면 분류: 핵심 vs 일반

        기준:
        - 처음, 중간, 끝 장면은 핵심
        - 전환점 장면은 핵심
        - 나머지는 일반
        """
        if len(scenes) <= 3:
            return scenes, []  # 모두 핵심

        total = len(scenes)
        key_indices = {0, total // 3, total * 2 // 3, total - 1}

        key_scenes = [s for i, s in enumerate(scenes) if i in key_indices]
        supporting_scenes = [s for i, s in enumerate(scenes) if i not in key_indices]

        return key_scenes, supporting_scenes

    async def generate_scene_video(
        self,
        scene: Scene,
        image_path: str,
        audio_path: str,
        output_dir: str,
        is_key_scene: bool,
        lipsync_audio_path: str = None,
    ) -> VideoSegment:
        """
        장면별 비디오 생성

        Args:
            scene: 장면 엔티티
            image_path: 입력 이미지 경로
            audio_path: 배경 오디오 경로 (BGM 등)
            output_dir: 출력 디렉토리
            is_key_scene: 핵심 장면 여부
            lipsync_audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)
        """

        segment = VideoSegment(
            id=f"seg_{scene.id}",
            scene_id=scene.id,
            image_path=image_path,
            audio_path=audio_path,
            duration=scene.duration,
            effects=["fade_in", "fade_out"]
        )

        # [v2.1] 핵심 장면은 Luma 우선 시도
        if is_key_scene and self.luma_adapter and self.luma_adapter.is_luma_available:
            video_path = f"{output_dir}/luma_{scene.id}.mp4"
            try:
                luma_segment = await self.luma_adapter.generate_video(
                    scene=scene,
                    image_path=image_path,
                    output_path=video_path,
                    is_key_scene=True
                )
                if luma_segment.video_path:
                    segment.video_path = luma_segment.video_path
                    segment.effects.append("luma_generated")
                    segment.metadata = luma_segment.metadata or {}
                    logger.info(f"Luma video generated for key scene: {scene.id}")
                    return segment
            except Exception as e:
                logger.warning(f"Luma failed for {scene.id}: {e}, falling back to SVD")

        # SVD 또는 Ken Burns
        if is_key_scene and await self.is_svd_available():
            # SVD로 비디오 생성
            video_path = f"{output_dir}/svd_{scene.id}.mp4"
            try:
                await self.svd.generate_with_preset(
                    image_path,
                    video_path,
                    preset=scene.motion_type,
                    audio_path=lipsync_audio_path,
                )
                segment.video_path = video_path
                segment.effects.append("svd_motion")
            except Exception as e:
                print(f"SVD failed for {scene.id}: {e}")
                # 실패 시 Ken Burns 사용
                segment.effects.append("ken_burns_zoom")
        else:
            # Ken Burns 효과
            segment.effects.append("ken_burns_zoom")

        return segment

    async def generate_all_segments(
        self,
        scenes: List[Scene],
        image_paths: List[str],
        audio_paths: List[str],
        output_dir: str,
        lipsync_audio_paths: List[str] = None,
    ) -> List[VideoSegment]:
        """
        모든 장면 비디오 생성

        Args:
            scenes: 장면 목록
            image_paths: 이미지 경로 목록
            audio_paths: 배경 오디오 경로 목록
            output_dir: 출력 디렉토리
            lipsync_audio_paths: TTS 오디오 경로 목록 (립싱크용, None이면 오디오 없이 생성)
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        key_scenes, _ = await self.classify_scenes(scenes)
        segments = []

        for i, (scene, image_path, audio_path) in enumerate(zip(scenes, image_paths, audio_paths)):
            is_key = scene in key_scenes
            # 립싱크 오디오 경로 (TTS)
            lipsync_audio = (
                lipsync_audio_paths[i]
                if lipsync_audio_paths and i < len(lipsync_audio_paths)
                else None
            )
            segment = await self.generate_scene_video(
                scene=scene,
                image_path=image_path,
                audio_path=audio_path,
                output_dir=output_dir,
                is_key_scene=is_key,
                lipsync_audio_path=lipsync_audio,
            )
            segments.append(segment)

        return segments

    async def create_final_video(
        self,
        segments: List[VideoSegment],
        output_path: str,
        audio_path: str = None,
    ):
        """
        최종 영상 합성

        Args:
            segments: 비디오 세그먼트 목록
            output_path: 출력 파일 경로
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 합성)
        """
        return await self.composer.compose(
            segments=segments,
            output_path=output_path,
            resolution=(1080, 1920),
            fps=30,
            audio_path=audio_path,
        )
