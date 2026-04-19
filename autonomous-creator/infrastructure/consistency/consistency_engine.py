"""
Consistency Engine

이미지/영상 생성 일관성 유지 엔진
"""
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
import re

from .character_db import CharacterDB, CharacterProfile
from .seed_manager import SeedManager


@dataclass
class SceneSpec:
    """장면 스펙"""
    id: str
    prompt: str
    characters: List[str] = field(default_factory=list)
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorySpec:
    """스토리 스펙"""
    id: str
    title: str
    scenes: List[SceneSpec] = field(default_factory=list)
    global_seed: Optional[int] = None


class ConsistencyEngine:
    """이미지/영상 생성 일관성 유지 엔진"""

    # 캐릭터 참조 패턴
    CHAR_PATTERN = re.compile(r"\[char:([a-zA-Z0-9_-]+)\]")

    def __init__(self, character_db: CharacterDB, seed_manager: SeedManager):
        self.character_db = character_db
        self.seed_manager = seed_manager

    def inject_character(self, prompt: str, char_id: str) -> str:
        """
        프롬프트에 캐릭터 descriptor 주입

        Args:
            prompt: 원본 프롬프트
            char_id: 캐릭터 ID

        Returns:
            캐릭터 descriptor와 seed가 추가된 프롬프트
        """
        descriptor = self.character_db.get_descriptor(char_id)
        seed = self.seed_manager.get_or_create_seed(char_id)

        if descriptor:
            prompt = f"{prompt}, {descriptor}"

        return f"{prompt}, seed:{seed}"

    def inject_characters(self, prompt: str, char_ids: List[str]) -> str:
        """
        여러 캐릭터 descriptor 주입

        Args:
            prompt: 원본 프롬프트
            char_ids: 캐릭터 ID 목록

        Returns:
            캐릭터 descriptor들이 추가된 프롬프트
        """
        descriptors = []
        seeds = []

        for char_id in char_ids:
            descriptor = self.character_db.get_descriptor(char_id)
            if descriptor:
                descriptors.append(descriptor)
            seed = self.seed_manager.get_or_create_seed(char_id)
            seeds.append((char_id, seed))

        if descriptors:
            prompt = f"{prompt}, {', '.join(descriptors)}"

        if seeds:
            seed_str = ", ".join(f"{cid}:{s}" for cid, s in seeds)
            prompt = f"{prompt}, seeds:[{seed_str}]"

        return prompt

    def resolve_character_refs(self, prompt: str) -> str:
        """
        프롬프트 내 캐릭터 참조 해결

        [char:char_id] 패턴을 캐릭터 descriptor로 교체
        """
        def replace_char_ref(match):
            char_id = match.group(1)
            descriptor = self.character_db.get_descriptor(char_id)
            seed = self.seed_manager.get_or_create_seed(char_id)
            if descriptor:
                return f"{descriptor}, seed:{seed}"
            return f"seed:{seed}"

        return self.CHAR_PATTERN.sub(replace_char_ref, prompt)

    def lock_scene_characters(self, scene_spec: SceneSpec) -> SceneSpec:
        """
        씬의 모든 캐릭터에 seed 고정

        Args:
            scene_spec: 장면 스펙

        Returns:
            캐릭터 seed가 고정된 장면 스펙
        """
        char_seeds = {}
        for char_id in scene_spec.characters:
            seed = self.seed_manager.get_or_create_seed(char_id)
            char_seeds[char_id] = seed

        scene_seed = self.seed_manager.create_scene_seed(
            scene_spec.id,
            char_seeds
        )

        scene_spec.seed = scene_seed
        scene_spec.metadata["char_seeds"] = char_seeds

        return scene_spec

    def lock_story_characters(self, story_spec: StorySpec) -> StorySpec:
        """
        스토리의 모든 캐릭터에 seed 고정

        Args:
            story_spec: 스토리 스펙

        Returns:
            모든 캐릭터 seed가 고정된 스토리 스펙
        """
        all_characters = set()
        for scene in story_spec.scenes:
            all_characters.update(scene.characters)

        for char_id in all_characters:
            self.seed_manager.get_or_create_seed(char_id)

        for scene in story_spec.scenes:
            self.lock_scene_characters(scene)

        return story_spec

    def validate_consistency(self, story_spec: StorySpec) -> List[str]:
        """
        일관성 검증

        Args:
            story_spec: 스토리 스펙

        Returns:
            오류 목록 (빈 목록이면 검증 통과)
        """
        errors = []

        for scene in story_spec.scenes:
            for char_id in scene.characters:
                profile = self.character_db.get_character(char_id)
                if not profile:
                    errors.append(
                        f"Scene '{scene.id}': Unknown character '{char_id}'"
                    )

        scene_ids = [s.id for s in story_spec.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            errors.append("Duplicate scene IDs found")

        for scene in story_spec.scenes:
            if not scene.prompt or not scene.prompt.strip():
                errors.append(f"Scene '{scene.id}': Empty prompt")

        return errors

    def get_character_seeds(self, story_spec: StorySpec) -> Dict[str, int]:
        """
        스토리의 모든 캐릭터 seed 반환

        Args:
            story_spec: 스토리 스펙

        Returns:
            캐릭터 ID -> seed 매핑
        """
        all_characters = set()
        for scene in story_spec.scenes:
            all_characters.update(scene.characters)

        return {
            char_id: self.seed_manager.get_or_create_seed(char_id)
            for char_id in all_characters
        }

    def generate_consistent_prompt(
        self,
        base_prompt: str,
        char_ids: List[str],
        scene_id: Optional[str] = None
    ) -> str:
        """
        일관성 있는 프롬프트 생성

        Args:
            base_prompt: 기본 프롬프트
            char_ids: 캐릭터 ID 목록
            scene_id: 장면 ID (선택)

        Returns:
            캐릭터 descriptor와 seed가 포함된 프롬프트
        """
        prompt = self.inject_characters(base_prompt, char_ids)

        if scene_id:
            char_seeds = {
                cid: self.seed_manager.get_or_create_seed(cid)
                for cid in char_ids
            }
            scene_seed = self.seed_manager.create_scene_seed(scene_id, char_seeds)
            prompt = f"{prompt}, scene_seed:{scene_seed}"

        return prompt

    def extract_characters_from_prompt(self, prompt: str) -> List[str]:
        """
        프롬프트에서 캐릭터 ID 추출

        Args:
            prompt: 프롬프트 텍스트

        Returns:
            추출된 캐릭터 ID 목록
        """
        return self.CHAR_PATTERN.findall(prompt)
