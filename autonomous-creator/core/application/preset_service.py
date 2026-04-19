"""
Preset Application Service

스타일 프리셋 관리
"""
from typing import List, Optional

from core.domain.entities.preset import StylePreset, DEFAULT_PRESETS
from infrastructure.persistence.repositories.preset_repo import PresetRepository


class PresetApplicationService:
    """
    프리셋 애플리케이션 서비스

    - 프리셋 CRUD
    - 기본 프리셋 관리
    """

    def __init__(self, preset_repo: PresetRepository):
        self.preset_repo = preset_repo

    async def initialize_defaults(self) -> int:
        """기본 프리셋 초기화"""
        return await self.preset_repo.initialize_defaults()

    async def create_preset(
        self,
        name: str,
        description: str = "",
        base_prompt: str = "",
        negative_prompt: str = "ugly, blurry, low quality",
        **kwargs
    ) -> StylePreset:
        """새 프리셋 생성"""
        preset = StylePreset(
            name=name,
            description=description,
            base_prompt=base_prompt,
            negative_prompt=negative_prompt,
            **kwargs
        )
        return await self.preset_repo.save(preset)

    async def get_preset(self, preset_id: str) -> Optional[StylePreset]:
        """프리셋 조회"""
        return await self.preset_repo.find_by_id(preset_id)

    async def get_preset_by_name(self, name: str) -> Optional[StylePreset]:
        """이름으로 프리셋 조회"""
        return await self.preset_repo.find_by_name(name)

    async def list_presets(self) -> List[StylePreset]:
        """모든 프리셋 목록"""
        return await self.preset_repo.find_all()

    async def list_default_presets(self) -> List[StylePreset]:
        """기본 프리셋 목록"""
        return await self.preset_repo.find_defaults()

    async def update_preset(
        self,
        preset_id: str,
        **updates
    ) -> Optional[StylePreset]:
        """프리셋 수정"""
        preset = await self.preset_repo.find_by_id(preset_id)
        if not preset:
            return None

        # 기본 프리셋은 수정 제한
        if preset.is_default:
            allowed = ["ip_adapter_ref", "ip_adapter_scale"]
            updates = {k: v for k, v in updates.items() if k in allowed}

        for key, value in updates.items():
            if hasattr(preset, key):
                setattr(preset, key, value)

        preset.update_timestamp()
        return await self.preset_repo.save(preset)

    async def delete_preset(self, preset_id: str) -> bool:
        """프리셋 삭제 (기본 프리셋 제외)"""
        return await self.preset_repo.delete(preset_id)

    async def clone_preset(
        self,
        preset_id: str,
        new_name: str
    ) -> Optional[StylePreset]:
        """프리셋 복제"""
        original = await self.preset_repo.find_by_id(preset_id)
        if not original:
            return None

        new_preset = StylePreset(
            name=new_name,
            description=f"Cloned from {original.name}",
            base_prompt=original.base_prompt,
            negative_prompt=original.negative_prompt,
            seed=-1,  # 새 시드
            cfg_scale=original.cfg_scale,
            steps=original.steps,
            sampler=original.sampler,
            ip_adapter_ref=original.ip_adapter_ref,
            ip_adapter_scale=original.ip_adapter_scale,
            lora_weights=original.lora_weights,
            lora_scale=original.lora_scale,
            is_default=False
        )
        return await self.preset_repo.save(new_preset)
