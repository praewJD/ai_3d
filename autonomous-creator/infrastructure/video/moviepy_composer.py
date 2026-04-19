"""
MoviePy Video Composer

이미지 + 오디오 → 영상 합성
"""
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    ColorClip
)
from moviepy.video.fx.all import fadein, fadeout, resize

from core.domain.interfaces.video_composer import IVideoComposer
from core.domain.entities.video import Video, VideoSegment
from config.settings import get_settings

logger = logging.getLogger(__name__)


class MoviePyComposer(IVideoComposer):
    """
    MoviePy 기반 영상 합성기

    - 이미지 시퀀스 → 영상
    - 오디오 추가
    - 전환 효과
    - Ken Burns 효과
    """

    def __init__(
        self,
        resolution: Tuple[int, int] = (1080, 1920),
        fps: int = 30
    ):
        settings = get_settings()
        self.resolution = resolution
        self.fps = fps

    async def compose(
        self,
        segments: List[VideoSegment],
        output_path: str,
        resolution: Tuple[int, int] = (1080, 1920),
        fps: int = 30,
        audio_path: str = None,
    ) -> Video:
        """
        세그먼트들을 영상으로 합성

        Args:
            segments: 비디오 세그먼트 목록
            output_path: 출력 파일 경로
            resolution: 해상도
            fps: 프레임 레이트
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 합성)

        Returns:
            생성된 Video 객체
        """
        # audio_path 검증 (립싱크 오디오)
        effective_audio_path = None
        if audio_path:
            if Path(audio_path).exists():
                effective_audio_path = audio_path
                logger.info(f"립싱크 오디오 활성화: {audio_path}")
            else:
                logger.warning(f"오디오 파일 없음, 오디오 없이 진행: {audio_path}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        clips = []
        total_duration = 0.0

        for seg in segments:
            # 비디오 클립 생성
            if seg.video_path and Path(seg.video_path).exists():
                # SVD 비디오
                clip = self._load_video_clip(seg)
            elif seg.image_path and Path(seg.image_path).exists():
                # 이미지 + Ken Burns
                clip = await self._create_image_clip(seg, resolution)
            else:
                continue

            # 오디오 추가
            if seg.audio_path and Path(seg.audio_path).exists():
                audio = AudioFileClip(seg.audio_path)
                clip = clip.set_audio(audio)

            # 이펙트 적용
            clip = self._apply_effects(clip, seg.effects)

            clips.append(clip)
            total_duration += seg.duration

        # 전체 영상 합성
        if clips:
            final_video = concatenate_videoclips(clips, method="compose")
        else:
            # 빈 영상 생성
            final_video = ColorClip(
                size=resolution,
                color=(0, 0, 0),
                duration=1.0
            )

        # 전체 페이드 인/아웃
        final_video = final_video.fadein(0.5).fadeout(0.5)

        # 렌더링
        final_video.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
            bitrate="8000k"
        )

        # 리소스 정리
        final_video.close()
        for clip in clips:
            clip.close()

        return Video(
            story_id=segments[0].scene_id if segments else "",
            segments=segments,
            output_path=output_path,
            duration=total_duration,
            resolution=resolution,
            fps=fps,
            created_at=datetime.now()
        )

    def _load_video_clip(self, segment: VideoSegment) -> "VideoClip":
        """비디오 파일 로드"""
        from moviepy.editor import VideoFileClip

        clip = VideoFileClip(segment.video_path)
        clip = clip.resize(self.resolution)
        clip = clip.set_duration(segment.duration)
        return clip

    async def _create_image_clip(
        self,
        segment: VideoSegment,
        resolution: Tuple[int, int]
    ) -> "ImageClip":
        """이미지로 비디오 클립 생성 (Ken Burns 효과)"""
        clip = ImageClip(segment.image_path)
        clip = clip.set_duration(segment.duration)

        # Ken Burns 효과
        if "ken_burns_zoom" in segment.effects:
            clip = self._apply_ken_burns_zoom(clip, resolution)
        elif "ken_burns_pan" in segment.effects:
            # 팬 방향 추출 (기본: left_to_right)
            pan_direction = "left_to_right"
            for effect in segment.effects:
                if effect.startswith("ken_burns_pan:"):
                    pan_direction = effect.split(":")[1]
                    break
            clip = self._apply_ken_burns_pan(clip, resolution, pan_direction)
        else:
            # 기본 리사이즈
            clip = clip.resize(resolution)

        return clip

    def _apply_ken_burns_zoom(
        self,
        clip: "ImageClip",
        resolution: Tuple[int, int],
        zoom_direction: str = "in"
    ) -> "ImageClip":
        """Ken Burns 줌 효과"""
        w, h = resolution

        def zoom_effect(get_frame, t):
            frame = get_frame(t)
            duration = clip.duration
            progress = t / duration

            if zoom_direction == "in":
                scale = 1.0 + 0.1 * progress  # 1.0 → 1.1
            else:
                scale = 1.1 - 0.1 * progress  # 1.1 → 1.0

            # 중앙 기준 크롭
            fh, fw = frame.shape[:2]
            new_h = int(fh / scale)
            new_w = int(fw / scale)
            y = (fh - new_h) // 2
            x = (fw - new_w) // 2

            cropped = frame[y:y+new_h, x:x+new_w]
            # 리사이즈는 별도 처리 필요
            return cropped

        return clip.resize((int(w*1.1), int(h*1.1))).fl(zoom_effect)

    def _apply_ken_burns_pan(
        self,
        clip: "ImageClip",
        resolution: Tuple[int, int],
        direction: str = "left_to_right"
    ) -> "ImageClip":
        """
        Ken Burns 팬 효과

        Args:
            clip: 이미지 클립
            resolution: 출력 해상도
            direction: 팬 방향
                - "left_to_right": 좌→우 (기본)
                - "right_to_left": 우→좌
                - "top_to_bottom": 상→하
                - "bottom_to_top": 하→상
        """
        w, h = resolution
        pan_range = 0.1  # 10% 이동

        if direction in ["left_to_right", "right_to_left"]:
            # 가로 팬: 넓게 리사이즈
            clip = clip.resize((int(w * (1 + pan_range)), h))

            def pan_effect(get_frame, t):
                frame = get_frame(t)
                progress = t / clip.duration

                if direction == "left_to_right":
                    offset = int(w * pan_range * progress)
                else:  # right_to_left
                    offset = int(w * pan_range * (1 - progress))

                return frame[:, offset:offset+w]

        elif direction in ["top_to_bottom", "bottom_to_top"]:
            # 세로 팬: 높게 리사이즈
            clip = clip.resize((w, int(h * (1 + pan_range))))

            def pan_effect(get_frame, t):
                frame = get_frame(t)
                progress = t / clip.duration

                if direction == "top_to_bottom":
                    offset = int(h * pan_range * progress)
                else:  # bottom_to_top
                    offset = int(h * pan_range * (1 - progress))

                return frame[offset:offset+h, :]

        else:
            # 기본: 좌→우
            clip = clip.resize((int(w * (1 + pan_range)), h))

            def pan_effect(get_frame, t):
                frame = get_frame(t)
                progress = t / clip.duration
                offset = int(w * pan_range * progress)
                return frame[:, offset:offset+w]

        return clip.fl(pan_effect)

    def _apply_effects(
        self,
        clip,
        effects: List[str]
    ):
        """이펙트 적용"""
        if "fade_in" in effects:
            clip = clip.fadein(0.3)
        if "fade_out" in effects:
            clip = clip.fadeout(0.3)
        if "color_enhance" in effects:
            # 색상 강조: 채도 +20%, 대비 +10%
            clip = self._apply_color_enhance(clip)
        return clip

    def _apply_color_enhance(self, clip) -> "ImageClip":
        """색상 강조 효과 (채도/대비 향상)"""
        import numpy as np

        def enhance_color(get_frame, t):
            frame = get_frame(t).copy()

            # RGB를 float로 변환
            rgb = frame.astype(np.float32) / 255.0

            # 채도 향상 (간단한 방식: 중간값에서 멀어지게)
            gray = np.mean(rgb, axis=2, keepdims=True)
            saturation_factor = 1.2  # +20%
            rgb = gray + (rgb - gray) * saturation_factor

            # 대비 향상 (+10%)
            contrast_factor = 1.1
            rgb = (rgb - 0.5) * contrast_factor + 0.5

            # 클립 및 정규화
            rgb = np.clip(rgb, 0, 1)
            return (rgb * 255).astype(np.uint8)

        return clip.fl(enhance_color)

    async def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        """영상에 오디오 추가"""
        from moviepy.editor import VideoFileClip

        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)

        # 오디오 길이를 비디오에 맞춤
        if audio.duration > video.duration:
            audio = audio.subclip(0, video.duration)
        elif audio.duration < video.duration:
            # 오디오 루프 또는 무음
            audio = audio.set_duration(video.duration)

        final = video.set_audio(audio)
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac"
        )

        video.close()
        audio.close()
        final.close()

        return output_path

    async def apply_ken_burns(
        self,
        image_path: str,
        duration: float,
        output_path: str,
        zoom_direction: str = "in"
    ) -> str:
        """Ken Burns 효과로 이미지 → 비디오"""
        clip = ImageClip(image_path).set_duration(duration)
        clip = self._apply_ken_burns_zoom(clip, self.resolution, zoom_direction)

        clip.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264"
        )
        clip.close()

        return output_path

    async def concatenate(
        self,
        video_paths: List[str],
        output_path: str,
        transition: Optional[str] = None
    ) -> str:
        """여러 영상 연결"""
        from moviepy.editor import VideoFileClip

        clips = [VideoFileClip(p) for p in video_paths]

        if transition == "crossfade":
            # 크로스페이드 트랜지션
            final = concatenate_videoclips(
                [c.crossfadein(0.5) for c in clips],
                method="compose"
            )
        elif transition == "fade":
            # 페이드 트랜지션
            final = concatenate_videoclips(
                [c.fadein(0.3).fadeout(0.3) for c in clips],
                method="compose"
            )
        else:
            final = concatenate_videoclips(clips, method="compose")

        final.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac"
        )

        for c in clips:
            c.close()
        final.close()

        return output_path
