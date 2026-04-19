# -*- coding: utf-8 -*-
"""
Scene Parser - 장면 파싱

스크립트에서 장면 정보를 추출하고 구조화
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json


@dataclass
class ParsedScene:
    """파싱된 장면"""
    index: int
    description: str
    characters: list[str] = field(default_factory=list)  # 캐릭터 이름/ID
    location: str = ""
    time_of_day: str = "night"
    action: str = ""
    dialogue: str = ""
    dialogue_speaker: Optional[str] = None
    camera_angle: Optional[str] = None
    sfx: str = ""
    mood: str = ""

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "characters": self.characters,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "action": self.action,
            "dialogue": self.dialogue,
            "dialogue_speaker": self.dialogue_speaker,
            "camera_angle": self.camera_angle,
            "sfx": self.sfx,
            "mood": self.mood,
        }


class SceneParser:
    """
    장면 파서

    스크립트에서 장면 단위로 분리하고 속성 추출
    """

    # 장면 구분 마커
    SCENE_MARKERS = {
        "th": ["ตอนที่", "[ฉาก", "[ภาพตัด", "(เปิดฉาก)", "(ตัดฉาก"],
        "ko": ["에피소드", "[장면", "[씬", "(오프닝)", "(장면 전환"],
        "ja": ["エピソード", "[シーン", "[場面", "(オープニング)", "(場面転換"],
        "en": ["Episode", "[Scene", "[SCENE", "(Opening)", "(Cut to"],
    }

    # 장소 키워드
    LOCATION_KEYWORDS = {
        "bangkok": ["bangkok", "กรุงเทพ", "방콕", "バンコク"],
        "seoul": ["seoul", "서울", "ソウル"],
        "tokyo": ["tokyo", "도쿄", "東京"],
        "rooftop": ["rooftop", "ยอดตึก", "옥상", "屋上", "building top"],
        "police_station": ["police station", "สถานีตำรวจ", "경찰서", "警察署", "headquarters"],
        "street": ["street", "ถนน", "거리", "通り", "road"],
        "indoor": ["indoor", "ในอาคาร", "실내", "屋内", "inside"],
    }

    # 시간대 키워드
    TIME_KEYWORDS = {
        "night": ["night", "ค่ำคืน", "밤", "夜", "ยามค่ำ", "evening"],
        "day": ["day", "daytime", "กลางวัน", "낮", "昼", "morning"],
        "evening": ["evening", "sunset", "黄昏", "夕方", "저녁"],
        "dawn": ["dawn", "morning", "รุ่งอรุณ", "새벽", "夜明け"],
    }

    # 카메라 앵글 키워드
    CAMERA_KEYWORDS = {
        "low_angle": ["ต่ำ", "low angle", "낮은", "ローアングル", "looking up"],
        "high_angle": ["สูง", "high angle", "높은", "ハイアングル", "looking down"],
        "wide": ["wide", "กว้าง", "와이드", "ワイド", "establishing"],
        "close_up": ["close", "ใกล้", "클로즈업", "クローズ", "close-up"],
        "medium": ["medium", "กลาง", "미디엄", "ミディアム"],
    }

    def __init__(self):
        pass

    def parse(self, script: str, language: str = "th") -> list[ParsedScene]:
        """
        스크립트를 장면으로 분리

        Args:
            script: 입력 스크립트
            language: 언어 코드

        Returns:
            파싱된 장면 리스트
        """
        scenes = []
        markers = self.SCENE_MARKERS.get(language, self.SCENE_MARKERS["en"])

        # 장면 단위로 분리
        scene_blocks = self._split_into_scenes(script, markers)

        for idx, block in enumerate(scene_blocks):
            scene = self._parse_scene_block(idx, block, language)
            if scene:
                scenes.append(scene)

        return scenes

    def _split_into_scenes(self, script: str, markers: list) -> list[str]:
        """스크립트를 장면 블록으로 분리"""
        blocks = []
        current_block = []

        lines = script.split('\n')

        for line in lines:
            # 새 장면 시작 확인
            is_new_scene = any(marker in line for marker in markers)

            if is_new_scene and current_block:
                # 이전 블록 저장
                blocks.append('\n'.join(current_block))
                current_block = [line]
            else:
                current_block.append(line)

        # 마지막 블록
        if current_block:
            blocks.append('\n'.join(current_block))

        return blocks

    def _parse_scene_block(
        self,
        index: int,
        block: str,
        language: str
    ) -> Optional[ParsedScene]:
        """장면 블록 파싱"""
        if not block.strip():
            return None

        scene = ParsedScene(index=index, description="")

        lines = block.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 장면 설명 [ฉาก: ...]
            if line.startswith('[') or line.startswith('('):
                self._parse_bracket_content(line, scene, language)
            else:
                # 일반 텍스트
                if not scene.description:
                    scene.description = line

                # 대사 감지 ("..." 형식)
                if '"' in line or '"' in line or '"' in line:
                    scene.dialogue = self._extract_dialogue(line)
                    scene.dialogue_speaker = self._extract_speaker(line)

        # 메타데이터 추출
        self._extract_location(block, scene)
        self._extract_time(block, scene)
        self._extract_camera(block, scene)

        return scene

    def _parse_bracket_content(self, line: str, scene: ParsedScene, language: str):
        """대괄호/괄호 내용 파싱"""
        # [ฉาก: ...] - 장면 설명
        if 'ฉาก' in line or 'scene' in line.lower() or '장면' in line or 'シーン' in line:
            content = self._extract_bracket_content(line)
            scene.description = content
            scene.location = self._extract_location_keyword(content)

        # [ภาพตัด: ...] - 컷 설명
        elif 'ภาพตัด' in line or 'cut' in line.lower():
            content = self._extract_bracket_content(line)
            scene.action = content

        # [มุมกล้อง: ...] - 카메라 앵글
        elif 'มุมกล้อง' in line or 'camera' in line.lower():
            content = self._extract_bracket_content(line)
            scene.camera_angle = content

    def _extract_bracket_content(self, line: str) -> str:
        """괄호 안 내용 추출"""
        # [...] 형식
        match = re.search(r'\[([^\]]+)\]', line)
        if match:
            content = match.group(1)
            # "label:" 부분 제거
            if ':' in content:
                content = content.split(':', 1)[1].strip()
            return content

        # (...) 형식
        match = re.search(r'\(([^)]+)\)', line)
        if match:
            return match.group(1)

        return line

    def _extract_dialogue(self, line: str) -> str:
        """대사 추출"""
        # 다양한 따옴표 패턴
        patterns = [
            r'"([^"]+)"',  # "..."
            r'"([^"]+)"',  # "..."
            r'"([^"]+)"',  # "..."
            r'「([^」]+)」',  # Japanese
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)

        return ""

    def _extract_speaker(self, line: str) -> Optional[str]:
        """화자 추출"""
        # "이름: 대사" 또는 "이름 (대사)" 패턴
        match = re.match(r'([가-힣ぁ-んァ-ン一-龥ก-๙A-Za-z]+)\s*[:：]', line)
        if match:
            return match.group(1)
        return None

    def _extract_location(self, text: str, scene: ParsedScene):
        """장소 키워드 추출"""
        text_lower = text.lower()

        for location, keywords in self.LOCATION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                scene.location = location
                break

    def _extract_time(self, text: str, scene: ParsedScene):
        """시간대 추출"""
        text_lower = text.lower()

        for time, keywords in self.TIME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                scene.time_of_day = time
                break

    def _extract_camera(self, text: str, scene: ParsedScene):
        """카메라 앵글 추출"""
        text_lower = text.lower()

        for angle, keywords in self.CAMERA_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                scene.camera_angle = angle
                break

    def _extract_location_keyword(self, text: str) -> str:
        """텍스트에서 장소 키워드만 추출"""
        text_lower = text.lower()

        for location, keywords in self.LOCATION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return location

        return ""
