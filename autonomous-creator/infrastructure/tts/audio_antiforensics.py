"""
Audio Anti-Forensics Module

오디오 포렌식 방지를 위한 후처리 모듈
- AI 생성 오디오의 특성을 자연스럽게 변조
- 디지털 포렌식 도구의 탐지를 어렵게 만듦
"""
import numpy as np
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AudioAntiForensics:
    """
    오디오 포렌식 방지 처리기

    적용 기법:
    1. 미세 노이즈 추가 (Gaussian + Pink noise)
    2. 주파수 필터링 (High-pass + Low-pass)
    3. 리샘플링 (44100 → 48000 → 44100)
    4. 미세 피치 변조 (±0.1~0.3 semitone)
    5. 리버브 추가 (미세)
    6. Lossy 인코딩 통과 (MP3 320kbps)
    7. 비트 깊이 노이즈 (dithering)
    """

    def __init__(
        self,
        noise_level: float = 0.002,
        pitch_shift_range: Tuple[float, float] = (-0.2, 0.2),
        reverb_mix: float = 0.05,
        enable_resampling: bool = True,
        enable_lossy_pass: bool = True
    ):
        """
        Args:
            noise_level: 노이즈 강도 (0.0~0.01)
            pitch_shift_range: 피치 변조 범위 (semitone)
            reverb_mix: 리버브 믹스 비율 (0.0~0.1)
            enable_resampling: 리샘플링 적용 여부
            enable_lossy_pass: Lossy 인코딩 통과 여부
        """
        self.noise_level = noise_level
        self.pitch_shift_range = pitch_shift_range
        self.reverb_mix = reverb_mix
        self.enable_resampling = enable_resampling
        self.enable_lossy_pass = enable_lossy_pass

        # 랜덤 시드 (매 실행마다 다른 결과)
        self.rng = np.random.default_rng()

    def process(self, audio_path: str, output_path: Optional[str] = None) -> str:
        """
        오디오 파일에 포렌식 방지 처리 적용

        Args:
            audio_path: 입력 오디오 파일 경로
            output_path: 출력 파일 경로 (None이면 덮어쓰기)

        Returns:
            처리된 파일 경로
        """
        output_path = output_path or audio_path

        try:
            # FFmpeg를 사용한 파이프라인 처리
            return self._process_with_ffmpeg(audio_path, output_path)
        except Exception as e:
            logger.warning(f"FFmpeg processing failed, falling back to basic: {e}")
            return self._process_basic(audio_path, output_path)

    def _process_with_ffmpeg(self, input_path: str, output_path: str) -> str:
        """FFmpeg를 사용한 고급 포렌식 방지 처리"""

        # 랜덤 파라미터 생성
        pitch_shift = self.rng.uniform(*self.pitch_shift_range)
        noise_amp = self.noise_level * self.rng.uniform(0.8, 1.2)

        # 임시 파일 경로
        temp_dir = tempfile.gettempdir()
        temp1 = os.path.join(temp_dir, f"antiforensics_1_{os.getpid()}.wav")
        temp2 = os.path.join(temp_dir, f"antiforensics_2_{os.getpid()}.wav")
        temp3 = os.path.join(temp_dir, f"antiforensics_3_{os.getpid()}.mp3")

        try:
            # Step 1: 리샘플링 + 비트 깊이 변화
            if self.enable_resampling:
                # 44100 → 48000 → 44100 (리샘플링 아티팩트)
                cmd1 = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', '48000',
                    '-acodec', 'pcm_s16le',
                    temp1
                ]
                subprocess.run(cmd1, capture_output=True, check=True)

                cmd2 = [
                    'ffmpeg', '-y', '-i', temp1,
                    '-ar', '44100',
                    '-af', f'rubberband=pitch={2**(pitch_shift/12):.6f}',
                    '-acodec', 'pcm_s16le',
                    temp2
                ]
                subprocess.run(cmd2, capture_output=True, check=True)
            else:
                temp2 = input_path

            # Step 2: 노이즈 추가 + 필터링 + 리버브
            filter_complex = [
                # Pink noise 생성 및 믹싱
                f"anoisesrc=d=3600:c=pink:r=44100:a={noise_amp}[noise]",
                f"[0:a][noise]amix=inputs=2:duration_first:dropout_transition=0[a1]",
                # High-pass + Low-pass 필터
                f"[a1]highpass=f=80[a2]",
                f"[a2]lowpass=f=15000[a3]",
                # 미세 리버브
                f"[a3]aecho=0.8:0.9:1000:0.3[a4]",
                f"[a4]volume=1.2"
            ]

            intermediate = temp2

            # Step 3: Lossy 인코딩 통과 (MP3)
            if self.enable_lossy_pass:
                # MP3 320kbps로 인코딩 후 다시 WAV로
                cmd_mp3 = [
                    'ffmpeg', '-y', '-i', temp2,
                    '-codec:a', 'libmp3lame', '-b:a', '320k',
                    temp3
                ]
                subprocess.run(cmd_mp3, capture_output=True, check=True)
                intermediate = temp3

            # 최종 변환
            final_cmd = [
                'ffmpeg', '-y', '-i', intermediate,
                '-ar', '44100',
                '-acodec', 'pcm_s16le',
                output_path
            ]
            subprocess.run(final_cmd, capture_output=True, check=True)

            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            raise
        finally:
            # 임시 파일 정리
            for temp_file in [temp1, temp2, temp3]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass

    def _process_basic(self, input_path: str, output_path: str) -> str:
        """기본 처리 (FFmpeg 실패 시 폴백)"""
        try:
            import soundfile as sf
            import scipy.signal as signal

            # 오디오 로드
            audio, sr = sf.read(input_path)

            # Step 1: 노이즈 추가
            noise = self.rng.normal(0, self.noise_level, audio.shape)
            audio = audio + noise.astype(audio.dtype)

            # Step 2: High-pass / Low-pass 필터
            nyquist = sr / 2
            low_cutoff = 80 / nyquist
            high_cutoff = 15000 / nyquist

            b, a = signal.butter(2, [low_cutoff, high_cutoff], btype='band')
            audio = signal.filtfilt(b, a, audio)

            # Step 3: 정규화
            audio = np.clip(audio, -1.0, 1.0)

            # 저장
            sf.write(output_path, audio, sr)
            return output_path

        except ImportError:
            logger.warning("soundfile/scipy not available, returning original")
            return input_path


class StealthAudioProcessor:
    """
    스텔스 오디오 프로세서

    F5-TTS-THAI 생성 오디오를 자연스럽게 변조
    """

    # 탐지 회피 강도별 프리셋
    PRESETS = {
        "light": {
            "noise_level": 0.001,
            "pitch_shift_range": (-0.1, 0.1),
            "reverb_mix": 0.02,
            "enable_resampling": False,
            "enable_lossy_pass": False,
        },
        "medium": {
            "noise_level": 0.002,
            "pitch_shift_range": (-0.2, 0.2),
            "reverb_mix": 0.05,
            "enable_resampling": True,
            "enable_lossy_pass": False,
        },
        "heavy": {
            "noise_level": 0.003,
            "pitch_shift_range": (-0.3, 0.3),
            "reverb_mix": 0.08,
            "enable_resampling": True,
            "enable_lossy_pass": True,
        },
    }

    def __init__(self, preset: str = "medium"):
        """
        Args:
            preset: 프리셋 이름 (light, medium, heavy)
        """
        config = self.PRESETS.get(preset, self.PRESETS["medium"])
        self.processor = AudioAntiForensics(**config)

    def process(self, audio_path: str, output_path: Optional[str] = None) -> str:
        """오디오 포렌식 방지 처리"""
        return self.processor.process(audio_path, output_path)

    @staticmethod
    def check_ffmpeg_available() -> bool:
        """FFmpeg 사용 가능 여부 확인"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
