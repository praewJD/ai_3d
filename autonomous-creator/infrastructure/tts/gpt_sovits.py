"""
GPT-SoVITS TTS Engine

고품질 다국어 TTS (한국어, 일본어, 중국어)
"""
import httpx
import os
from typing import Optional, List
from pathlib import Path

from .base import BaseTTSEngine
from core.domain.entities.audio import VoiceSettings, VoiceGender
from config.settings import get_settings


class GPTSoVITSEngine(BaseTTSEngine):
    """
    GPT-SoVITS v3 TTS 엔진

    로컬 서버 (9872 포트)와 통신하여 고품질 음성 생성
    - 한국어, 일본어, 중국어 지원
    - 보이스 클로닝 가능
    """

    # GPT-SoVITS 언어 코드 매핑
    LANG_MAP = {
        "ko": "ko",
        "ja": "ja",
        "zh": "zh",
        "en": "en",  # 지원하지만 품질 낮음
    }

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 60.0
    ):
        super().__init__()
        settings = get_settings()
        self.base_url = base_url or settings.gpt_sovits_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def _generate_audio(
        self,
        text: str,
        voice: VoiceSettings,
        output_path: str
    ) -> str:
        """GPT-SoVITS API 호출"""

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 언어 코드 변환
        lang_code = self.LANG_MAP.get(voice.language, "ko")

        # API 요청 페이로드
        payload = {
            "text": text,
            "text_lang": lang_code,
            "ref_audio_path": voice.speaker_id,  # 참조 음성 경로
            "prompt_text": "",
            "prompt_lang": lang_code,
            "top_k": 5,
            "top_p": 1.0,
            "temperature": 1.0,
            "speed": voice.speed,
            "text_split_method": "cut5",  # 문장 단위 분할
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/tts",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            # 오디오 저장
            with open(output_path, "wb") as f:
                f.write(response.content)

            return output_path

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"GPT-SoVITS API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"GPT-SoVITS connection error: {str(e)}")

    def supports_language(self, language: str) -> bool:
        """지원 언어 확인"""
        return language.lower() in ["ko", "ja", "zh"]

    def get_engine_name(self) -> str:
        return "GPT-SoVITS"

    async def get_available_voices(self, language: str) -> List[dict]:
        """사용 가능한 음성 목록"""
        # GPT-SoVITS는 참조 오디오 기반
        # 미리 등록된 스피커 목록 반환
        return [
            {
                "id": "speaker_ko_female_01",
                "name": "한국어 여성 1",
                "gender": "female",
                "language": "ko"
            },
            {
                "id": "speaker_ko_male_01",
                "name": "한국어 남성 1",
                "gender": "male",
                "language": "ko"
            },
            {
                "id": "speaker_ja_female_01",
                "name": "일본어 여성 1",
                "gender": "female",
                "language": "ja"
            },
            {
                "id": "speaker_zh_female_01",
                "name": "중국어 여성 1",
                "gender": "female",
                "language": "zh"
            },
        ]

    async def health_check(self) -> bool:
        """서버 상태 확인"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False

    async def close(self):
        """연결 종료"""
        await self.client.aclose()
