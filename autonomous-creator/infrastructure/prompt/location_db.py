# -*- coding: utf-8 -*-
"""
Location DB - 장소 데이터베이스

계층적 장소 정보 관리 및 프롬프트 생성
"""
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class LocationData:
    """장소 데이터"""
    id: str
    name: str
    name_local: Optional[str] = None
    description: str = ""
    elements: list[str] = field(default_factory=list)
    lighting: str = ""
    atmosphere: str = ""
    colors: list[str] = field(default_factory=list)
    weather: list[str] = field(default_factory=list)
    camera_angles: dict[str, str] = field(default_factory=dict)
    style_modifiers: list[str] = field(default_factory=list)
    negative: str = ""

    def to_prompt_segment(self, include_elements: int = 5) -> str:
        """프롬프트용 문자열 변환"""
        parts = []

        # 이름
        parts.append(self.name)

        # 주요 요소들
        if self.elements:
            selected = self.elements[:include_elements]
            parts.append(', '.join(selected))

        # 조명
        if self.lighting:
            parts.append(self.lighting)

        # 분위기
        if self.atmosphere:
            parts.append(self.atmosphere)

        # 색상
        if self.colors:
            parts.append(f"{', '.join(self.colors[:3])} tones")

        # 스타일
        if self.style_modifiers:
            parts.append(self.style_modifiers[0])

        return ', '.join(parts)

    def get_camera_angle(self, angle_type: str = "wide") -> str:
        """카메라 앵글 프롬프트 반환"""
        return self.camera_angles.get(angle_type, "")

    def get_negative(self) -> str:
        """Negative 프롬프트 반환"""
        return self.negative


class LocationDB:
    """
    장소 데이터베이스

    계층 구조로 장소 정보 관리:
    - cities: 도시별 야경/낮
    - place_types: 장소 타입 (옥상, 경찰서 등)
    - time_of_day: 시간대
    """

    def __init__(self, data_dir: str = "data/locations"):
        """
        초기화

        Args:
            data_dir: 장소 데이터 디렉토리
        """
        self.data_dir = Path(data_dir)

        # 데이터 저장소
        self._cities: dict[str, LocationData] = {}
        self._place_types: dict[str, LocationData] = {}
        self._time_of_day: dict[str, LocationData] = {}

        # 별칭 매핑 (대체 이름)
        self._aliases = {
            # 도시 별칭
            "bangkok": ["bangkok_night", "กรุงเทพ", "방콕"],
            "seoul": ["seoul_night", "서울"],
            "tokyo": ["tokyo_night", "도쿄", "東京"],
            "bangkok_20xx": ["bangkok_night_20xx", "future bangkok"],
            # 장소 별칭
            "rooftop": ["roof", "building top", "옥상"],
            "police": ["police_station", "경찰서"],
            "street": ["road", "거리"],
            # 시간대 별칭
            "night": ["밤", "夜", "nighttime"],
            "day": ["낮", "daytime"],
            "evening": ["저녁", "dusk", "sunset"],
        }

        # 데이터 로드
        self._load_all()

    def _load_all(self):
        """모든 장소 데이터 로드"""
        self._load_category("cities", self._cities)
        self._load_category("place_types", self._place_types)
        self._load_category("time_of_day", self._time_of_day)

    def _load_category(self, category: str, storage: dict):
        """카테고리별 데이터 로드"""
        category_dir = self.data_dir / category

        if not category_dir.exists():
            return

        for json_file in category_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                location = LocationData(
                    id=data.get("id", json_file.stem),
                    name=data.get("name", json_file.stem),
                    name_local=data.get("name_local"),
                    description=data.get("description", ""),
                    elements=data.get("elements", []),
                    lighting=data.get("lighting", ""),
                    atmosphere=data.get("atmosphere", ""),
                    colors=data.get("colors", []),
                    weather=data.get("weather", []),
                    camera_angles=data.get("camera_angles", {}),
                    style_modifiers=data.get("style_modifiers", []),
                    negative=data.get("negative", ""),
                )

                storage[location.id] = location

            except Exception as e:
                print(f"장소 데이터 로드 실패 ({json_file}): {e}")

    def find(
        self,
        city: Optional[str] = None,
        place_type: Optional[str] = None,
        time: Optional[str] = None,
    ) -> tuple[Optional[LocationData], Optional[LocationData], Optional[LocationData]]:
        """
        계층 검색으로 장소 조회

        Args:
            city: 도시 ID 또는 별칭
            place_type: 장소 타입 ID 또는 별칭
            time: 시간대 ID 또는 별칭

        Returns:
            (city_data, place_type_data, time_data)
        """
        city_data = self._resolve_location(city, self._cities)
        place_data = self._resolve_location(place_type, self._place_types)
        time_data = self._resolve_location(time, self._time_of_day)

        return city_data, place_data, time_data

    def _resolve_location(
        self,
        query: Optional[str],
        storage: dict
    ) -> Optional[LocationData]:
        """쿼리로 장소 찾기 (ID + 별칭 지원)"""
        if not query:
            return None

        query_lower = query.lower()

        # 직접 ID 매치
        if query_lower in storage:
            return storage[query_lower]

        # 별칭 검색
        for loc_id, location in storage.items():
            if query_lower == loc_id.lower():
                return location

        # _aliases에서 검색
        for canonical, aliases in self._aliases.items():
            if query_lower in [a.lower() for a in aliases]:
                if canonical in storage:
                    return storage[canonical]

        return None

    def build_location_prompt(
        self,
        city: Optional[str] = None,
        place_type: Optional[str] = None,
        time: Optional[str] = None,
        camera_angle: str = "wide",
    ) -> str:
        """
        통합 장소 프롬프트 생성

        Args:
            city: 도시
            place_type: 장소 타입
            time: 시간대
            camera_angle: 카메라 앵글

        Returns:
            완성된 장소 프롬프트
        """
        city_data, place_data, time_data = self.find(city, place_type, time)

        parts = []

        # 1. 장소 타입 (옥상, 경찰서 등)
        if place_data:
            parts.append(place_data.to_prompt_segment(include_elements=4))

        # 2. 도시 (배경)
        if city_data:
            parts.append(f"background: {city_data.to_prompt_segment(include_elements=3)}")

        # 3. 시간대
        if time_data:
            parts.append(time_data.to_prompt_segment(include_elements=2))

        # 카메라 앵글
        camera_prompt = ""
        if place_data and camera_angle in place_data.camera_angles:
            camera_prompt = place_data.get_camera_angle(camera_angle)
        elif city_data and camera_angle in city_data.camera_angles:
            camera_prompt = city_data.get_camera_angle(camera_angle)

        if camera_prompt:
            parts.append(camera_prompt)

        return ', '.join(parts)

    def build_negative_prompt(
        self,
        city: Optional[str] = None,
        place_type: Optional[str] = None,
    ) -> str:
        """장소 Negative 프롬프트"""
        city_data, place_data, _ = self.find(city, place_type)

        negatives = ["blurry", "low quality", "watermark"]

        if city_data and city_data.negative:
            negatives.append(city_data.negative)

        if place_data and place_data.negative:
            negatives.append(place_data.negative)

        return ', '.join(negatives)

    def list_cities(self) -> list[str]:
        """사용 가능한 도시 목록"""
        return list(self._cities.keys())

    def list_place_types(self) -> list[str]:
        """사용 가능한 장소 타입 목록"""
        return list(self._place_types.keys())

    def list_times(self) -> list[str]:
        """사용 가능한 시간대 목록"""
        return list(self._time_of_day.keys())

    def get(self, location_id: str) -> Optional[LocationData]:
        """ID로 직접 조회"""
        # 모든 카테고리에서 검색
        if location_id in self._cities:
            return self._cities[location_id]
        if location_id in self._place_types:
            return self._place_types[location_id]
        if location_id in self._time_of_day:
            return self._time_of_day[location_id]
        return None
