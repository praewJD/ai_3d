"""
F5-TTS-THAI Engine

태국어 TTS를 위한 F5-TTS-THAI 엔진
- Zero-shot voice cloning 지원
- 고품질 Thai 음성 생성
- f5-tts-th 패키지 사용
"""
import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

# UTF-8 강제 설정 (Windows 대응)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from .base import BaseTTSEngine
from core.domain.entities.audio import VoiceSettings, VoiceGender

logger = logging.getLogger(__name__)

# f5-tts-th 사용 가능 여부 체크
F5_TTS_TH_AVAILABLE = False
try:
    from f5_tts_th.tts import TTS
    F5_TTS_TH_AVAILABLE = True
except ImportError:
    pass


class F5TTSThaiEngine(BaseTTSEngine):
    """
    F5-TTS-THAI 엔진

    특징:
    - Zero-shot voice cloning
    - Thai + English 지원
    - 고품질 자연스러운 음성
    """

    # 기본 reference audio 경로
    DEFAULT_REFERENCE_AUDIO = Path(r"C:\Users\JN\narration_th.flac")
    DEFAULT_REFERENCE_TEXT = "สวัสดีค่ะ ยินดีที่ได้รู้จักทุกท่านนะคะ"

    # 태국어 음성 프리셋
    VOICE_PRESETS = {
        "female_standard": {
            "description": "표준 여성 목소리",
            "speed": 1.0,
        },
        "female_slow": {
            "description": "천천히 말하는 여성 목소리",
            "speed": 0.8,
        },
        "female_fast": {
            "description": "빠르게 말하는 여성 목소리",
            "speed": 1.2,
        },
    }

    def __init__(
        self,
        reference_audio_path: Optional[str] = None,
        reference_text: Optional[str] = None,
    ):
        """
        Args:
            reference_audio_path: 커스텀 reference audio 경로
            reference_text: reference audio 텍스트
        """
        super().__init__()

        self.reference_audio_path = reference_audio_path or str(self.DEFAULT_REFERENCE_AUDIO)
        self.reference_text = reference_text or self.DEFAULT_REFERENCE_TEXT

        # 모델 인스턴스 (지연 로딩)
        self._tts_model = None

        if not F5_TTS_TH_AVAILABLE:
            logger.warning(
                "f5-tts-th not installed. "
                "Run: pip install f5-tts-th"
            )

    def _get_tts_model(self):
        """모델 지연 로딩"""
        if self._tts_model is None:
            if not F5_TTS_TH_AVAILABLE:
                raise ImportError(
                    "f5-tts-th not installed. "
                    "Run: pip install f5-tts-th"
                )
            logger.info("Loading F5-TTS-THAI model...")
            self._tts_model = TTS(model="v1")
            logger.info("F5-TTS-THAI model loaded!")
        return self._tts_model

    def _get_reference_audio(self, voice: VoiceSettings) -> str:
        """Reference audio 경로 결정"""
        # 1. VoiceSettings에 지정된 reference
        if voice.reference_audio and os.path.exists(voice.reference_audio):
            return voice.reference_audio

        # 2. 기본 reference
        if os.path.exists(self.reference_audio_path):
            return self.reference_audio_path

        # 3. 기본 reference 없으면 에러
        raise FileNotFoundError(
            f"Reference audio not found. "
            f"Please provide a reference audio file. "
            f"Expected: {self.reference_audio_path}"
        )

    def _get_reference_text(self, voice: VoiceSettings) -> str:
        """Reference text 결정"""
        # 1. VoiceSettings에 지정된 text
        if voice.reference_text:
            return voice.reference_text

        # 2. 기본 reference text
        return self.reference_text

    async def _generate_audio(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """F5-TTS-THAI로 오디오 생성"""

        # 모델 로드
        tts = self._get_tts_model()

        # Reference audio 결정
        ref_audio = self._get_reference_audio(voice)
        ref_text = self._get_reference_text(voice)

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 속도 설정
        speed = voice.speed if voice.speed else 1.0

        logger.info(f"Generating Thai TTS...")
        logger.info(f"  Reference: {ref_audio}")
        logger.info(f"  Text length: {len(text)} chars")
        logger.info(f"  Speed: {speed}")

        try:
            # F5-TTS-TH inference (동기 → 비동기 래핑)
            loop = asyncio.get_event_loop()
            wav = await loop.run_in_executor(
                None,
                lambda: tts.infer(
                    ref_audio=ref_audio,
                    ref_text=ref_text,
                    gen_text=text,
                    step=32,
                    cfg=2.0,
                    speed=speed
                )
            )

            # 저장
            import soundfile as sf
            sf.write(output_path, wav, 24000)

            logger.info(f"Generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"F5-TTS-THAI generation failed: {e}")
            raise RuntimeError(f"F5-TTS-THAI generation failed: {e}")

    def supports_language(self, language: str) -> bool:
        """Thai + English 지원"""
        return language.lower() in ["th", "thai", "en", "english"]

    def get_engine_name(self) -> str:
        return "F5-TTS-THAI"

    async def get_available_voices(self, language: str) -> List[dict]:
        """사용 가능한 음성 목록"""
        voices = []
        for preset_id, preset_info in self.VOICE_PRESETS.items():
            voices.append({
                "id": preset_id,
                "name": preset_info["description"],
                "gender": "female" if "female" in preset_id else "male",
                "language": "th",
                "speed": preset_info["speed"]
            })
        return voices

    @staticmethod
    def check_dependencies() -> dict:
        """의존성 체크"""
        results = {
            "f5_tts_th_installed": F5_TTS_TH_AVAILABLE,
            "torch_available": False,
            "cuda_available": False,
            "reference_audio_exists": False,
        }

        # PyTorch 확인
        try:
            import torch
            results["torch_available"] = True
            results["cuda_available"] = torch.cuda.is_available()
        except ImportError:
            pass

        # Reference audio 확인
        results["reference_audio_exists"] = F5TTSThaiEngine.DEFAULT_REFERENCE_AUDIO.exists()

        return results

    @staticmethod
    def get_installation_instructions() -> str:
        """설치 가이드"""
        return """
# F5-TTS-THAI 설치 가이드

## 1. f5-tts-th 패키지 설치
pip install f5-tts-th

## 2. PyTorch (CUDA) - 이미 설치되어 있다면 생략
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

## 3. Reference Audio 준비
- 2~8초 길이의 깨끗한 태국어 음성 파일
- 배경 소음이 없는 고품질 녹음
- 기본 경로: C:\\Users\\JN\\narration_th.flac

## 4. 테스트
python -c "from f5_tts_th.tts import TTS; print('OK')"
"""
