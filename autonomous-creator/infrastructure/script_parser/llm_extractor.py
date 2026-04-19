# -*- coding: utf-8 -*-
"""
LLM Extractor - Claude API 기반 캐릭터/장면 추출

복잡한 스크립트에서 정확한 정보 추출을 위한 LLM 사용
"""
import os
import json
import asyncio
from typing import Optional
from dataclasses import dataclass

from core.domain.entities.character import (
    Character,
    CharacterAppearance,
    CharacterType,
)
from infrastructure.script_parser.scene_parser import ParsedScene


@dataclass
class LLMExtractionResult:
    """LLM 추출 결과"""
    characters: list[Character]
    scenes: list[dict]
    raw_response: str


class LLMExtractor:
    """
    Claude API 기반 스크립트 분석기

    로컬 규칙으로 처리하기 어려운 복잡한 스크립트 분석
    """

    EXTRACTION_PROMPT = """
다음 스크립트에서 등장인물과 장면 정보를 추출하세요.

스크립트:
{script}

출력 형식 (JSON):
{{
  "characters": [
    {{
      "name": "영문명",
      "name_local": "원어명",
      "type": "hero|villain|supporting|extra",
      "appearance": {{
        "age": "young adult|adult|middle_aged|elderly|child",
        "gender": "male|female|unknown",
        "body_type": "slim|average|athletic|muscular|heavy",
        "hair": "머리 스타일 설명",
        "clothing": ["의상1", "의상2"],
        "accessories": ["액세서리1"],
        "distinctive_features": ["특징1"]
      }},
      "personality": ["성격1", "성격2"],
      "powers": ["능력1", "능력2"]
    }}
  ],
  "scenes": [
    {{
      "description": "장면 설명",
      "characters": ["등장 캐릭터명"],
      "location": "bangkok_night|seoul_night|tokyo_night|rooftop|police_station|street",
      "time_of_day": "night|day|evening|dawn",
      "action": "주요 동작",
      "mood": "장면 분위기"
    }}
  ]
}}

중요:
1. 캐릭터 외형은 시각적으로 묘사 가능한 것만 포함
2. type은 hero(주인공), villain(빌런), supporting(조연), extra(엑스트라) 중 선택
3. location은 가능한 한 목록에서 선택, 없으면 새로 정의
4. personality와 powers는 스크립트에서 명시된 것만 추출
"""

    def __init__(self, api_key: Optional[str] = None):
        """
        초기화

        Args:
            api_key: Anthropic API 키 (없으면 환경변수 사용)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def client(self):
        """지연 초기화 클라이언트"""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic 패키지를 설치하세요: pip install anthropic")
        return self._client

    async def extract(
        self,
        script: str,
        language: str = "th"
    ) -> LLMExtractionResult:
        """
        스크립트에서 캐릭터와 장면 추출

        Args:
            script: 입력 스크립트
            language: 언어 코드

        Returns:
            추출 결과
        """
        # 언어별 프롬프트 조정
        language_hint = self._get_language_hint(language)
        prompt = self.EXTRACTION_PROMPT.format(
            script=script[:8000]  # 토큰 제한
        ) + f"\n\n언어: {language_hint}"

        try:
            # API 호출 (비동기 래핑)
            response = await asyncio.to_thread(
                self._call_api,
                prompt
            )

            # 결과 파싱
            result = self._parse_response(response)

            return result

        except Exception as e:
            print(f"LLM 추출 오류: {e}")
            return LLMExtractionResult(characters=[], scenes=[], raw_response="")

    def _call_api(self, prompt: str) -> str:
        """동기 API 호출"""
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    def _parse_response(self, response: str) -> LLMExtractionResult:
        """API 응답 파싱"""
        characters = []
        scenes = []

        # JSON 추출
        try:
            # ```json ... ``` 블록 찾기
            json_match = None
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            else:
                json_str = "{}"

            data = json.loads(json_str)

            # 캐릭터 변환
            for char_data in data.get("characters", []):
                char = self._dict_to_character(char_data)
                characters.append(char)

            # 장면 데이터
            scenes = data.get("scenes", [])

        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")

        return LLMExtractionResult(
            characters=characters,
            scenes=scenes,
            raw_response=response
        )

    def _dict_to_character(self, data: dict) -> Character:
        """딕셔너리를 Character로 변환"""
        appearance_data = data.get("appearance", {})

        appearance = CharacterAppearance(
            age=appearance_data.get("age", "adult"),
            gender=appearance_data.get("gender", "unknown"),
            body_type=appearance_data.get("body_type", "average"),
            hair=appearance_data.get("hair", ""),
            clothing=appearance_data.get("clothing", []),
            accessories=appearance_data.get("accessories", []),
            distinctive_features=appearance_data.get("distinctive_features", []),
        )

        type_str = data.get("type", "supporting")
        try:
            char_type = CharacterType(type_str)
        except ValueError:
            char_type = CharacterType.SUPPORTING

        return Character(
            name=data.get("name", "Unknown"),
            name_local=data.get("name_local"),
            type=char_type,
            appearance=appearance,
            personality=data.get("personality", []),
            powers=data.get("powers", []),
        )

    def _get_language_hint(self, language: str) -> str:
        """언어 힌트 반환"""
        hints = {
            "th": "Thai (태국어)",
            "ko": "Korean (한국어)",
            "ja": "Japanese (일본어)",
            "en": "English",
        }
        return hints.get(language, language)

    async def extract_characters_only(
        self,
        script: str,
        language: str = "th"
    ) -> list[Character]:
        """캐릭터만 추출"""
        result = await self.extract(script, language)
        return result.characters

    async def extract_scenes_only(
        self,
        script: str,
        language: str = "th"
    ) -> list[dict]:
        """장면만 추출"""
        result = await self.extract(script, language)
        return result.scenes
