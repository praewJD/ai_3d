"""
IP-Adapter Handler

이미지 기반 스타일 일관성 유지
"""
import torch
from typing import Optional, Dict, Any
from pathlib import Path
from PIL import Image

try:
    from ip_adapter import IPAdapterPlus
    IP_ADAPTER_AVAILABLE = True
except ImportError:
    IP_ADAPTER_AVAILABLE = False

from config.settings import get_settings


class IPAdapterHandler:
    """
    IP-Adapter 핸들러

    - 참조 이미지에서 스타일 추출
    - 새 이미지에 스타일 적용
    - 캐릭터/스타일 일관성 유지
    """

    # 사전 학습된 모델 경로
    MODEL_PATHS = {
        "sd35_large": "InstantX/SD3.5-Large-IP-Adapter",
        "sdxl": "h94/IP-Adapter",
        "sd15": "h94/IP-Adapter",
    }

    def __init__(
        self,
        model_type: str = "sd35_large",
        device: str = "auto"
    ):
        settings = get_settings()
        self.device = "cuda" if (device == "auto" and torch.cuda.is_available()) else device
        self.model_type = model_type
        self.model_path = self.MODEL_PATHS.get(model_type)

        self.ip_adapter = None
        self._is_loaded = False

        if not IP_ADAPTER_AVAILABLE:
            print("Warning: ip-adapter not installed. Style consistency features limited.")

    async def load(self) -> None:
        """IP-Adapter 모델 로드"""
        if self._is_loaded or not IP_ADAPTER_AVAILABLE:
            return

        try:
            # IP-Adapter Plus 로드 (더 나은 품질)
            self.ip_adapter = IPAdapterPlus(
                self.model_path,
                subfolder="sdxl_models" if "sdxl" in self.model_type else "models",
                device=self.device
            )
            self._is_loaded = True
            print(f"IP-Adapter loaded: {self.model_type}")
        except Exception as e:
            print(f"Failed to load IP-Adapter: {e}")
            self._is_loaded = False

    def is_available(self) -> bool:
        """IP-Adapter 사용 가능 여부"""
        return IP_ADAPTER_AVAILABLE and self._is_loaded

    def load_reference_image(self, image_path: str) -> Image.Image:
        """참조 이미지 로드"""
        return Image.open(image_path).convert("RGB")

    def get_adapter_params(
        self,
        reference_image: str,
        scale: float = 0.8
    ) -> Dict[str, Any]:
        """
        IP-Adapter 파라미터 생성

        Args:
            reference_image: 참조 이미지 경로
            scale: 스타일 강도 (0~1)

        Returns:
            Pipeline에 전달할 파라미터
        """
        if not self.is_available():
            return {}

        ref_image = self.load_reference_image(reference_image)

        return {
            "ip_adapter_image": ref_image,
            "ip_adapter_scale": scale,
        }

    async def apply_style(
        self,
        pipeline,
        prompt: str,
        reference_image: str,
        negative_prompt: str = "",
        scale: float = 0.8,
        **kwargs
    ):
        """
        IP-Adapter로 스타일 적용

        Args:
            pipeline: Diffusion pipeline
            prompt: 텍스트 프롬프트
            reference_image: 참조 이미지
            negative_prompt: 네거티브 프롬프트
            scale: 스타일 강도
            **kwargs: 추가 파라미터

        Returns:
            생성된 이미지
        """
        if not self.is_available():
            # IP-Adapter 없이 일반 생성
            return pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                **kwargs
            ).images[0]

        # IP-Adapter 파라미터 추가
        adapter_params = self.get_adapter_params(reference_image, scale)

        return pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            **adapter_params,
            **kwargs
        ).images[0]

    def set_scale(self, scale: float) -> None:
        """스타일 강도 설정"""
        if self.ip_adapter:
            self.ip_adapter.set_ip_adapter_scale(scale)


class IPAdapterCache:
    """IP-Adapter 임베딩 캐시 (성능 최적화)"""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def get(self, image_path: str) -> Optional[Any]:
        return self._cache.get(image_path)

    def set(self, image_path: str, embedding: Any) -> None:
        self._cache[image_path] = embedding

    def clear(self) -> None:
        self._cache.clear()
