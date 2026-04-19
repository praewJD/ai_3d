"""
Edge-TTS Engine

Microsoft Edge 무료 TTS (영어 및 다국어)
"""
import asyncio
from typing import List
from pathlib import Path

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

from .base import BaseTTSEngine
from core.domain.entities.audio import VoiceSettings, VoiceGender
from config.settings import get_settings


class EdgeTTSEngine(BaseTTSEngine):
    """
    Edge-TTS 엔진

    - 무료 사용 가능
    - 고품질 Neural Voice
    - 영어 최적, 다국어 지원
    """

    # Edge-TTS 음성 매핑
    VOICE_MAP = {
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
        "th": {
            "female": "th-TH-PremwadeeNeural",
            "male": "th-TH-NiwatNeural",
        },
    }

    def __init__(self):
        super().__init__()

        if not EDGE_TTS_AVAILABLE:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")

    async def _generate_audio(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """Edge-TTS로 오디오 생성"""

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 음성 선택
        voice_name = self._get_voice_name(voice)

        # Communicate 생성
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_name,
            rate=self._convert_rate(voice.speed),
            pitch=self._convert_pitch(voice.pitch)
        )

        # 오디오 생성
        await communicate.save(output_path)

        return output_path

    def _get_voice_name(self, voice: VoiceSettings) -> str:
        """음성 이름 결정"""
        if voice.voice_name:
            return voice.voice_name

        lang_voices = self.VOICE_MAP.get(voice.language, {})
        gender_key = voice.gender.value if voice.gender else "female"

        return lang_voices.get(gender_key, "en-US-JennyNeural")

    def _convert_rate(self, speed: float) -> str:
        """속도 변환 (0.5~2.0 → Edge rate)"""
        # Edge-TTS: "+0%" ~ "+100%" 또는 "-100%" ~ "-0%"
        percentage = int((speed - 1) * 100)
        if percentage >= 0:
            return f"+{percentage}%"
        else:
            return f"{percentage}%"

    def _convert_pitch(self, pitch: float) -> str:
        """피치 변환 (0.5~2.0 → Edge pitch)"""
        # Edge-TTS: "+0Hz" ~ "+50Hz" 또는 "-50Hz" ~ "-0Hz"
        hz = int((pitch - 1) * 50)
        if hz >= 0:
            return f"+{hz}Hz"
        else:
            return f"{hz}Hz"

    def supports_language(self, language: str) -> bool:
        """지원 언어 확인"""
        return language.lower() in self.VOICE_MAP

    def get_engine_name(self) -> str:
        return "Edge-TTS"

    async def get_available_voices(self, language: str) -> List[dict]:
        """사용 가능한 음성 목록"""
        # Edge-TTS에서 실제 목록 가져오기
        try:
            voices = await edge_tts.list_voices()
            filtered = [
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "gender": v["Gender"].lower(),
                    "language": v["Locale"][:2]
                }
                for v in voices
                if v["Locale"].startswith(language)
            ]
            return filtered
        except:
            # 실패 시 기본 목록 반환
            voices = self.VOICE_MAP.get(language, {})
            return [
                {"id": v, "name": v, "gender": g, "language": language}
                for g, v in voices.items()
            ]
