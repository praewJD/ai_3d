"""
Character Library - 캐릭터 라이브러리 관리

캐릭터 저장, 로드, 검색 기능
"""
import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import aiofiles

from core.domain.entities.character.character import (
    Character,
    CharacterType,
    CharacterRole,
    CharacterGender
)

logger = logging.getLogger(__name__)


class CharacterLibrary:
    """
    캐릭터 라이브러리

    기능:
    - 캐릭터 CRUD
    - 시리즈별 캐릭터 관리
    - 캐릭터 검색
    - 참조 이미지 관리
    """

    DEFAULT_LIBRARY_PATH = "data/characters"

    def __init__(self, library_path: str = None):
        self.library_path = Path(library_path or self.DEFAULT_LIBRARY_PATH)
        self.library_path.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시
        self._characters: Dict[str, Character] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """지연 로드"""
        if not self._loaded:
            await self.load_all()
            self._loaded = True

    # ============================================================
    # CRUD Operations
    # ============================================================

    async def save(self, character: Character) -> Character:
        """
        캐릭터 저장

        Args:
            character: 저장할 캐릭터

        Returns:
            저장된 캐릭터
        """
        await self._ensure_loaded()

        # 타입별 디렉토리
        type_dir = self.library_path / character.type.value
        type_dir.mkdir(parents=True, exist_ok=True)

        # 파일 경로
        file_path = type_dir / f"{character.id}.json"

        # 타임스탬프 업데이트
        character.update_timestamp()

        # 저장
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(character.model_dump_json(indent=2))

        # 캐시 업데이트
        self._characters[character.id] = character

        logger.info(f"Character saved: {character.name} ({character.id})")
        return character

    async def load(self, character_id: str) -> Optional[Character]:
        """
        캐릭터 로드

        Args:
            character_id: 캐릭터 ID

        Returns:
            캐릭터 또는 None
        """
        # 캐시 확인
        if character_id in self._characters:
            return self._characters[character_id]

        # 파일에서 로드
        for char_type in CharacterType:
            file_path = self.library_path / char_type.value / f"{character_id}.json"
            if file_path.exists():
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    character = Character(**data)
                    self._characters[character_id] = character
                    return character

        return None

    async def delete(self, character_id: str) -> bool:
        """
        캐릭터 삭제

        Args:
            character_id: 캐릭터 ID

        Returns:
            삭제 성공 여부
        """
        for char_type in CharacterType:
            file_path = self.library_path / char_type.value / f"{character_id}.json"
            if file_path.exists():
                file_path.unlink()

                # 캐시에서도 삭제
                if character_id in self._characters:
                    del self._characters[character_id]

                logger.info(f"Character deleted: {character_id}")
                return True

        return False

    async def load_all(self) -> List[Character]:
        """
        모든 캐릭터 로드

        Returns:
            모든 캐릭터 목록
        """
        characters = []

        for char_type in CharacterType:
            type_dir = self.library_path / char_type.value
            if not type_dir.exists():
                continue

            for file_path in type_dir.glob("*.json"):
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                        character = Character(**data)
                        characters.append(character)
                        self._characters[character.id] = character
                except Exception as e:
                    logger.error(f"Failed to load character {file_path}: {e}")

        logger.info(f"Loaded {len(characters)} characters")
        return characters

    # ============================================================
    # Query Operations
    # ============================================================

    async def get_by_name(self, name: str) -> Optional[Character]:
        """이름으로 캐릭터 찾기"""
        await self._ensure_loaded()

        for char in self._characters.values():
            if char.name.lower() == name.lower():
                return char
        return None

    async def get_by_type(self, char_type: CharacterType) -> List[Character]:
        """타입별 캐릭터 목록"""
        await self._ensure_loaded()

        return [
            char for char in self._characters.values()
            if char.type == char_type
        ]

    async def get_protagonists(self) -> List[Character]:
        """주인공 목록"""
        return await self.get_by_type(CharacterType.PROTAGONIST)

    async def get_supporting(self) -> List[Character]:
        """조연 목록"""
        return await self.get_by_type(CharacterType.SUPPORTING)

    async def get_animals(self) -> List[Character]:
        """동물 캐릭터 목록"""
        return await self.get_by_type(CharacterType.ANIMAL)

    async def search(
        self,
        query: str = None,
        char_type: CharacterType = None,
        role: CharacterRole = None,
        tags: List[str] = None
    ) -> List[Character]:
        """
        캐릭터 검색

        Args:
            query: 이름/설명 검색어
            char_type: 캐릭터 타입 필터
            role: 역할 필터
            tags: 태그 필터

        Returns:
            검색 결과
        """
        await self._ensure_loaded()

        results = list(self._characters.values())

        # 타입 필터
        if char_type:
            results = [c for c in results if c.type == char_type]

        # 역할 필터
        if role:
            results = [c for c in results if c.role == role]

        # 텍스트 검색
        if query:
            query_lower = query.lower()
            results = [
                c for c in results
                if query_lower in c.name.lower()
                or query_lower in c.description.lower()
            ]

        # 태그 필터
        if tags:
            results = [
                c for c in results
                if any(tag in c.tags for tag in tags)
            ]

        return results

    async def get_episode_characters(self, episode_id: str) -> List[Character]:
        """
        특정 에피소드에 등장하는 캐릭터

        Args:
            episode_id: 에피소드 ID

        Returns:
            캐릭터 목록
        """
        await self._ensure_loaded()

        return [
            char for char in self._characters.values()
            if episode_id in char.episodes
        ]

    # ============================================================
    # Batch Operations
    # ============================================================

    async def save_batch(self, characters: List[Character]) -> List[Character]:
        """여러 캐릭터 일괄 저장"""
        saved = []
        for char in characters:
            saved.append(await self.save(char))
        return saved

    async def import_from_dict(self, data: Dict[str, Any]) -> Character:
        """딕셔너리에서 캐릭터 import"""
        character = Character(**data)
        return await self.save(character)

    async def export_to_dict(self, character_id: str) -> Optional[Dict[str, Any]]:
        """캐릭터를 딕셔너리로 export"""
        character = await self.load(character_id)
        if character:
            return character.model_dump()
        return None

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """라이브러리 통계"""
        await self._ensure_loaded()

        chars = list(self._characters.values())

        return {
            "total": len(chars),
            "by_type": {
                char_type.value: len([c for c in chars if c.type == char_type])
                for char_type in CharacterType
            },
            "by_role": {
                role.value: len([c for c in chars if c.role == role])
                for role in CharacterRole
            },
            "with_reference_images": len([
                c for c in chars if c.reference_image_path
            ])
        }

    # ============================================================
    # Reference Image Management
    # ============================================================

    async def set_reference_image(
        self,
        character_id: str,
        image_path: str,
        image_type: str = "main"
    ) -> bool:
        """
        참조 이미지 설정

        Args:
            character_id: 캐릭터 ID
            image_path: 이미지 경로
            image_type: 이미지 타입 (main, front, side, expression 등)

        Returns:
            성공 여부
        """
        character = await self.load(character_id)
        if not character:
            return False

        if image_type == "main":
            character.reference_image_path = image_path
        else:
            character.reference_images[image_type] = image_path

        await self.save(character)
        return True

    async def get_reference_images(
        self,
        character_id: str
    ) -> Dict[str, str]:
        """
        캐릭터의 모든 참조 이미지

        Returns:
            이미지 타입별 경로
        """
        character = await self.load(character_id)
        if not character:
            return {}

        images = {}
        if character.reference_image_path:
            images["main"] = character.reference_image_path
        images.update(character.reference_images)

        return images


# ============================================================
# Singleton
# ============================================================

_library_instance: Optional[CharacterLibrary] = None


def get_character_library() -> CharacterLibrary:
    """캐릭터 라이브러리 싱글톤"""
    global _library_instance
    if _library_instance is None:
        _library_instance = CharacterLibrary()
    return _library_instance
