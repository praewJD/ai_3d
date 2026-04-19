# -*- coding: utf-8 -*-
"""
Video Validator - 영상 생성 후 검증

생성된 비디오의 무결성, 재생 가능 여부 검증
(오디오는 이미 합성되어 있으므로 비디오 파일만 검증)
"""
import asyncio
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    video_path: str
    video_duration: float  # 초
    has_audio: bool
    file_size_mb: float
    codec_video: str
    codec_audio: str
    resolution: tuple[int, int]  # (width, height)
    errors: list[str]
    warnings: list[str]

    def __str__(self):
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        return f"""
{status} Video Validation Result
────────────────────────────────
File: {self.video_path}
Size: {self.file_size_mb:.2f} MB
Duration: {self.video_duration:.2f}s
Resolution: {self.resolution[0]}x{self.resolution[1]}
Video: {self.codec_video} | Audio: {self.codec_audio or 'None'}
Errors: {len(self.errors)} | Warnings: {len(self.warnings)}
"""


class VideoValidator:
    """영상 생성 후 검증 (최종 비디오만)"""

    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe_path = ffprobe_path

    async def validate(
        self,
        video_path: str,
        min_duration: float = 1.0,
        max_size_mb: float = 500.0,
        require_audio: bool = True
    ) -> ValidationResult:
        """
        비디오 파일 검증 (오디오 이미 포함됨)

        Args:
            video_path: 비디오 파일 경로
            min_duration: 최소 길이 (초)
            max_size_mb: 최대 파일 크기 (MB)
            require_audio: 오디오 트랙 필수 여부

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        video_path = Path(video_path)

        # 1. 파일 존재 확인
        if not video_path.exists():
            return ValidationResult(
                is_valid=False,
                video_path=str(video_path),
                video_duration=0,
                has_audio=False,
                file_size_mb=0,
                codec_video="",
                codec_audio="",
                resolution=(0, 0),
                errors=[f"파일이 존재하지 않음: {video_path}"],
                warnings=[]
            )

        # 2. 파일 크기 확인
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        if file_size_mb == 0:
            errors.append("파일 크기가 0 bytes")
        elif file_size_mb > max_size_mb:
            warnings.append(f"파일 크기가 큼: {file_size_mb:.1f}MB > {max_size_mb}MB")

        # 3. ffprobe로 메타데이터 추출
        try:
            metadata = await self._probe_video(str(video_path))
        except Exception as e:
            errors.append(f"ffprobe 실패: {e}")
            return ValidationResult(
                is_valid=False,
                video_path=str(video_path),
                video_duration=0,
                has_audio=False,
                file_size_mb=file_size_mb,
                codec_video="",
                codec_audio="",
                resolution=(0, 0),
                errors=errors,
                warnings=warnings
            )

        video_duration = metadata.get("duration", 0)
        codec_video = metadata.get("video_codec", "")
        codec_audio = metadata.get("audio_codec", "")
        resolution = metadata.get("resolution", (0, 0))
        has_audio = bool(codec_audio)

        # 4. 최소 길이 확인
        if video_duration < min_duration:
            errors.append(f"비디오 길이가 너무 짧음: {video_duration:.2f}s < {min_duration}s")

        # 5. 오디오 트랙 확인
        if require_audio and not has_audio:
            errors.append("오디오 트랙이 없음")

        # 6. 코덱 확인
        if codec_video and codec_video not in ["h264", "hevc", "libx264"]:
            warnings.append(f"비디오 코덱: {codec_video} (H.264 권장)")
        if has_audio and codec_audio not in ["aac", "mp3"]:
            warnings.append(f"오디오 코덱: {codec_audio} (AAC 권장)")

        # 7. 해상도 확인 (세로 영상)
        if resolution[0] > 0 and resolution[1] > 0:
            if resolution[0] > resolution[1]:
                warnings.append(f"가로 영상: {resolution[0]}x{resolution[1]} (세로 영상 권장)")

        # 최종 결과
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            video_path=str(video_path),
            video_duration=video_duration,
            has_audio=has_audio,
            file_size_mb=file_size_mb,
            codec_video=codec_video,
            codec_audio=codec_audio,
            resolution=resolution,
            errors=errors,
            warnings=warnings
        )

    async def _probe_video(self, video_path: str) -> dict:
        """ffprobe로 비디오 메타데이터 추출"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"ffprobe error: {stderr.decode()}")

        data = json.loads(stdout.decode())

        # 메타데이터 추출
        result = {
            "duration": float(data.get("format", {}).get("duration", 0)),
            "video_codec": "",
            "audio_codec": "",
            "resolution": (0, 0)
        }

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                result["video_codec"] = stream.get("codec_name", "")
                result["resolution"] = (
                    stream.get("width", 0),
                    stream.get("height", 0)
                )
            elif stream.get("codec_type") == "audio":
                result["audio_codec"] = stream.get("codec_name", "")

        return result

    async def validate_batch(self, video_paths: list[str]) -> list[ValidationResult]:
        """여러 비디오 파일 일괄 검증"""
        results = []
        for video_path in video_paths:
            result = await self.validate(video_path)
            results.append(result)
        return results


# CLI 진입점
async def main():
    """CLI 테스트"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python video_validator.py <video_path>")
        print("Example: python video_validator.py output/video.mp4")
        return

    video_path = sys.argv[1]

    validator = VideoValidator()
    result = await validator.validate(video_path)
    print(result)

    if not result.is_valid:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
