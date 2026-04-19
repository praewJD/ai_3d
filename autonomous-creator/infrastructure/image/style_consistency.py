"""
Style Consistency Manager

영상 전체의 스타일 일관성 관리
"""
from typing import List, Optional
from pathlib import Path

from .sd35_generator import SD35Generator
from .ip_adapter import IPAdapterHandler
from core.domain.entities.preset import StylePreset
from core.domain.entities.story import Scene
from config.settings import get_settings


class StyleConsistencyManager:
    """
    스타일 일관성 관리자

    전략:
    1. Seed 고정 → 기본 일관성
    2. IP-Adapter → 스타일 전이
    3. (Optional) LoRA → 캐릭터 고정
    """

    def __init__(
        self,
        generator: Optional[SD35Generator] = None,
        ip_adapter: Optional[IPAdapterHandler] = None
    ):
        settings = get_settings()
        self.generator = generator or SD35Generator()
        self.ip_adapter = ip_adapter or IPAdapterHandler()

        self._reference_image: Optional[str] = None

    async def initialize(self) -> None:
        """초기화"""
        await self.generator.load_model()
        if self.ip_adapter:
            await self.ip_adapter.load()

    def set_reference_image(self, image_path: str) -> None:
        """참조 이미지 설정 (IP-Adapter용)"""
        self._reference_image = image_path

    async def generate_consistent_images(
        self,
        scenes: List[Scene],
        preset: StylePreset,
        output_dir: str
    ) -> List[str]:
        """
        일관된 스타일로 장면별 이미지 생성

        Args:
            scenes: 장면 목록
            preset: 스타일 프리셋
            output_dir: 출력 디렉토리

        Returns:
            생성된 이미지 경로 목록
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        image_paths = []

        # IP-Adapter 참조 이미지 결정
        ref_image = preset.ip_adapter_ref or self._reference_image
        use_ip_adapter = ref_image and self.ip_adapter.is_available()

        if use_ip_adapter:
            print(f"Using IP-Adapter with reference: {ref_image}")
        else:
            print(f"Using seed-based consistency (seed: {preset.seed})")

        for i, scene in enumerate(scenes):
            output_path = f"{output_dir}/scene_{i:03d}.png"

            if use_ip_adapter:
                # IP-Adapter 사용
                image = await self.ip_adapter.apply_style(
                    pipeline=self.generator.pipeline,
                    prompt=f"{preset.base_prompt}, {scene.image_prompt}",
                    reference_image=ref_image,
                    negative_prompt=preset.negative_prompt,
                    scale=preset.ip_adapter_scale,
                    num_inference_steps=preset.steps,
                    guidance_scale=preset.cfg_scale,
                    width=576,
                    height=1024,
                )
                image.save(output_path, quality=95)
            else:
                # Seed만 사용
                await self.generator.generate(
                    prompt=scene.image_prompt,
                    preset=preset,
                    output_path=output_path
                )

            image_paths.append(output_path)
            print(f"Generated: {output_path}")

        return image_paths

    async def generate_first_as_reference(
        self,
        scenes: List[Scene],
        preset: StylePreset,
        output_dir: str
    ) -> List[str]:
        """
        첫 번째 이미지를 참조로 사용하여 일관성 유지

        - 첫 이미지: Seed 기반 생성
        - 나머지: 첫 이미지를 IP-Adapter 참조로 사용
        """
        if not scenes:
            return []

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        image_paths = []

        # 첫 번째 이미지 생성
        first_path = f"{output_dir}/scene_000.png"
        await self.generator.generate(
            prompt=scenes[0].image_prompt,
            preset=preset,
            output_path=first_path
        )
        image_paths.append(first_path)

        # 첫 이미지를 참조로 설정
        self.set_reference_image(first_path)

        # IP-Adapter 로드 (필요시)
        if not self.ip_adapter.is_available():
            await self.ip_adapter.load()

        # 나머지 이미지 생성
        for i, scene in enumerate(scenes[1:], 1):
            output_path = f"{output_dir}/scene_{i:03d}.png"

            if self.ip_adapter.is_available():
                image = await self.ip_adapter.apply_style(
                    pipeline=self.generator.pipeline,
                    prompt=f"{preset.base_prompt}, {scene.image_prompt}",
                    reference_image=first_path,
                    negative_prompt=preset.negative_prompt,
                    scale=preset.ip_adapter_scale,
                    num_inference_steps=preset.steps,
                    guidance_scale=preset.cfg_scale,
                    width=576,
                    height=1024,
                )
                image.save(output_path, quality=95)
            else:
                await self.generator.generate(
                    prompt=scene.image_prompt,
                    preset=preset,
                    output_path=output_path
                )

            image_paths.append(output_path)

        return image_paths
