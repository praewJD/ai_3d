"""
Seed Manager

일관성 유지를 위한 Seed 관리
"""
from typing import Dict, Optional
import random


class SeedManager:
    """일관성 유지를 위한 Seed 관리"""

    def __init__(self):
        self.seeds: Dict[str, int] = {}
        self._locked_seeds: set = set()

    def get_or_create_seed(self, char_id: str) -> int:
        """
        캐릭터별 고정 seed 반환

        없으면 새로 생성하여 저장
        """
        if char_id in self.seeds:
            return self.seeds[char_id]

        seed = self._generate_deterministic_seed(char_id)
        self.seeds[char_id] = seed
        return seed

    def lock_seed(self, char_id: str, seed: int):
        """
        seed 강제 설정

        Args:
            char_id: 캐릭터 ID
            seed: 고정할 seed 값
        """
        self.seeds[char_id] = seed
        self._locked_seeds.add(char_id)

    def unlock_seed(self, char_id: str):
        """seed 잠금 해제"""
        self._locked_seeds.discard(char_id)

    def is_locked(self, char_id: str) -> bool:
        """seed 잠금 여부 확인"""
        return char_id in self._locked_seeds

    def get_seed(self, char_id: str) -> Optional[int]:
        """seed 조회 (없으면 None)"""
        return self.seeds.get(char_id)

    def set_seed(self, char_id: str, seed: int):
        """seed 설정 (lock 없이)"""
        self.seeds[char_id] = seed

    def remove_seed(self, char_id: str):
        """seed 제거"""
        self.seeds.pop(char_id, None)
        self._locked_seeds.discard(char_id)

    def clear_all(self):
        """모든 seed 제거"""
        self.seeds.clear()
        self._locked_seeds.clear()

    def get_all_seeds(self) -> Dict[str, int]:
        """모든 seed 반환 (복사본)"""
        return dict(self.seeds)

    def apply_to_generator(self, char_id: str, generator) -> int:
        """
        제너레이터에 seed 적용

        Args:
            char_id: 캐릭터 ID
            generator: 난수 생성기 (random.Random 또는 유사 객체)

        Returns:
            적용된 seed
        """
        seed = self.get_or_create_seed(char_id)
        if hasattr(generator, "seed"):
            generator.seed(seed)
        return seed

    def _generate_deterministic_seed(self, char_id: str) -> int:
        """결정론적 seed 생성"""
        hash_value = hash(char_id)
        return abs(hash_value) % 2147483647

    def create_scene_seed(self, scene_id: str, char_seeds: Dict[str, int]) -> int:
        """
        씬별 고유 seed 생성

        여러 캐릭터의 seed를 조합하여 씬 고유 seed 생성
        """
        combined = f"{scene_id}:{':'.join(f'{k}={v}' for k, v in sorted(char_seeds.items()))}"
        hash_value = hash(combined)
        return abs(hash_value) % 2147483647
