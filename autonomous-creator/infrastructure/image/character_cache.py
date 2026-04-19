# -*- coding: utf-8 -*-
"""
Character Cache - 캐릭터 이미지/임베딩 캐시

생성된 캐릭터 기준 이미지와 임베딩을 캐싱하여 재사용
"""
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    character_id: str
    character_name: str
    created_at: str
    reference_image: str
    embedding_file: Optional[str] = None
    metadata: dict = None

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "created_at": self.created_at,
            "reference_image": self.reference_image,
            "embedding_file": self.embedding_file,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        return cls(
            character_id=data["character_id"],
            character_name=data["character_name"],
            created_at=data["created_at"],
            reference_image=data["reference_image"],
            embedding_file=data.get("embedding_file"),
            metadata=data.get("metadata"),
        )


class CharacterCache:
    """
    캐릭터 이미지/임베딩 캐시

    디렉토리 구조:
    cache_dir/
    ├── index.json           # 캐시 인덱스
    ├── {character_id}/
    │   ├── reference.png    # 기준 이미지
    │   ├── embedding.npy    # IP-Adapter 임베딩
    │   └── metadata.json    # 캐릭터 메타데이터
    """

    def __init__(self, cache_dir: str = "data/character_cache"):
        """
        초기화

        Args:
            cache_dir: 캐시 디렉토리 경로
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.cache_dir / "index.json"
        self._index: dict[str, CacheEntry] = {}

        self._load_index()

    def _load_index(self):
        """인덱스 로드"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._index = {
                        k: CacheEntry.from_dict(v) for k, v in data.items()
                    }
            except Exception as e:
                print(f"캐시 인덱스 로드 실패: {e}")
                self._index = {}

    def _save_index(self):
        """인덱스 저장"""
        try:
            data = {k: v.to_dict() for k, v in self._index.items()}
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"캐시 인덱스 저장 실패: {e}")

    def get(self, character_id: str) -> Optional[str]:
        """
        캐시된 기준 이미지 경로 반환

        Args:
            character_id: 캐릭터 ID

        Returns:
            이미지 경로 또는 None
        """
        if character_id not in self._index:
            return None

        entry = self._index[character_id]
        image_path = self.cache_dir / character_id / entry.reference_image

        if image_path.exists():
            return str(image_path)

        return None

    def set(
        self,
        character_id: str,
        character_name: str,
        image: Image.Image,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        기준 이미지 캐시 저장

        Args:
            character_id: 캐릭터 ID
            character_name: 캐릭터 이름
            image: PIL Image
            metadata: 추가 메타데이터

        Returns:
            저장된 이미지 경로
        """
        # 캐릭터 디렉토리 생성
        char_dir = self.cache_dir / character_id
        char_dir.mkdir(parents=True, exist_ok=True)

        # 이미지 저장
        image_path = char_dir / "reference.png"
        image.save(image_path, "PNG", quality=95)

        # 인덱스 업데이트
        entry = CacheEntry(
            character_id=character_id,
            character_name=character_name,
            created_at=datetime.now().isoformat(),
            reference_image="reference.png",
            metadata=metadata,
        )

        self._index[character_id] = entry
        self._save_index()

        return str(image_path)

    def get_embedding(self, character_id: str) -> Optional[np.ndarray]:
        """
        캐시된 임베딩 반환

        Args:
            character_id: 캐릭터 ID

        Returns:
            임베딩 배열 또는 None
        """
        if character_id not in self._index:
            return None

        entry = self._index[character_id]
        if not entry.embedding_file:
            return None

        embedding_path = self.cache_dir / character_id / entry.embedding_file

        if embedding_path.exists():
            try:
                return np.load(str(embedding_path))
            except Exception as e:
                print(f"임베딩 로드 실패: {e}")

        return None

    def set_embedding(
        self,
        character_id: str,
        embedding: np.ndarray,
    ) -> str:
        """
        임베딩 캐시 저장

        Args:
            character_id: 캐릭터 ID
            embedding: 임베딩 배열

        Returns:
            저장된 임베딩 경로
        """
        char_dir = self.cache_dir / character_id
        char_dir.mkdir(parents=True, exist_ok=True)

        embedding_path = char_dir / "embedding.npy"
        np.save(str(embedding_path), embedding)

        # 인덱스 업데이트
        if character_id in self._index:
            self._index[character_id].embedding_file = "embedding.npy"
            self._save_index()

        return str(embedding_path)

    def exists(self, character_id: str) -> bool:
        """캐시 존재 여부"""
        return character_id in self._index

    def list_cached(self) -> list[CacheEntry]:
        """캐시된 캐릭터 목록"""
        return list(self._index.values())

    def delete(self, character_id: str) -> bool:
        """
        캐시 삭제

        Args:
            character_id: 캐릭터 ID

        Returns:
            삭제 성공 여부
        """
        if character_id not in self._index:
            return False

        char_dir = self.cache_dir / character_id

        # 디렉토리 삭제
        if char_dir.exists():
            import shutil
            shutil.rmtree(char_dir)

        # 인덱스에서 제거
        del self._index[character_id]
        self._save_index()

        return True

    def clear_all(self):
        """모든 캐시 삭제"""
        for character_id in list(self._index.keys()):
            self.delete(character_id)

    def get_cache_size(self) -> dict:
        """캐시 크기 정보"""
        total_size = 0
        file_count = 0

        for char_dir in self.cache_dir.iterdir():
            if char_dir.is_dir():
                for file in char_dir.iterdir():
                    if file.is_file():
                        total_size += file.stat().st_size
                        file_count += 1

        return {
            "total_bytes": total_size,
            "total_mb": total_size / (1024 * 1024),
            "file_count": file_count,
            "character_count": len(self._index),
        }

    def generate_character_id(self, name: str, description: str = "") -> str:
        """캐릭터 이름으로 ID 생성"""
        base = f"{name}_{description[:50]}"
        return hashlib.md5(base.encode()).hexdigest()[:12]
