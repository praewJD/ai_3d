"""
SVD Generator - Stable Video Diffusion

이미지 → 비디오 변환
"""
import logging
import torch
from typing import Optional
from pathlib import Path
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video

from core.domain.interfaces.video_composer import ISVDGenerator
from config.settings import get_settings

logger = logging.getLogger(__name__)


class SVDGenerator(ISVDGenerator):
    """
    Stable Video Diffusion 이미지→비디오 변환기

    - 12GB+ VRAM 권장
    - 2-4초 비디오 생성
    - 576x1024 (9:16) 해상도
    """

    # VRAM 요구사항 (GB)
    VRAM_REQUIREMENTS = {
        "full": 16,
        "optimized": 12,
        "low": 8,
    }

    def __init__(
        self,
        model_path: str = "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
        device: str = "auto"
    ):
        settings = get_settings()
        self.model_path = model_path
        self.device = self._determine_device(device)
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        self.pipeline: Optional[StableVideoDiffusionPipeline] = None
        self._is_loaded = False

    def _determine_device(self, device: str) -> str:
        if device == "auto":
            if torch.cuda.is_available():
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram < 8:
                    print(f"Warning: Low VRAM ({vram:.1f}GB). SVD may not work properly.")
                return "cuda"
            return "cpu"
        return device

    async def is_available(self) -> bool:
        """SVD 사용 가능 여부 (VRAM 확인)"""
        if not torch.cuda.is_available():
            return False

        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        return vram >= 8  # 8GB 이상

    async def load_model(self) -> None:
        """모델 로드"""
        if self._is_loaded:
            return

        print(f"Loading SVD on {self.device}...")

        self.pipeline = StableVideoDiffusionPipeline.from_pretrained(
            self.model_path,
            torch_dtype=self.dtype,
            use_safetensors=True
        )

        if self.device == "cuda":
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)

            if vram < 12:
                # 저VRAM 최적화
                self.pipeline.enable_model_cpu_offload()
                self.pipeline.unet.enable_forward_chunking(chunk_size=1, dim=1)
            else:
                self.pipeline = self.pipeline.to(self.device)

        self._is_loaded = True
        print("SVD loaded successfully")

    async def unload_model(self) -> None:
        """모델 언로드"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._is_loaded = False

    async def generate_video(
        self,
        image_path: str,
        output_path: str,
        num_frames: int = 25,
        fps: int = 8,
        motion_bucket_id: int = 127,
        audio_path: str = None,
    ) -> str:
        """
        이미지에서 비디오 생성

        Args:
            image_path: 입력 이미지 경로
            output_path: 출력 비디오 경로
            num_frames: 프레임 수 (기본 25 = ~3초 @ 8fps)
            fps: 프레임 레이트
            motion_bucket_id: 모션 강도 (1-255, 높을수록 역동적)
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)

        Returns:
            생성된 비디오 경로
        """
        if not self._is_loaded:
            await self.load_model()

        # audio_path 검증 (립싱크 오디오)
        effective_audio_path = None
        if audio_path:
            if Path(audio_path).exists():
                effective_audio_path = audio_path
                logger.info(f"립싱크 오디오 활성화: {audio_path}")
            else:
                logger.warning(f"오디오 파일 없음, 오디오 없이 진행: {audio_path}")

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 이미지 로드 및 리사이즈
        image = load_image(image_path)
        image = image.resize((576, 1024))  # 9:16

        # 비디오 생성
        frames = self.pipeline(
            image,
            num_frames=num_frames,
            motion_bucket_id=motion_bucket_id,
            noise_aug_strength=0.02,
            min_guidance_scale=1.0,
            max_guidance_scale=3.0,
            decode_chunk_size=8,
        ).frames[0]

        # 비디오로 내보내기
        export_to_video(frames, output_path, fps=fps)

        return output_path

    async def generate_with_preset(
        self,
        image_path: str,
        output_path: str,
        preset: str = "medium",
        audio_path: str = None,
    ) -> str:
        """
        프리셋으로 비디오 생성

        Args:
            image_path: 입력 이미지 경로
            output_path: 출력 비디오 경로
            preset: 모션 프리셋 ("subtle" | "medium" | "dynamic" | "long")
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)
        """

        presets = {
            "subtle": {"motion_bucket_id": 64, "num_frames": 25, "fps": 8},
            "medium": {"motion_bucket_id": 127, "num_frames": 25, "fps": 8},
            "dynamic": {"motion_bucket_id": 200, "num_frames": 25, "fps": 8},
            "long": {"motion_bucket_id": 127, "num_frames": 40, "fps": 8},
        }

        params = presets.get(preset, presets["medium"])
        return await self.generate_video(image_path, output_path, audio_path=audio_path, **params)


class SVDOptimizer:
    """SVD 성능 최적화"""

    @staticmethod
    def get_optimal_settings(vram_gb: float) -> dict:
        """VRAM에 따른 최적 설정"""
        if vram_gb >= 16:
            return {"num_frames": 25, "decode_chunk_size": 8, "cpu_offload": False}
        elif vram_gb >= 12:
            return {"num_frames": 25, "decode_chunk_size": 4, "cpu_offload": True}
        elif vram_gb >= 8:
            return {"num_frames": 16, "decode_chunk_size": 2, "cpu_offload": True}
        else:
            return None  # SVD 사용 불가
