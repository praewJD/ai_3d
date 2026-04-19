"""
SD 3.5 Medium Image Generator

Stable Diffusion 3.5 Medium 기반 이미지 생성
v2.0: IP-Adapter 통합으로 캐릭터 일관성 유지
"""
import torch
from typing import Optional, List
from pathlib import Path
from diffusers import StableDiffusion3Pipeline

from core.domain.interfaces.image_generator import IImageGenerator
from core.domain.entities.preset import StylePreset
from config.settings import get_settings

# [신규] IP-Adapter 통합
from infrastructure.image.ip_adapter_client import IPAdapterClient, IPAdapterConfig


class SD35Generator(IImageGenerator):
    """
    Stable Diffusion 3.5 Medium 이미지 생성기

    - 6GB VRAM에서 실행 가능 (CPU offload)
    - 고품질 텍스트-이미지 생성
    - 9:16 세로 영상 최적화
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto"
    ):
        settings = get_settings()
        self.model_path = model_path or settings.sd_model
        self.device = self._determine_device(device)
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.low_vram = settings.sd_low_vram

        self.pipeline: Optional[StableDiffusion3Pipeline] = None
        self._is_loaded = False

        # [신규] IP-Adapter 관련
        self._ip_adapter: Optional[IPAdapterClient] = None
        self._ip_adapter_enabled = settings.ip_adapter_enabled
        self._ip_adapter_config = IPAdapterConfig(
            model_path=settings.ip_adapter_model_path,
            strength=settings.ip_adapter_strength,
            cpu_offload=settings.sd_low_vram,
        )

    def _determine_device(self, device: str) -> str:
        """장치 결정"""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    async def load_model(self) -> None:
        """모델 로드"""
        if self._is_loaded:
            return

        print(f"Loading SD 3.5 Medium on {self.device}...")

        self.pipeline = StableDiffusion3Pipeline.from_pretrained(
            self.model_path,
            torch_dtype=self.dtype,
            use_safetensors=True
        )

        if self.device == "cuda":
            if self.low_vram:
                # 저VRAM 모드: CPU offload
                self.pipeline.enable_model_cpu_offload()
            else:
                self.pipeline = self.pipeline.to(self.device)

        self._is_loaded = True
        print("SD 3.5 Medium loaded successfully")

        # [신규] IP-Adapter 로드 시도
        if self._ip_adapter_enabled:
            self._init_ip_adapter()

    async def unload_model(self) -> None:
        """모델 언로드"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._is_loaded = False
        self._ip_adapter = None

    def _init_ip_adapter(self) -> bool:
        """IP-Adapter 초기화"""
        if not self.pipeline:
            return False

        try:
            self._ip_adapter = IPAdapterClient(self.pipeline, self._ip_adapter_config)
            return self._ip_adapter.load_ip_adapter()
        except Exception as e:
            print(f"IP-Adapter 초기화 실패: {e}")
            self._ip_adapter = None
            return False

    def set_character_reference(self, image_path: str) -> bool:
        """
        캐릭터 기준 이미지 설정

        Args:
            image_path: 기준 이미지 경로

        Returns:
            설정 성공 여부
        """
        if not self._ip_adapter:
            print("IP-Adapter가 로드되지 않음")
            return False

        return self._ip_adapter.set_reference_image(image_path)

    def clear_character_reference(self):
        """캐릭터 기준 이미지 초기화"""
        if self._ip_adapter:
            self._ip_adapter.clear_reference()

    def is_ip_adapter_loaded(self) -> bool:
        """IP-Adapter 로드 여부"""
        return self._ip_adapter is not None and self._ip_adapter.is_loaded()

    def is_loaded(self) -> bool:
        return self._is_loaded

    def get_model_name(self) -> str:
        return "SD3.5-Medium"

    async def generate(
        self,
        prompt: str,
        preset: StylePreset,
        output_path: str,
        width: int = 576,
        height: int = 1024,
        use_ip_adapter: bool = True
    ) -> str:
        """
        이미지 생성

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            output_path: 출력 경로
            width: 너비 (기본 576, 9:16)
            height: 높이 (기본 1024, 9:16)
            use_ip_adapter: IP-Adapter 사용 여부

        Returns:
            생성된 이미지 경로
        """
        # 모델 로드 확인
        if not self._is_loaded:
            await self.load_model()

        # 프롬프트 조합
        full_prompt = f"{preset.base_prompt}, {prompt}" if preset.base_prompt else prompt

        # [신규] IP-Adapter 사용 시
        if (
            use_ip_adapter
            and self._ip_adapter
            and self._ip_adapter.has_reference()
        ):
            image = self._ip_adapter.generate_with_identity(
                prompt=full_prompt,
                negative_prompt=preset.negative_prompt or "",
                width=width,
                height=height,
                num_inference_steps=preset.steps,
                guidance_scale=preset.cfg_scale,
                seed=preset.seed,
            )

            if image is None:
                # IP-Adapter 실패 시 기본 생성으로 폴백
                image = await self._generate_standard(
                    full_prompt, preset, width, height
                )
        else:
            # 기본 생성
            image = await self._generate_standard(
                full_prompt, preset, width, height
            )

        # 저장
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        return output_path

    async def _generate_standard(
        self,
        prompt: str,
        preset: StylePreset,
        width: int,
        height: int
    ):
        """표준 이미지 생성 (IP-Adapter 없이)"""
        # 시드 설정
        generator = None
        if preset.seed and preset.seed > 0:
            generator = torch.Generator(device="cpu").manual_seed(preset.seed)

        # 이미지 생성
        result = self.pipeline(
            prompt=prompt,
            negative_prompt=preset.negative_prompt,
            num_inference_steps=preset.steps,
            guidance_scale=preset.cfg_scale,
            width=width,
            height=height,
            generator=generator,
        )

        return result.images[0]

    async def generate_with_reference(
        self,
        prompt: str,
        preset: StylePreset,
        reference_image: str,
        output_path: str,
        scale: float = 0.8
    ) -> str:
        """
        참조 이미지 기반 생성 (IP-Adapter 사용)

        캐릭터 일관성 유지를 위해 기준 이미지 사용

        Args:
            prompt: 이미지 프롬프트
            preset: 스타일 프리셋
            reference_image: 기준 이미지 경로
            output_path: 출력 경로
            scale: IP-Adapter 강도 (0.0~1.0)

        Returns:
            생성된 이미지 경로
        """
        # 모델 로드 확인
        if not self._is_loaded:
            await self.load_model()

        # 기준 이미지 설정
        if self._ip_adapter:
            self._ip_adapter.set_reference_image(reference_image)

        # IP-Adapter 강도 임시 설정
        original_strength = self._ip_adapter_config.strength
        if scale > 0:
            self._ip_adapter_config.strength = scale

        try:
            # 생성 (use_ip_adapter=True)
            return await self.generate(
                prompt=prompt,
                preset=preset,
                output_path=output_path,
                use_ip_adapter=True
            )
        finally:
            # 원래 강도로 복구
            self._ip_adapter_config.strength = original_strength

    async def generate_batch(
        self,
        prompts: List[str],
        preset: StylePreset,
        output_dir: str
    ) -> List[str]:
        """여러 이미지 일괄 생성"""
        paths = []
        for i, prompt in enumerate(prompts):
            output_path = f"{output_dir}/image_{i:03d}.png"
            path = await self.generate(prompt, preset, output_path)
            paths.append(path)
        return paths
