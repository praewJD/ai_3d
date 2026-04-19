"""
Manage Preset Use Case

스타일 프리셋 관리 비즈니스 로직을 캡슐화
"""
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from ..entities.preset import StylePreset
from ..interfaces.repository import IPresetRepository


class PresetAction(str, Enum):
    """프리셋 액션"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DUPLICATE = "duplicate"


@dataclass
class ManagePresetRequest:
    """프리셋 관리 요청"""
    action: PresetAction
    preset: Optional[StylePreset] = None
    preset_id: Optional[str] = None
    new_name: Optional[str] = None


@dataclass
class ManagePresetResponse:
    """프리셋 관리 응답"""
    success: bool
    message: str = ""
    preset: Optional[StylePreset] = None
    presets: Optional[List[StylePreset]] = None


class ManagePresetUseCase:
    """
    프리셋 관리 유스케이스

    Responsibility:
    - 프리셋 CRUD 작업
    - 프리셋 복제
    - 프리셋 검증
    """

    def __init__(self, preset_repository: IPresetRepository):
        self._preset_repository = preset_repository

    async def execute(self, request: ManagePresetRequest) -> ManagePresetResponse:
        """
        프리셋 관리 실행

        Args:
            request: 프리셋 관리 요청

        Returns:
            ManagePresetResponse: 처리 결과
        """
        if request.action == PresetAction.CREATE:
            return await self._create_preset(request.preset)

        elif request.action == PresetAction.UPDATE:
            return await self._update_preset(request.preset)

        elif request.action == PresetAction.DELETE:
            return await self._delete_preset(request.preset_id)

        elif request.action == PresetAction.DUPLICATE:
            return await self._duplicate_preset(request.preset_id, request.new_name)

        return ManagePresetResponse(
            success=False,
            message=f"알 수 없는 액션: {request.action}"
        )

    async def _create_preset(self, preset: StylePreset) -> ManagePresetResponse:
        """프리셋 생성"""
        if not preset or not preset.name:
            return ManagePresetResponse(
                success=False,
                message="프리셋 이름이 필요합니다."
            )

        # 이름 중복 확인
        existing = await self._preset_repository.find_by_name(preset.name)
        if existing:
            return ManagePresetResponse(
                success=False,
                message=f"이미 존재하는 프리셋 이름입니다: {preset.name}"
            )

        saved = await self._preset_repository.save(preset)
        return ManagePresetResponse(
            success=True,
            message="프리셋이 생성되었습니다.",
            preset=saved
        )

    async def _update_preset(self, preset: StylePreset) -> ManagePresetResponse:
        """프리셋 수정"""
        if not preset or not preset.id:
            return ManagePresetResponse(
                success=False,
                message="수정할 프리셋 ID가 필요합니다."
            )

        existing = await self._preset_repository.find_by_id(preset.id)
        if not existing:
            return ManagePresetResponse(
                success=False,
                message=f"프리셋을 찾을 수 없습니다: {preset.id}"
            )

        updated = await self._preset_repository.save(preset)
        return ManagePresetResponse(
            success=True,
            message="프리셋이 수정되었습니다.",
            preset=updated
        )

    async def _delete_preset(self, preset_id: str) -> ManagePresetResponse:
        """프리셋 삭제"""
        if not preset_id:
            return ManagePresetResponse(
                success=False,
                message="삭제할 프리셋 ID가 필요합니다."
            )

        existing = await self._preset_repository.find_by_id(preset_id)
        if not existing:
            return ManagePresetResponse(
                success=False,
                message=f"프리셋을 찾을 수 없습니다: {preset_id}"
            )

        await self._preset_repository.delete(preset_id)
        return ManagePresetResponse(
            success=True,
            message="프리셋이 삭제되었습니다."
        )

    async def _duplicate_preset(
        self,
        preset_id: str,
        new_name: str
    ) -> ManagePresetResponse:
        """프리셋 복제"""
        if not preset_id:
            return ManagePresetResponse(
                success=False,
                message="복제할 프리셋 ID가 필요합니다."
            )

        existing = await self._preset_repository.find_by_id(preset_id)
        if not existing:
            return ManagePresetResponse(
                success=False,
                message=f"프리셋을 찾을 수 없습니다: {preset_id}"
            )

        # 새 이름 생성
        if not new_name:
            new_name = f"{existing.name} (복사)"

        # 복제된 프리셋 생성
        duplicated = StylePreset(
            name=new_name,
            description=existing.description,
            sd_settings=existing.sd_settings,
            ip_adapter_settings=existing.ip_adapter_settings,
            lora_settings=existing.lora_settings,
            video_settings=existing.video_settings
        )

        saved = await self._preset_repository.save(duplicated)
        return ManagePresetResponse(
            success=True,
            message=f"프리셋이 복제되었습니다: {new_name}",
            preset=saved
        )

    async def list_presets(self) -> List[StylePreset]:
        """모든 프리셋 목록 조회"""
        return await self._preset_repository.find_all()

    async def get_default_preset(self) -> Optional[StylePreset]:
        """기본 프리셋 조회"""
        return await self._preset_repository.find_default()
