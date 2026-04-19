"""
IP-Adapter Manager - 캐릭터 일관성 유지

참조 이미지 기반 캐릭터 일관성 관리
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class CharacterEmbedding:
    """캐릭터 임베딩 정보"""
    character_id: str
    name: str = ""
    embedding_path: Path = None
    reference_image_path: Path = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "embedding_path": str(self.embedding_path) if self.embedding_path else "",
            "reference_image_path": str(self.reference_image_path) if self.reference_image_path else "",
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterEmbedding":
        return cls(
            character_id=data["character_id"],
            name=data.get("name", ""),
            embedding_path=Path(data["embedding_path"]) if data.get("embedding_path") else None,
            reference_image_path=Path(data["reference_image_path"]) if data.get("reference_image_path") else None,
            created_at=data.get("created_at", "")
        )


class IPAdapterManager:
    """
    IP-Adapter 캐릭터 일관성 관리자

    캐릭터 참조 이미지를 관리하고
    이미지 생성 시 일관성 유지
    """

    def __init__(self, cache_dir: str = "data/ip_adapter_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._embeddings: Dict[str, CharacterEmbedding] = {}

    async def register_character(
        self,
        character_id: str,
        name: str,
        reference_image: Path
    ) -> CharacterEmbedding:
        """
        캐릭터 등록

        Args:
            character_id: 캐릭터 ID
            name: 캐릭터 이름
            reference_image: 참조 이미지 경로

        Returns:
            CharacterEmbedding
        """
        embedding = CharacterEmbedding(
            character_id=character_id,
            name=name,
            embedding_path=self.cache_dir / f"{character_id}_embedding.json",
            reference_image_path=reference_image,
            created_at=datetime.now().isoformat()
        )

        self._embeddings[character_id] = embedding
        await self._save_embedding(embedding)

        logger.info(f"Character registered: {character_id} ({name})")
        return embedding

    def get_embedding(self, character_id: str) -> Optional[CharacterEmbedding]:
        """캐릭터 임베딩 조회"""
        return self._embeddings.get(character_id)

    def has_embedding(self, character_id: str) -> bool:
        """임베딩 존재 여부"""
        return character_id in self._embeddings

    def apply_to_prompt(self, prompt: str, character_ids: List[str]) -> str:
        """
        프롬프트에 일관성 태그 추가

        Args:
            prompt: 원본 프롬프트
            character_ids: 캐릭터 ID 목록

        Returns:
            수정된 프롬프트
        """
        if not character_ids:
            return prompt

        consistency_tags = [
            "consistent character design",
            "same face, same appearance",
            "character consistency"
        ]

        # 등록된 캐릭터면 추가 태그
        for cid in character_ids:
            if self.has_embedding(cid):
                consistency_tags.append(f"same character as reference")

        return f"{prompt}, {', '.join(consistency_tags)}"

    def get_reference_images(self, character_ids: List[str]) -> List[Path]:
        """
        참조 이미지 목록 조회

        Args:
            character_ids: 캐릭터 ID 목록

        Returns:
            참조 이미지 경로 목록
        """
        images = []
        for cid in character_ids:
            emb = self._embeddings.get(cid)
            if emb and emb.reference_image_path:
                if Path(emb.reference_image_path).exists():
                    images.append(Path(emb.reference_image_path))
        return images

    def get_ip_adapter_params(
        self,
        character_ids: List[str]
    ) -> Dict[str, Any]:
        """
        API 호출용 IP-Adapter 파라미터

        Args:
            character_ids: 캐릭터 ID 목록

        Returns:
            IP-Adapter 파라미터
        """
        ref_images = self.get_reference_images(character_ids)

        if not ref_images:
            return {}

        return {
            "init_image": str(ref_images[0]),  # 첫 번째 참조 이미지
            "init_image_mode": "IMAGE_STRENGTH",
            "image_strength": 0.35,  # 참조 이미지 영향도
            "style_preset": "3d-model"
        }

    async def _save_embedding(self, embedding: CharacterEmbedding) -> None:
        """임베딩 저장"""
        path = self.cache_dir / f"{embedding.character_id}.json"
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(embedding.to_dict(), ensure_ascii=False, indent=2))

    async def load_all(self) -> None:
        """저장된 모든 임베딩 로드"""
        if not self.cache_dir.exists():
            return

        for path in self.cache_dir.glob("*.json"):
            try:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    emb = CharacterEmbedding.from_dict(data)
                    self._embeddings[emb.character_id] = emb
                    logger.debug(f"Loaded embedding: {emb.character_id}")
            except Exception as e:
                logger.error(f"Failed to load embedding {path}: {e}")

    def list_characters(self) -> List[str]:
        """등록된 캐릭터 ID 목록"""
        return list(self._embeddings.keys())


# 싱글톤
_manager: Optional[IPAdapterManager] = None


def get_ip_adapter_manager() -> IPAdapterManager:
    """IP-Adapter 매니저 싱글톤"""
    global _manager
    if _manager is None:
        _manager = IPAdapterManager()
    return _manager
