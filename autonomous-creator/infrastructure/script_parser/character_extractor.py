# -*- coding: utf-8 -*-
"""
Character Extractor - 로컬 규칙 기반 캐릭터 추출

스크립트에서 캐릭터 정의를 추출하는 로컬 규칙 기반 파서
"""
import re
from typing import Optional
from pathlib import Path

from core.domain.entities.character import (
    Character,
    CharacterAppearance,
    CharacterType,
)


class CharacterExtractor:
    """
    로컬 규칙 기반 캐릭터 추출기

    지원 형식:
    - "이름 (영문): 설명"
    - "이름: 설명"
    - "이름 (영문) - 타입: 설명"
    """

    # 언어별 캐릭터 정의 패턴
    PATTERNS = {
        "th": [
            # ฮีโรโน (Hearono): เด็กหนุ่มที่...
            r"([ก-๙]+)\s*\(([A-Za-z]+)\)\s*[:：]\s*(.+)",
            # ฮีโรโน: เด็กหนุ่มที่...
            r"([ก-๙]+)\s*[:：]\s*(.+)",
        ],
        "ko": [
            # 히로노 (Hirono): 젊은 남성...
            r"([가-힣]+)\s*\(([A-Za-z]+)\)\s*[:：]\s*(.+)",
            # 히로노: 젊은 남성...
            r"([가-힣]+)\s*[:：]\s*(.+)",
        ],
        "ja": [
            # ヒロノ (Hirono): 若い男性...
            r"([ぁ-んァ-ン一-龥]+)\s*\(([A-Za-z]+)\)\s*[:：]\s*(.+)",
            # ヒロノ: 若い男性...
            r"([ぁ-んァ-ン一-龥]+)\s*[:：]\s*(.+)",
        ],
        "en": [
            # Hirono: Young man with...
            r"([A-Za-z]+)\s*[:：]\s*(.+)",
        ],
    }

    # 캐릭터 타입 키워드
    TYPE_KEYWORDS = {
        "hero": ["ฮีโร่", "ฮีโรโน", "พระเอก", "히어로", "주인공", "ヒーロー", "主人公", "hero", "protagonist"],
        "villain": ["วายร้าย", "빌런", "악당", "反派", "villain", "antagonist", "enemy"],
        "supporting": ["ตัวประกอบ", "조연", "助演", "supporting", "secondary"],
    }

    # 외형 키워드
    APPEARANCE_KEYWORDS = {
        "age": {
            "young adult": ["young", "teen", "เด็กหนุ่ม", "젊은", "若い", "20代"],
            "adult": ["adult", "ผู้ใหญ่", "성인", "大人"],
            "middle_aged": ["middle-aged", "วัยกลางคน", "중년", "中年"],
            "elderly": ["elderly", "old", "สูงวัย", "노인", "老人"],
            "child": ["child", "kid", "เด็ก", "어린이", "子供"],
        },
        "gender": {
            "male": ["male", "man", "남성", "ชาย", "男性", "men"],
            "female": ["female", "woman", "여성", "หญิง", "女性", "women"],
        },
        "clothing": {
            "hooded cloak": ["hooded", "cloak", "คลุม", "후드", "フード", "cape"],
            "armor": ["armor", "เกราะ", "갑옷", "鎧", "armored"],
            "suit": ["suit", "สูท", "정장", "スーツ"],
            "casual": ["casual", "ธรรมดา", "캐주얼", "普通"],
            "uniform": ["uniform", "เครื่องแบบ", "제복", "制服"],
        },
        "accessories": {
            "headphones": ["headphones", "หูฟัง", "헤드폰", "ヘッドフォン", "earphones"],
            "glasses": ["glasses", "แว่น", "안경", "眼鏡"],
            "mask": ["mask", "หน้ากาก", "마스크", "マスク"],
        },
    }

    def __init__(self):
        self.patterns = self.PATTERNS

    def extract(self, script: str, language: str = "th") -> list[Character]:
        """
        스크립트에서 캐릭터 추출

        Args:
            script: 입력 스크립트
            language: 언어 코드 (th/ko/ja/en)

        Returns:
            추출된 캐릭터 리스트
        """
        characters = []
        lines = script.split('\n')

        # 언어 패턴 가져오기
        lang_patterns = self.patterns.get(language, self.patterns["en"])

        for line in lines:
            line = line.strip()
            if not line:
                continue

            char = self._extract_from_line(line, lang_patterns, language)
            if char:
                characters.append(char)

        return characters

    def _extract_from_line(
        self,
        line: str,
        patterns: list,
        language: str
    ) -> Optional[Character]:
        """단일 라인에서 캐릭터 추출"""

        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()

                if len(groups) == 3:
                    # 이름 (영문): 설명 형식
                    name_local, name, description = groups
                elif len(groups) == 2:
                    # 이름: 설명 형식
                    name = groups[0]
                    name_local = name if language != "en" else None
                    description = groups[1]
                else:
                    continue

                # 캐릭터 생성
                appearance = self._parse_description(description, language)
                char_type = self._detect_type(description, name)

                return Character(
                    name=name.strip(),
                    name_local=name_local.strip() if name_local else None,
                    type=char_type,
                    appearance=appearance,
                    source_language=language,
                )

        return None

    def _parse_description(self, description: str, language: str) -> CharacterAppearance:
        """설명에서 외형 속성 추출"""
        appearance = CharacterAppearance()
        desc_lower = description.lower()

        # 나이
        for age, keywords in self.APPEARANCE_KEYWORDS["age"].items():
            if any(kw in desc_lower for kw in keywords):
                appearance.age = age
                break

        # 성별
        for gender, keywords in self.APPEARANCE_KEYWORDS["gender"].items():
            if any(kw in desc_lower for kw in keywords):
                appearance.gender = gender
                break

        # 의상
        for clothing, keywords in self.APPEARANCE_KEYWORDS["clothing"].items():
            if any(kw in desc_lower for kw in keywords):
                appearance.clothing.append(clothing)

        # 액세서리
        for accessory, keywords in self.APPEARANCE_KEYWORDS["accessories"].items():
            if any(kw in desc_lower for kw in keywords):
                appearance.accessories.append(accessory)

        # 특징 - 키워드에서 찾지 못한 설명 부분
        # TODO: 더 정교한 파싱 필요

        return appearance

    def _detect_type(self, description: str, name: str) -> CharacterType:
        """캐릭터 타입 감지"""
        text = (description + " " + name).lower()

        for char_type, keywords in self.TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return CharacterType(char_type)

        return CharacterType.SUPPORTING

    def extract_from_character_section(
        self,
        script: str,
        language: str = "th"
    ) -> list[Character]:
        """
        '캐릭터:' 섹션에서 캐릭터 추출

        스크립트에 별도 캐릭터 정의 섹션이 있는 경우 사용
        """
        characters = []

        # 캐릭터 섹션 찾기
        section_markers = [
            "ตัวละคร", "ตัวละครหลัก",  # Thai
            "등장인물", "캐릭터",  # Korean
            "登場人物", "キャラクター",  # Japanese
            "characters", "cast",  # English
        ]

        lines = script.split('\n')
        in_character_section = False

        for line in lines:
            line_stripped = line.strip()

            # 섹션 시작 확인
            if any(marker in line_stripped.lower() for marker in section_markers):
                in_character_section = True
                continue

            # 다음 섹션 시작 시 종료
            if in_character_section and line_stripped.startswith('#'):
                break

            if in_character_section and line_stripped:
                char = self._extract_from_line(
                    line_stripped,
                    self.patterns.get(language, self.patterns["en"]),
                    language
                )
                if char:
                    characters.append(char)

        return characters
