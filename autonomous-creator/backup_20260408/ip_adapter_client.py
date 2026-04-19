# -*- coding: utf-8 -*-
"""
IP-Adapter Client - 캐릭터 일관성 유지

IP-Adapter를 사용하여 동일 캐릭터의 일관된 외형 유지
"""
import os
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass
import torch

from PIL import Image


@dataclass
class IPAdapterConfig:
    """IP-Adapter 설정"""
    model_path: str = "models/ip-adapter"
    subfolder: str = "models"
    weight_name: str = "ip-adapter-plus_sd15.bin"
    device: str = "cuda"
    cpu_offload: bool = True
    strength: float = 0.8
    num_tokens: int = 16


class IPAdapterClient:
    """
    IP-Adapter 클라이언트

    캐릭터 외형 일관성을 위한 IP-Adapter 래퍼

    6GB VRAM 대응:
    - CPU offload 기본 사용
    - 낮은 해상도 기본값
    """

    def __init__(
        self,
        sd_pipeline,
        config: IPAdapterConfig = None,
    ):
        """
        초기화

        Args:
            sd_pipeline: SD 3.5 파이프라인
            config: IP-Adapter 설정
        """
        self.pipeline = sd_pipeline
        self.config = config or IPAdapterConfig()

        # 상태
        self._ip_adapter = None
        self._reference_image: Optional[Image.Image] = None
        self._reference_embeds = None

        # VRAM 확인
        self.vram = self._get_vram()
        if self.vram < 12:
            self.config.cpu_offload = True
            print(f"VRAM {self.vram:.1f}GB - CPU offload 활성화")

    def _get_vram(self) -> float:
        """VRAM 크기 확인"""
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
        return 0

    def load_ip_adapter(self) -> bool:
        """
        IP-Adapter 로드

        Returns:
            로드 성공 여부
        """
        try:
            # IP-Adapter 패키지 확인
            from ip_adapter import IPAdapterPlus

            # 기본 경로 설정
            model_path = Path(self.config.model_path)
            if not model_path.exists():
                print(f"IP-Adapter 모델 경로 없음: {model_path}")
                print("IP-Adapter 없이 진행합니다.")
                return False

            # IP-Adapter 로드
            self._ip_adapter = IPAdapterPlus(
                self.pipeline,
                path=str(model_path),
                subfolder=self.config.subfolder,
                weight_name=self.config.weight_name,
                device=self.config.device,
                num_tokens=self.config.num_tokens,
            )

            if self.config.cpu_offload:
                self._ip_adapter.enable_cpu_offload()

            print("IP-Adapter 로드 완료")
            return True

        except ImportError:
            print("ip_adapter 패키지 없음 - 기본 모드로 진행")
            print("설치: pip install ip-adapter")
            return False
        except Exception as e:
            print(f"IP-Adapter 로드 실패: {e}")
            return False

    def set_reference_image(
        self,
        image: Union[str, Path, Image.Image],
    ) -> bool:
        """
        캐릭터 기준 이미지 설정

        Args:
            image: 이미지 경로 또는 PIL Image

        Returns:
            설정 성공 여부
        """
        try:
            if isinstance(image, (str, Path)):
                self._reference_image = Image.open(image).convert("RGB")
            else:
                self._reference_image = image.convert("RGB")

            # 임베딩 미리 계산 (IP-Adapter 있는 경우)
            if self._ip_adapter:
                self._reference_embeds = self._ip_adapter.get_image_embeds(
                    self._reference_image
                )

            return True

        except Exception as e:
            print(f"기준 이미지 설정 실패: {e}")
            return False

    def generate_with_identity(
        self,
        prompt: str,
        negative_prompt: str = "",
        strength: Optional[float] = None,
        width: int = 576,
        height: int = 1024,
        num_inference_steps: int = 40,
        guidance_scale: float = 4.5,
        seed: Optional[int] = None,
        **kwargs,
    ) -> Optional[Image.Image]:
        """
        일관된 외형으로 이미지 생성

        Args:
            prompt: 프롬프트
            negative_prompt: Negative 프롬프트
            strength: IP-Adapter 강도
            width: 이미지 너비
            height: 이미지 높이
            num_inference_steps: 스텝 수
            guidance_scale: CFG 스케일
            seed: 시드

        Returns:
            생성된 이미지
        """
        strength = strength or self.config.strength

        # IP-Adapter 없으면 일반 생성
        if not self._ip_adapter or not self._reference_image:
            return self._generate_without_adapter(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                seed=seed,
            )

        try:
            # 시드 설정
            generator = None
            if seed is not None:
                generator = torch.Generator(device="cpu").manual_seed(seed)

            # IP-Adapter로 생성
            images = self._ip_adapter.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                pil_image=self._reference_image,
                scale=strength,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
                **kwargs,
            )

            return images[0] if images else None

        except Exception as e:
            print(f"IP-Adapter 생성 실패: {e}")
            return self._generate_without_adapter(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                seed=seed,
            )

    def _generate_without_adapter(
        self,
        prompt: str,
        negative_prompt: str,
        **kwargs,
    ) -> Optional[Image.Image]:
        """IP-Adapter 없이 일반 생성"""
        try:
            result = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                **kwargs,
            )
            return result.images[0] if result.images else None
        except Exception as e:
            print(f"이미지 생성 실패: {e}")
            return None

    def is_loaded(self) -> bool:
        """IP-Adapter 로드 여부"""
        return self._ip_adapter is not None

    def has_reference(self) -> bool:
        """기준 이미지 설정 여부"""
        return self._reference_image is not None

    def clear_reference(self):
        """기준 이미지 초기화"""
        self._reference_image = None
        self._reference_embeds = None


class IPAdapterManager:
    """
    IP-Adapter 매니저

    여러 캐릭터의 기준 이미지 관리
    """

    def __init__(
        self,
        sd_pipeline,
        config: IPAdapterConfig = None,
    ):
        self.pipeline = sd_pipeline
        self.config = config or IPAdapterConfig()

        # 캐릭터별 클라이언트
        self._clients: dict[str, IPAdapterClient] = {}

        # 글로벌 클라이언트 (단일 캐릭터용)
        self._global_client: Optional[IPAdapterClient] = None

    def get_client(self, character_id: Optional[str] = None) -> IPAdapterClient:
        """캐릭터 ID로 클라이언트 조회/생성"""
        if character_id is None:
            if self._global_client is None:
                self._global_client = IPAdapterClient(self.pipeline, self.config)
            return self._global_client

        if character_id not in self._clients:
            self._clients[character_id] = IPAdapterClient(self.pipeline, self.config)

        return self._clients[character_id]

    def set_character_reference(
        self,
        character_id: str,
        image: Union[str, Path, Image.Image],
    ) -> bool:
        """캐릭터 기준 이미지 설정"""
        client = self.get_client(character_id)
        return client.set_reference_image(image)

    def generate_character_scene(
        self,
        character_id: str,
        prompt: str,
        negative_prompt: str = "",
        **kwargs,
    ) -> Optional[Image.Image]:
        """캐릭터 일관성 유지하며 장면 생성"""
        client = self.get_client(character_id)
        return client.generate_with_identity(
            prompt=prompt,
            negative_prompt=negative_prompt,
            **kwargs,
        )

    def preload_adapters(self):
        """모든 클라이언트에 IP-Adapter 로드"""
        for client in self._clients.values():
            if not client.is_loaded():
                client.load_ip_adapter()

        if self._global_client and not self._global_client.is_loaded():
            self._global_client.load_ip_adapter()

    def clear_all(self):
        """모든 기준 이미지 초기화"""
        for client in self._clients.values():
            client.clear_reference()

        if self._global_client:
            self._global_client.clear_reference()
