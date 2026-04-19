"""
TTSGenerator - 텍스트 음성 변환

Edge TTS / Azure TTS 연동
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class TTSGenerationResult:
    """TTS 생성 결과"""
    success: bool
    character_id: str
    audio_path: Optional[Path] = None
    text: str = ""
    voice_id: str = ""
    emotion: str = "neutral"
    duration_ms: int = 0
    generation_time_ms: int = 0
    error_message: str = ""


class TTSGenerator:
    """
    TTS 생성기

    - Edge TTS (무료)
    - Azure TTS (유료, 고품질)
    - 캐릭터별 보이스 매핑
    - 감정 파라미터
    """

    # 기본 한국어 보이스
    DEFAULT_VOICES = {
        "female_young": "ko-KR-SunHiNeural",
        "female_adult": "ko-KR-JiMinNeural",
        "male_young": "ko-KR-InJoonNeural",
        "male_adult": "ko-KR-BongJinNeural",
        "narrator": "ko-KR-HyunsuNeural",
    }

    def __init__(
        self,
        provider: str = "edge",
        api_key: str = None,
        output_dir: str = "outputs/audio"
    ):
        self.provider = provider
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 캐릭터별 보이스 매핑
        self._character_voices: Dict[str, str] = {}

        # 카운터
        self._counter = 0

    def set_character_voice(
        self,
        character_id: str,
        voice_id: str
    ) -> None:
        """캐릭터별 보이스 설정"""
        self._character_voices[character_id] = voice_id
        logger.info(f"Voice set for {character_id}: {voice_id}")

    def get_voice_for_character(
        self,
        character_id: str,
        default_type: str = "female_young"
    ) -> str:
        """캐릭터 보이스 조회"""
        if character_id in self._character_voices:
            return self._character_voices[character_id]
        return self.DEFAULT_VOICES.get(default_type, self.DEFAULT_VOICES["female_young"])

    async def generate(
        self,
        text: str,
        character_id: str = None,
        emotion: str = "neutral",
        speed: float = 1.0,
        pitch: float = 0.0
    ) -> TTSGenerationResult:
        """
        단일 텍스트 TTS

        Args:
            text: 변환할 텍스트
            character_id: 캐릭터 ID
            emotion: 감정 (happy, sad, excited, angry, neutral)
            speed: 속도 (0.5-2.0)
            pitch: 피치 (-50 to +50)

        Returns:
            TTSGenerationResult
        """
        start_time = datetime.now()

        try:
            # 감정 파라미터 변환
            params = self._emotion_to_params(emotion)

            # 속도/피치 적용
            rate = params["rate"]
            if speed != 1.0:
                rate = f"{int((speed - 1) * 100):+d}%"

            pitch_str = params["pitch"]
            if pitch != 0:
                pitch_str = f"{int(pitch):+d}Hz"

            # 보이스 선택
            voice_id = self.get_voice_for_character(character_id) if character_id else self.DEFAULT_VOICES["narrator"]

            # TTS 호출
            if self.provider == "azure":
                audio_data = await self._call_azure_tts(
                    text=text,
                    voice_id=voice_id,
                    emotion=emotion
                )
            else:
                audio_data = await self._call_edge_tts(
                    text=text,
                    voice_id=voice_id,
                    rate=rate,
                    pitch=pitch_str
                )

            if not audio_data:
                return TTSGenerationResult(
                    success=False,
                    character_id=character_id or "",
                    error_message="TTS generation returned no data"
                )

            # 저장
            audio_path = await self._save_audio(audio_data, character_id)

            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            return TTSGenerationResult(
                success=True,
                character_id=character_id or "",
                audio_path=audio_path,
                text=text,
                voice_id=voice_id,
                emotion=emotion,
                duration_ms=len(audio_data) // 32,  # 대략적인 추정
                generation_time_ms=int(elapsed)
            )

        except Exception as e:
            logger.exception("TTS generation failed")
            return TTSGenerationResult(
                success=False,
                character_id=character_id or "",
                error_message=str(e)
            )

    async def generate_batch(
        self,
        texts: List[Dict[str, Any]]
    ) -> List[TTSGenerationResult]:
        """
        여러 텍스트 TTS

        Args:
            texts: [{text, character_id, emotion}, ...]

        Returns:
            생성 결과 목록
        """
        tasks = [
            self.generate(
                text=item["text"],
                character_id=item.get("character_id"),
                emotion=item.get("emotion", "neutral")
            )
            for item in texts
        ]

        results = await asyncio.gather(*tasks)
        return list(results)

    async def _call_edge_tts(
        self,
        text: str,
        voice_id: str,
        rate: str,
        pitch: str
    ) -> bytes:
        """Edge TTS 호출"""
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            pitch=pitch
        )

        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    async def _call_azure_tts(
        self,
        text: str,
        voice_id: str,
        emotion: str
    ) -> bytes:
        """Azure TTS 호출"""
        import azure.cognitiveservices.speech as speechsdk

        speech_config = speechsdk.SpeechConfig(
            subscription=self.api_key,
            region="koreacentral"
        )
        speech_config.speech_synthesis_voice_name = voice_id

        # SSML로 감정 표현
        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ko-KR">
            <voice name="{voice_id}">
                <mstts:express-as style="{emotion}">
                    {text}
                </mstts:express-as>
            </voice>
        </speak>
        """

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None
        )

        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        else:
            raise Exception(f"Azure TTS failed: {result.reason}")

    async def _save_audio(self, audio_data: bytes, character_id: str) -> Path:
        """오디오 저장"""
        self._counter += 1
        filename = f"{character_id or 'narrator'}_{self._counter:03d}.wav"
        path = self.output_dir / filename

        with open(path, 'wb') as f:
            f.write(audio_data)

        logger.info(f"Audio saved: {path}")
        return path

    def _emotion_to_params(self, emotion: str) -> Dict[str, Any]:
        """감정을 TTS 파라미터로 변환"""
        emotion_map = {
            "happy": {"rate": "+10%", "pitch": "+5Hz"},
            "sad": {"rate": "-15%", "pitch": "-5Hz"},
            "excited": {"rate": "+20%", "pitch": "+10Hz"},
            "angry": {"rate": "+10%", "pitch": "-2Hz"},
            "fear": {"rate": "-10%", "pitch": "+3Hz"},
            "neutral": {"rate": "+0%", "pitch": "+0Hz"},
        }
        return emotion_map.get(emotion, emotion_map["neutral"])


# 싱글톤
_generator: Optional[TTSGenerator] = None


def get_tts_generator(provider: str = "edge", api_key: str = None) -> TTSGenerator:
    """TTS 생성기 싱글톤"""
    global _generator
    if _generator is None or api_key:
        _generator = TTSGenerator(provider=provider, api_key=api_key)
    return _generator
