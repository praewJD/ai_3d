"""
Presets API Routes

스타일 프리셋 관리
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from core.application.preset_service import PresetApplicationService
from core.domain.entities.preset import StylePreset
from interfaces.api.dependencies import get_preset_service


router = APIRouter()


from pydantic import BaseModel, Field


class CreatePresetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = ""
    base_prompt: str = ""
    negative_prompt: str = "ugly, blurry, low quality"
    seed: int = -1
    cfg_scale: float = 7.5
    steps: int = 30
    sampler: str = "dpmpp_2m"
    ip_adapter_ref: Optional[str] = None
    ip_adapter_scale: float = 0.8


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    base_prompt: str
    negative_prompt: str
    seed: int
    cfg_scale: float
    steps: int
    sampler: str
    ip_adapter_ref: Optional[str]
    ip_adapter_scale: float
    is_default: bool


@router.get("", response_model=List[PresetResponse])
async def list_presets(
    service: PresetApplicationService = Depends(get_preset_service)
):
    """모든 프리셋 목록"""
    presets = await service.list_presets()
    return [
        PresetResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            base_prompt=p.base_prompt,
            negative_prompt=p.negative_prompt,
            seed=p.seed,
            cfg_scale=p.cfg_scale,
            steps=p.steps,
            sampler=p.sampler,
            ip_adapter_ref=p.ip_adapter_ref,
            ip_adapter_scale=p.ip_adapter_scale,
            is_default=p.is_default
        )
        for p in presets
    ]


@router.get("/defaults", response_model=List[PresetResponse])
async def list_default_presets(
    service: PresetApplicationService = Depends(get_preset_service)
):
    """기본 프리셋 목록"""
    presets = await service.list_default_presets()
    return [
        PresetResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            base_prompt=p.base_prompt,
            negative_prompt=p.negative_prompt,
            seed=p.seed,
            cfg_scale=p.cfg_scale,
            steps=p.steps,
            sampler=p.sampler,
            ip_adapter_ref=p.ip_adapter_ref,
            ip_adapter_scale=p.ip_adapter_scale,
            is_default=p.is_default
        )
        for p in presets
    ]


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: str,
    service: PresetApplicationService = Depends(get_preset_service)
):
    """프리셋 조회"""
    preset = await service.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    return PresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        base_prompt=preset.base_prompt,
        negative_prompt=preset.negative_prompt,
        seed=preset.seed,
        cfg_scale=preset.cfg_scale,
        steps=preset.steps,
        sampler=preset.sampler,
        ip_adapter_ref=preset.ip_adapter_ref,
        ip_adapter_scale=preset.ip_adapter_scale,
        is_default=preset.is_default
    )


@router.post("", response_model=PresetResponse)
async def create_preset(
    request: CreatePresetRequest,
    service: PresetApplicationService = Depends(get_preset_service)
):
    """새 프리셋 생성"""
    preset = await service.create_preset(
        name=request.name,
        description=request.description,
        base_prompt=request.base_prompt,
        negative_prompt=request.negative_prompt,
        seed=request.seed,
        cfg_scale=request.cfg_scale,
        steps=request.steps,
        sampler=request.sampler,
        ip_adapter_ref=request.ip_adapter_ref,
        ip_adapter_scale=request.ip_adapter_scale
    )

    return PresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        base_prompt=preset.base_prompt,
        negative_prompt=preset.negative_prompt,
        seed=preset.seed,
        cfg_scale=preset.cfg_scale,
        steps=preset.steps,
        sampler=preset.sampler,
        ip_adapter_ref=preset.ip_adapter_ref,
        ip_adapter_scale=preset.ip_adapter_scale,
        is_default=preset.is_default
    )


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: str,
    request: CreatePresetRequest,
    service: PresetApplicationService = Depends(get_preset_service)
):
    """프리셋 수정"""
    preset = await service.update_preset(
        preset_id,
        name=request.name,
        description=request.description,
        base_prompt=request.base_prompt,
        negative_prompt=request.negative_prompt,
        seed=request.seed,
        cfg_scale=request.cfg_scale,
        steps=request.steps,
        ip_adapter_ref=request.ip_adapter_ref,
        ip_adapter_scale=request.ip_adapter_scale
    )
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    return PresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        base_prompt=preset.base_prompt,
        negative_prompt=preset.negative_prompt,
        seed=preset.seed,
        cfg_scale=preset.cfg_scale,
        steps=preset.steps,
        sampler=preset.sampler,
        ip_adapter_ref=preset.ip_adapter_ref,
        ip_adapter_scale=preset.ip_adapter_scale,
        is_default=preset.is_default
    )


@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: str,
    service: PresetApplicationService = Depends(get_preset_service)
):
    """프리셋 삭제"""
    deleted = await service.delete_preset(preset_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete default preset or preset not found"
        )
    return {"status": "deleted", "preset_id": preset_id}


@router.post("/{preset_id}/clone")
async def clone_preset(
    preset_id: str,
    new_name: str,
    service: PresetApplicationService = Depends(get_preset_service)
):
    """프리셋 복제"""
    preset = await service.clone_preset(preset_id, new_name)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    return {"status": "cloned", "new_preset_id": preset.id}
