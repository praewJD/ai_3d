"""
Audio Domain Entity

음성 및 오디오 관련 데이터 모델
"""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class VoiceGender(str, Enum):
    """음성 성별"""
    MALE = "male"
    FEMALE = "female"


class VoiceSettings(BaseModel):
    """
    음성 설정

    TTS 엔진에서 사용할 음성 설정
    """
    # 언어
    language: str = Field(
        default="ko",
        description="언어 코드 (ko, th, en, ja, zh)"
    )

    # 음성 속성
    gender: VoiceGender = Field(
        default=VoiceGender.FEMALE,
        description="음성 성별"
    )
    speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="재생 속도 (0.5~2.0)"
    )
    pitch: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="피치 조절 (0.5~2.0)"
    )

    # GPT-SoVITS 전용
    speaker_id: Optional[str] = Field(
        default=None,
        description="GPT-SoVITS 스피커 참조 오디오 경로"
    )
    emotion: Optional[str] = Field(
        default=None,
        description="감정 표현 (neutral, happy, sad, angry)"
    )

    # Azure TTS 전용
    voice_name: Optional[str] = Field(
        default=None,
        description="Azure TTS 음성 이름 (예: th-TH-PremwadeeNeural)"
    )

    # F5-TTS 전용 (Voice Cloning)
    reference_audio: Optional[str] = Field(
        default=None,
        description="F5-TTS Reference Audio 파일 경로 (보이스 클론용)"
    )
    reference_text: Optional[str] = Field(
        default=None,
        description="Reference Audio 텍스트 (F5-TTS용)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "language": "ko",
                "gender": "female",
                "speed": 1.0,
                "pitch": 1.0,
                "speaker_id": "refs/voice_korean_female_01.wav",
                "emotion": "neutral",
                "voice_name": None
            }
        }


class AudioTrack(BaseModel):
    """
    오디오 트랙

    생성된 오디오 파일 정보
    """
    id: str
    scene_id: str = Field(..., description="연결된 Scene ID")
    file_path: str = Field(..., description="오디오 파일 경로")

    # 오디오 속성
    duration: float = Field(..., ge=0, description="재생 시간(초)")
    sample_rate: int = Field(default=44100, description="샘플 레이트 (Hz)")
    channels: int = Field(default=1, ge=1, le=2, description="채널 수")

    # 메타데이터
    text: str = Field(..., description="변환된 텍스트")
    voice_settings: VoiceSettings = Field(..., description="사용된 음성 설정")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "audio_001",
                "scene_id": "scene_001",
                "file_path": "outputs/audio/scene_001.wav",
                "duration": 3.5,
                "sample_rate": 44100,
                "channels": 1,
                "text": "어둠이 내리앉는 숲속으로 한 소년이 걸어들어갑니다.",
                "voice_settings": {
                    "language": "ko",
                    "gender": "female",
                    "speed": 1.0
                },
                "created_at": "2026-03-29T10:02:00"
            }
        }
