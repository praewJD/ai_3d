"""
Character Identity Engine - 캐릭터 일관성 유지 엔진

LoRA + Reference + Seed + Token Compression 통합 관리
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class CharacterIdentity:
    """캐릭터 정체성 데이터"""
    character_id: str
    lora_path: str  # LoRA 파일 경로
    reference_image: str  # 참조 이미지 경로
    core_tokens: str  # 핵심 토큰 (압축된 descriptor)
    seed: int = 12345

    # 렌더링 파라미터
    lora_weight: float = 0.85
    reference_strength: float = 0.7
    controlnet_weight: float = 0.75

    # 네거티브 프롬프트
    negative_prompt: str = "blurry, deformed, bad anatomy, different person, extra limbs, low quality, distorted face"

    # 메타데이터
    name: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "lora_path": self.lora_path,
            "reference_image": self.reference_image,
            "core_tokens": self.core_tokens,
            "seed": self.seed,
            "lora_weight": self.lora_weight,
            "reference_strength": self.reference_strength,
            "controlnet_weight": self.controlnet_weight,
            "negative_prompt": self.negative_prompt,
            "name": self.name,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterIdentity":
        return cls(**data)


class CharacterIdentityEngine:
    """
    캐릭터 정체성 엔진

    캐릭터 등록 → LoRA/Reference/Seed/Token 통합 관리
    """

    # 기본 파라미터 범위 (벗어나면 일관성 깨짐)
    PARAM_RANGES = {
        "lora_weight": (0.8, 0.9),
        "reference_strength": (0.6, 0.75),
        "controlnet_weight": (0.7, 0.8)
    }

    def __init__(self, cache_dir: str = "data/character_identity"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.characters: Dict[str, CharacterIdentity] = {}

    def register(
        self,
        character_id: str,
        lora_path: str,
        reference_image: str,
        core_tokens: str,
        seed: int = 12345,
        name: str = "",
        description: str = "",
        lora_weight: float = 0.85,
        reference_strength: float = 0.7,
        controlnet_weight: float = 0.75
    ) -> CharacterIdentity:
        """
        캐릭터 등록

        Args:
            character_id: 캐릭터 ID (예: "char_hero")
            lora_path: LoRA 파일 경로 (예: "lora/raven_v1.safetensors")
            reference_image: 참조 이미지 경로 (예: "assets/ref/raven.png")
            core_tokens: 핵심 토큰 (예: "hooded hero, blue aura, pale face")
            seed: 고정 시드
            name: 캐릭터 이름
            description: 캐릭터 설명

        Returns:
            CharacterIdentity
        """
        # 파라미터 범위 검증
        self._validate_params(lora_weight, reference_strength, controlnet_weight)

        identity = CharacterIdentity(
            character_id=character_id,
            lora_path=lora_path,
            reference_image=reference_image,
            core_tokens=core_tokens,
            seed=seed,
            name=name,
            description=description,
            lora_weight=lora_weight,
            reference_strength=reference_strength,
            controlnet_weight=controlnet_weight
        )

        self.characters[character_id] = identity
        logger.info(f"Registered character: {character_id}")

        return identity

    def get(self, character_id: str) -> Optional[CharacterIdentity]:
        """캐릭터 정체성 조회"""
        return self.characters.get(character_id)

    def get_render_config(self, character_id: str) -> Dict[str, Any]:
        """
        렌더링 설정 반환

        Returns:
            렌더링에 필요한 모든 설정
        """
        identity = self.get(character_id)
        if not identity:
            raise ValueError(f"Character not found: {character_id}")

        return {
            "lora": identity.lora_path,
            "lora_weight": identity.lora_weight,
            "reference_image": identity.reference_image,
            "reference_strength": identity.reference_strength,
            "seed": identity.seed,
            "controlnet_weight": identity.controlnet_weight,
            "negative_prompt": identity.negative_prompt,
            "core_tokens": identity.core_tokens
        }

    def _validate_params(self, lora_weight: float, ref_strength: float, cn_weight: float):
        """파라미터 범위 검증"""
        ranges = self.PARAM_RANGES

        if not (ranges["lora_weight"][0] <= lora_weight <= ranges["lora_weight"][1]):
            logger.warning(f"lora_weight {lora_weight} outside recommended range {ranges['lora_weight']}")

        if not (ranges["reference_strength"][0] <= ref_strength <= ranges["reference_strength"][1]):
            logger.warning(f"reference_strength {ref_strength} outside recommended range {ranges['reference_strength']}")

        if not (ranges["controlnet_weight"][0] <= cn_weight <= ranges["controlnet_weight"][1]):
            logger.warning(f"controlnet_weight {cn_weight} outside recommended range {ranges['controlnet_weight']}")

    def save(self, path: str = None):
        """캐릭터 DB 저장"""
        path = path or str(self.cache_dir / "characters.json")
        data = {cid: char.to_dict() for cid, char in self.characters.items()}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.characters)} characters to {path}")

    def load(self, path: str = None):
        """캐릭터 DB 로드"""
        path = path or str(self.cache_dir / "characters.json")
        if not Path(path).exists():
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.characters = {
            cid: CharacterIdentity.from_dict(char_data)
            for cid, char_data in data.items()
        }
        logger.info(f"Loaded {len(self.characters)} characters from {path}")

    def list_characters(self) -> List[str]:
        """등록된 캐릭터 목록"""
        return list(self.characters.keys())
