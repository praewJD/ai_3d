"""
VideoComposer - 영상 합성

MoviePy 기반 영상/오디오 합성
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# MoviePy imports (지연 import로 처리)
_executor = ThreadPoolExecutor(max_workers=2)


@dataclass
class SceneClip:
    """장면 클립 정보"""
    scene_id: str
    video_path: Path
    audio_path: Optional[Path] = None
    duration: float = 5.0
    transition_in: str = "fade"
    transition_out: str = "fade"


@dataclass
class CompositionResult:
    """합성 결과"""
    success: bool
    output_path: Optional[Path] = None
    total_duration: float = 0.0
    scene_count: int = 0
    composition_time_ms: int = 0
    error_message: str = ""


class VideoComposer:
    """
    영상 합성기

    - 여러 영상 클립 연결
    - 오디오 추가
    - 전환 효과
    - BGM 믹싱
    """

    def __init__(
        self,
        output_dir: str = "outputs/final",
        fps: int = 30,
        resolution: tuple = (1920, 1080)
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.resolution = resolution

    async def compose(
        self,
        clips: List[SceneClip],
        bgm_path: Path = None,
        title: str = "",
        output_filename: str = None
    ) -> CompositionResult:
        """
        전체 영상 합성

        Args:
            clips: 장면 클립 목록
            bgm_path: BGM 파일 경로
            title: 제목
            output_filename: 출력 파일명

        Returns:
            CompositionResult
        """
        start_time = datetime.now()

        try:
            # MoviePy import
            from moviepy.editor import (
                VideoFileClip, AudioFileClip, CompositeVideoClip,
                concatenate_videoclips, ColorClip
            )

            if not clips:
                return CompositionResult(
                    success=False,
                    error_message="No clips to compose"
                )

            # 출력 파일명
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"final_{timestamp}.mp4"

            output_path = self.output_dir / output_filename

            # 1. 비디오 클립 로드
            logger.info(f"Loading {len(clips)} video clips...")
            video_clips = []

            for clip_info in clips:
                if not clip_info.video_path.exists():
                    logger.warning(f"Video not found: {clip_info.video_path}")
                    continue

                video_clip = VideoFileClip(str(clip_info.video_path))

                # 오디오가 있으면 교체
                if clip_info.audio_path and clip_info.audio_path.exists():
                    audio_clip = AudioFileClip(str(clip_info.audio_path))
                    video_clip = video_clip.set_audio(audio_clip)

                # 전환 효과
                video_clip = self._apply_transition(
                    video_clip,
                    clip_info.transition_in,
                    clip_info.transition_out
                )

                video_clips.append(video_clip)

            if not video_clips:
                return CompositionResult(
                    success=False,
                    error_message="No valid video clips"
                )

            # 2. 클립 연결
            logger.info("Concatenating clips...")
            final_video = concatenate_videoclips(video_clips, method="compose")

            # 3. BGM 추가
            if bgm_path and bgm_path.exists():
                logger.info(f"Adding BGM: {bgm_path}")
                final_video = self._add_bgm(final_video, bgm_path, volume=0.3)

            # 4. 렌더링
            logger.info(f"Rendering to {output_path}...")

            def render():
                final_video.write_videofile(
                    str(output_path),
                    fps=self.fps,
                    codec='libx264',
                    audio_codec='aac',
                    threads=4,
                    preset='medium',
                    bitrate='8000k'
                )

            # 별도 스레드에서 렌더링
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_executor, render)

            # 정리
            for clip in video_clips:
                clip.close()
            final_video.close()

            # 결과
            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Composition complete: {output_path}")

            return CompositionResult(
                success=True,
                output_path=output_path,
                total_duration=final_video.duration if hasattr(final_video, 'duration') else 0,
                scene_count=len(video_clips),
                composition_time_ms=int(elapsed)
            )

        except Exception as e:
            logger.exception("Composition failed")
            return CompositionResult(
                success=False,
                error_message=str(e)
            )

    def _apply_transition(
        self,
        clip,
        transition_in: str,
        transition_out: str,
        duration: float = 0.5
    ):
        """전환 효과 적용"""
        try:
            from moviepy.editor import vfx

            # Fade in
            if transition_in == "fade":
                clip = clip.fadein(duration)

            # Fade out
            if transition_out == "fade":
                clip = clip.fadeout(duration)

            return clip

        except Exception as e:
            logger.warning(f"Transition failed: {e}")
            return clip

    def _add_bgm(
        self,
        video,
        bgm_path: Path,
        volume: float = 0.3
    ):
        """BGM 추가"""
        try:
            from moviepy.editor import AudioFileClip, CompositeAudioClip

            bgm = AudioFileClip(str(bgm_path))

            # 루프 처리
            if bgm.duration < video.duration:
                bgm = bgm.loop(duration=video.duration)
            else:
                bgm = bgm.subclip(0, video.duration)

            # 볼륨 조절
            bgm = bgm.volumex(volume)

            # 기존 오디오와 믹싱
            if video.audio:
                final_audio = CompositeAudioClip([video.audio, bgm])
            else:
                final_audio = bgm

            return video.set_audio(final_audio)

        except Exception as e:
            logger.warning(f"BGM addition failed: {e}")
            return video

    async def create_preview(
        self,
        clips: List[SceneClip],
        max_duration: float = 30.0
    ) -> CompositionResult:
        """
        미리보기 영상 생성

        Args:
            clips: 장면 클립 목록
            max_duration: 최대 길이

        Returns:
            CompositionResult
        """
        # 각 클립을 max_duration/len(clips)로 제한
        duration_per_clip = max_duration / len(clips) if clips else max_duration

        preview_clips = []
        for clip in clips:
            preview_clip = SceneClip(
                scene_id=clip.scene_id,
                video_path=clip.video_path,
                audio_path=clip.audio_path,
                duration=min(clip.duration, duration_per_clip),
                transition_in=clip.transition_in,
                transition_out=clip.transition_out
            )
            preview_clips.append(preview_clip)

        return await self.compose(
            preview_clips,
            output_filename="preview.mp4"
        )

    async def add_subtitles(
        self,
        video_path: Path,
        subtitles: List[Dict[str, Any]],
        output_path: Path = None
    ) -> CompositionResult:
        """
        자막 추가

        Args:
            video_path: 비디오 경로
            subtitles: 자막 목록 [{start, end, text}]
            output_path: 출력 경로

        Returns:
            CompositionResult
        """
        try:
            from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

            video = VideoFileClip(str(video_path))
            txt_clips = []

            for sub in subtitles:
                txt = TextClip(
                    sub["text"],
                    fontsize=24,
                    color='white',
                    font='Arial'
                )
                txt = txt.set_position(('center', 'bottom'))
                txt = txt.set_start(sub["start"])
                txt = txt.set_duration(sub["end"] - sub["start"])
                txt_clips.append(txt)

            result = CompositeVideoClip([video] + txt_clips)

            output = output_path or video_path.with_name(
                video_path.stem + "_subtitled.mp4"
            )

            result.write_videofile(
                str(output),
                fps=self.fps,
                codec='libx264'
            )

            return CompositionResult(
                success=True,
                output_path=output
            )

        except Exception as e:
            return CompositionResult(
                success=False,
                error_message=str(e)
            )


# 싱글톤
_composer: Optional[VideoComposer] = None


def get_video_composer() -> VideoComposer:
    """영상 합성기 싱글톤"""
    global _composer
    if _composer is None:
        _composer = VideoComposer()
    return _composer
