"""
Character Database

캐릭터 정보 저장 및 관리
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import json
import hashlib
import random


@dataclass
class CharacterProfile:
    """캐릭터 프로필"""
    id: str
    name: str
    appearance: str
    seed: int
    traits: List[str] = field(default_factory=list)
    reference_images: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "appearance": self.appearance,
            "seed": self.seed,
            "traits": self.traits,
            "reference_images": self.reference_images
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterProfile":
        return cls(
            id=data["id"],
            name=data["name"],
            appearance=data["appearance"],
            seed=data["seed"],
            traits=data.get("traits", []),
            reference_images=data.get("reference_images", [])
        )


class CharacterDB:
    """캐릭터 정보 저장 및 관리"""

    def __init__(self, cache_dir: str = "data/character_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.characters: Dict[str, CharacterProfile] = {}
        self._index_file = self.cache_dir / "character_index.json"

    def register_character(
        self,
        char_id: str,
        name: str,
        appearance: str,
        traits: Optional[List[str]] = None
    ) -> str:
        """
        새 캐릭터 등록, seed 자동 생성

        Args:
            char_id: 캐릭터 고유 ID
            name: 캐릭터 이름
            appearance: 외모 설명
            traits: 성격 특성 목록

        Returns:
            등록된 캐릭터 ID
        """
        seed = self._generate_seed(char_id, name, appearance)

        profile = CharacterProfile(
            id=char_id,
            name=name,
            appearance=appearance,
            seed=seed,
            traits=traits or [],
            reference_images=[]
        )

        self.characters[char_id] = profile
        self._save_character_file(profile)

        return char_id

    def get_character(self, char_id: str) -> Optional[CharacterProfile]:
        """캐릭터 조회"""
        if char_id in self.characters:
            return self.characters[char_id]

        profile = self._load_character_file(char_id)
        if profile:
            self.characters[char_id] = profile
            return profile

        return None

    def get_descriptor(self, char_id: str) -> str:
        """
        프롬프트용 descriptor 반환

        캐릭터 외모와 특성을 조합한 프롬프트 descriptor 생성
        """
        profile = self.get_character(char_id)
        if not profile:
            return ""

        parts = [profile.appearance]

        if profile.traits:
            trait_str = ", ".join(profile.traits)
            parts.append(f"personality: {trait_str}")

        return ", ".join(parts)

    def add_reference_image(self, char_id: str, image_path: str) -> bool:
        """참조 이미지 추가"""
        profile = self.get_character(char_id)
        if not profile:
            return False

        if image_path not in profile.reference_images:
            profile.reference_images.append(image_path)
            self._save_character_file(profile)

        return True

    def get_reference_images(self, char_id: str) -> List[str]:
        """참조 이미지 목록 반환"""
        profile = self.get_character(char_id)
        if not profile:
            return []
        return profile.reference_images

    def list_characters(self) -> List[str]:
        """등록된 캐릭터 ID 목록 반환"""
        return list(self.characters.keys())

    def delete_character(self, char_id: str) -> bool:
        """캐릭터 삭제"""
        if char_id in self.characters:
            del self.characters[char_id]
            char_file = self.cache_dir / f"{char_id}.json"
            if char_file.exists():
                char_file.unlink()
            return True
        return False

    def save(self):
        """인덱스 저장"""
        index_data = {
            "characters": list(self.characters.keys())
        }
        with open(self._index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        for profile in self.characters.values():
            self._save_character_file(profile)

    def load(self):
        """인덱스 로드"""
        if not self._index_file.exists():
            return

        with open(self._index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)

        for char_id in index_data.get("characters", []):
            profile = self._load_character_file(char_id)
            if profile:
                self.characters[char_id] = profile

    def _generate_seed(self, char_id: str, name: str, appearance: str) -> int:
        """일관성 있는 seed 생성"""
        combined = f"{char_id}:{name}:{appearance}"
        hash_bytes = hashlib.md5(combined.encode()).digest()
        seed = int.from_bytes(hash_bytes[:4], byteorder="big")
        return seed % 2147483647

    def _save_character_file(self, profile: CharacterProfile):
        """캐릭터 파일 저장"""
        char_file = self.cache_dir / f"{profile.id}.json"
        with open(char_file, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_character_file(self, char_id: str) -> Optional[CharacterProfile]:
        """캐릭터 파일 로드"""
        char_file = self.cache_dir / f"{char_id}.json"
        if not char_file.exists():
            return None

        with open(char_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CharacterProfile.from_dict(data)
