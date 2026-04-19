"""
Character Asset - 캐릭터 에셋 관리

캐릭터 저장, 조회, 검색, IP-Adapter 임베딩 관리
"""
import json
import asyncio
import aiofiles
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class CharacterAsset:
    """
    캐릭터 에셋 데이터 클래스

    캐릭터의 시각적 일관성을 유지하기 위한 모든 정보 포함
    """
    id: str
    name: str
    description: str

    # 이미지 경로
    reference_image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None

    # IP-Adapter 임베딩 (스타일 일관성)
    ip_adapter_embedding: Optional[str] = None

    # 외형 정보
    appearance: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "age": "adult",
    #     "gender": "female",
    #     "body_type": "slim",
    #     "hair": "long black hair",
    #     "clothing": ["white dress"],
    #     "accessories": ["earrings"],
    #     "distinctive_features": ["blue eyes"]
    # }

    # 성격 및 능력
    personality: List[str] = field(default_factory=list)
    powers: List[str] = field(default_factory=list)

    # 메타데이터
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 사용 통계
    usage_count: int = 0
    last_used_at: Optional[str] = None

    def update_timestamp(self) -> None:
        """수정 시간 업데이트"""
        self.updated_at = datetime.now().isoformat()

    def increment_usage(self) -> None:
        """사용 횟수 증가"""
        self.usage_count += 1
        self.last_used_at = datetime.now().isoformat()

    def to_prompt_segment(self) -> str:
        """프롬프트용 문자열 변환"""
        parts = []

        # 기본 정보
        if self.appearance.get("gender"):
            parts.append(self.appearance["gender"])
        if self.appearance.get("age"):
            parts.append(self.appearance["age"])
        if self.appearance.get("body_type"):
            parts.append(f"{self.appearance['body_type']} build")

        # 외형 상세
        if self.appearance.get("hair"):
            parts.append(self.appearance["hair"])
        if self.appearance.get("clothing"):
            parts.append(f"wearing {', '.join(self.appearance['clothing'])}")
        if self.appearance.get("accessories"):
            parts.append(', '.join(self.appearance["accessories"]))
        if self.appearance.get("distinctive_features"):
            parts.append(', '.join(self.appearance["distinctive_features"]))

        return ', '.join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterAsset":
        """딕셔너리에서 생성"""
        return cls(**data)

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        appearance: Dict[str, Any] = None,
        **kwargs
    ) -> "CharacterAsset":
        """새 캐릭터 생성"""
        # ID 생성
        id_base = f"{name}_{datetime.now().isoformat()}"
        char_id = f"char_{hashlib.md5(id_base.encode()).hexdigest()[:8]}"

        return cls(
            id=char_id,
            name=name,
            description=description,
            appearance=appearance or {},
            **kwargs
        )


class CharacterAssetManager:
    """
    캐릭터 에셋 관리자

    기능:
    - CRUD 작업
    - 검색 및 필터링
    - IP-Adapter 임베딩 관리
    - 썸네일 연동
    """

    def __init__(self, base_path: str = "data/assets/characters"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 메모리 캐시
        self._cache: Dict[str, CharacterAsset] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """지연 로드"""
        if not self._loaded:
            await self.load_all()
            self._loaded = True

    def _get_asset_path(self, character_id: str) -> Path:
        """에셋 파일 경로"""
        return self.base_path / f"{character_id}.json"

    def _get_image_dir(self, character_id: str) -> Path:
        """이미지 디렉토리"""
        img_dir = self.base_path / character_id
        img_dir.mkdir(parents=True, exist_ok=True)
        return img_dir

    @staticmethod
    def generate_id(name: str) -> str:
        """이름 기반 ID 생성"""
        base = f"char_{name}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(base.encode()).hexdigest()[:12]

    # ============================================================
    # CRUD Operations
    # ============================================================

    async def save(self, character: CharacterAsset) -> CharacterAsset:
        """
        캐릭터 저장

        Args:
            character: 저장할 캐릭터

        Returns:
            저장된 캐릭터
        """
        character.update_timestamp()

        file_path = self._get_asset_path(character.id)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(character.to_dict(), ensure_ascii=False, indent=2))

        # 캐시 업데이트
        self._cache[character.id] = character

        logger.info(f"Character saved: {character.name} ({character.id})")
        return character

    async def get(self, character_id: str) -> Optional[CharacterAsset]:
        """
        캐릭터 조회

        Args:
            character_id: 캐릭터 ID

        Returns:
            캐릭터 또는 None
        """
        # 캐시 확인
        if character_id in self._cache:
            return self._cache[character_id]

        # 파일에서 로드
        file_path = self._get_asset_path(character_id)
        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
            character = CharacterAsset.from_dict(data)
            self._cache[character_id] = character
            return character

    async def delete(self, character_id: str) -> bool:
        """
        캐릭터 삭제

        Args:
            character_id: 캐릭터 ID

        Returns:
            삭제 성공 여부
        """
        file_path = self._get_asset_path(character_id)
        if not file_path.exists():
            return False

        # 파일 삭제
        file_path.unlink()

        # 이미지 디렉토리도 삭제
        img_dir = self.base_path / character_id
        if img_dir.exists():
            import shutil
            shutil.rmtree(img_dir)

        # 캐시에서 삭제
        if character_id in self._cache:
            del self._cache[character_id]

        logger.info(f"Character deleted: {character_id}")
        return True

    async def load_all(self) -> List[CharacterAsset]:
        """
        모든 캐릭터 로드

        Returns:
            모든 캐릭터 목록
        """
        characters = []

        for file_path in self.base_path.glob("*.json"):
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    character = CharacterAsset.from_dict(data)
                    characters.append(character)
                    self._cache[character.id] = character
            except Exception as e:
                logger.error(f"Failed to load character {file_path}: {e}")

        logger.info(f"Loaded {len(characters)} characters")
        return characters

    async def list_all(self) -> List[CharacterAsset]:
        """모든 캐릭터 목록"""
        await self._ensure_loaded()
        return list(self._cache.values())

    # ============================================================
    # Search Operations
    # ============================================================

    async def search(
        self,
        query: str = None,
        tags: List[str] = None,
        gender: str = None,
        age: str = None,
        limit: int = 50
    ) -> List[CharacterAsset]:
        """
        캐릭터 검색

        Args:
            query: 이름/설명 검색어
            tags: 태그 필터
            gender: 성별 필터
            age: 나이 필터
            limit: 최대 결과 수

        Returns:
            검색 결과
        """
        await self._ensure_loaded()

        results = list(self._cache.values())

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

        # 성별 필터
        if gender:
            results = [
                c for c in results
                if c.appearance.get("gender") == gender
            ]

        # 나이 필터
        if age:
            results = [
                c for c in results
                if c.appearance.get("age") == age
            ]

        # 사용 횟수 기준 정렬
        results.sort(key=lambda c: c.usage_count, reverse=True)

        return results[:limit]

    async def get_by_name(self, name: str) -> Optional[CharacterAsset]:
        """이름으로 캐릭터 찾기"""
        await self._ensure_loaded()

        for char in self._cache.values():
            if char.name.lower() == name.lower():
                return char
        return None

    async def get_popular(self, limit: int = 10) -> List[CharacterAsset]:
        """인기 캐릭터 (사용 빈도 기준)"""
        await self._ensure_loaded()

        sorted_chars = sorted(
            self._cache.values(),
            key=lambda c: c.usage_count,
            reverse=True
        )
        return sorted_chars[:limit]

    # ============================================================
    # Reference Image Management
    # ============================================================

    async def set_reference_image(
        self,
        character_id: str,
        image_path: str
    ) -> bool:
        """
        참조 이미지 설정

        Args:
            character_id: 캐릭터 ID
            image_path: 이미지 경로

        Returns:
            성공 여부
        """
        character = await self.get(character_id)
        if not character:
            return False

        # 이미지 복사
        img_dir = self._get_image_dir(character_id)
        src_path = Path(image_path)

        if not src_path.exists():
            logger.error(f"Image not found: {image_path}")
            return False

        import shutil
        dest_path = img_dir / f"reference{src_path.suffix}"
        shutil.copy2(src_path, dest_path)

        character.reference_image_path = str(dest_path)
        await self.save(character)

        return True

    async def get_reference_image(
        self,
        character_id: str
    ) -> Optional[str]:
        """참조 이미지 경로 조회"""
        character = await self.get(character_id)
        if character and character.reference_image_path:
            if Path(character.reference_image_path).exists():
                return character.reference_image_path
        return None

    # ============================================================
    # IP-Adapter Embedding
    # ============================================================

    async def set_ip_adapter_embedding(
        self,
        character_id: str,
        embedding_path: str
    ) -> bool:
        """
        IP-Adapter 임베딩 설정

        Args:
            character_id: 캐릭터 ID
            embedding_path: 임베딩 파일 경로

        Returns:
            성공 여부
        """
        character = await self.get(character_id)
        if not character:
            return False

        # 임베딩 복사
        img_dir = self._get_image_dir(character_id)
        src_path = Path(embedding_path)

        if not src_path.exists():
            logger.error(f"Embedding not found: {embedding_path}")
            return False

        import shutil
        dest_path = img_dir / f"embedding{src_path.suffix}"
        shutil.copy2(src_path, dest_path)

        character.ip_adapter_embedding = str(dest_path)
        await self.save(character)

        return True

    async def get_ip_adapter_embedding(
        self,
        character_id: str
    ) -> Optional[str]:
        """IP-Adapter 임베딩 경로 조회"""
        character = await self.get(character_id)
        if character and character.ip_adapter_embedding:
            if Path(character.ip_adapter_embedding).exists():
                return character.ip_adapter_embedding
        return None

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        await self._ensure_loaded()

        chars = list(self._cache.values())

        return {
            "total": len(chars),
            "with_reference_images": len([
                c for c in chars if c.reference_image_path
            ]),
            "with_embeddings": len([
                c for c in chars if c.ip_adapter_embedding
            ]),
            "total_usage": sum(c.usage_count for c in chars),
            "by_gender": self._count_by_field(chars, "gender"),
            "by_age": self._count_by_field(chars, "age"),
        }

    def _count_by_field(
        self,
        characters: List[CharacterAsset],
        field: str
    ) -> Dict[str, int]:
        """필드별 카운트"""
        counts: Dict[str, int] = {}
        for char in characters:
            value = char.appearance.get(field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts
