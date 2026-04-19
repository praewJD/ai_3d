"""
Azure TTS Engine

태국어 및 기타 언어용 Azure Cognitive Services TTS
"""
import asyncio
from typing import List, Optional
from pathlib import Path

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

from .base import BaseTTSEngine
from core.domain.entities.audio import VoiceSettings, VoiceGender
from config.settings import get_settings


class AzureTTSEngine(BaseTTSEngine):
    """
    Azure Cognitive Services TTS 엔진

    - 태국어 고품질 지원
    - Neural Voice 사용
    - SSML 지원
    """

    # Azure 음성 매핑
    VOICE_MAP = {
        "th": {
            "female": "th-TH-PremwadeeNeural",
            "male": "th-TH-NiwatNeural",
        },
        "en": {
            "female": "en-US-JennyNeural",
            "male": "en-US-GuyNeural",
        },
        "ko": {
            "female": "ko-KR-SunHiNeural",
            "male": "ko-KR-InJoonNeural",
        },
        "ja": {
            "female": "ja-JP-NanamiNeural",
            "male": "ja-JP-KeitaNeural",
        },
        "zh": {
            "female": "zh-CN-XiaoxiaoNeural",
            "male": "zh-CN-YunxiNeural",
        },
    }

    def __init__(
        self,
        subscription_key: Optional[str] = None,
        region: str = "southeastasia"
    ):
        super().__init__()
        settings = get_settings()

        self.subscription_key = subscription_key or settings.azure_tts_key
        self.region = region or settings.azure_tts_region

        if not self.subscription_key:
            raise ValueError("Azure TTS subscription key required")

        if not AZURE_AVAILABLE:
            raise ImportError("azure-cognitiveservices-speech not installed")

        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key,
            region=self.region
        )

    async def _generate_audio(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """Azure TTS로 오디오 생성"""

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 음성 선택
        voice_name = self._get_voice_name(voice)
        self.speech_config.speech_synthesis_voice_name = voice_name

        # 오디오 출력 설정
        audio_config = speechsdk.audio.AudioOutputConfig(
            filename=output_path
        )

        # SSML 생성 (속도 조절)
        ssml = self._build_ssml(text, voice)

        # 동기 API를 비동기로 래핑
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )

        # 비동기 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: synthesizer.speak_ssml_async(ssml).get()
        )

        # 결과 확인
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return output_path
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            raise RuntimeError(
                f"Azure TTS cancelled: {cancellation.reason} - {cancellation.error_details}"
            )
        else:
            raise RuntimeError(f"Azure TTS failed: {result.reason}")

    def _get_voice_name(self, voice: VoiceSettings) -> str:
        """음성 이름 결정"""
        # 사용자 지정 음성이 있으면 사용
        if voice.voice_name:
            return voice.voice_name

        # 언어/성별 기본 음성
        lang_voices = self.VOICE_MAP.get(voice.language, {})
        gender_key = voice.gender.value if voice.gender else "female"

        return lang_voices.get(gender_key, "en-US-JennyNeural")

    def _build_ssml(self, text: str, voice: VoiceSettings) -> str:
        """SSML 생성"""
        voice_name = self._get_voice_name(voice)

        # 속도/피치 변환
        rate = self._convert_speed(voice.speed)
        pitch = self._convert_pitch(voice.pitch)

        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{voice.language}">
            <voice name="{voice_name}">
                <prosody rate="{rate}" pitch="{pitch}">
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        return ssml.strip()

    def _convert_speed(self, speed: float) -> str:
        """속도 변환 (0.5~2.0 → Azure rate)"""
        if speed < 0.8:
            return f"{int((speed - 1) * 100)}%"
        elif speed > 1.2:
            return f"+{int((speed - 1) * 100)}%"
        else:
            return "default"

    def _convert_pitch(self, pitch: float) -> str:
        """피치 변환 (0.5~2.0 → Azure pitch)"""
        if pitch < 0.8:
            return f"{int((pitch - 1) * 50)}%"
        elif pitch > 1.2:
            return f"+{int((pitch - 1) * 50)}%"
        else:
            return "default"

    def supports_language(self, language: str) -> bool:
        """모든 언어 지원 (Azure는 광범위)"""
        return language.lower() in self.VOICE_MAP

    def get_engine_name(self) -> str:
        return "Azure-TTS"

    async def get_available_voices(self, language: str) -> List[dict]:
        """Azure에서 지원하는 음성 목록"""
        voices = self.VOICE_MAP.get(language, {})
        return [
            {"id": v, "name": v, "gender": g, "language": language}
            for g, v in voices.items()
        ]
