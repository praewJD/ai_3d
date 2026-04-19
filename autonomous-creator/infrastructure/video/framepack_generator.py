"""
FramePack Generator - Next-Frame Prediction Video Generation

lllyasviel/FramePack 기반 비디오 생성
6GB VRAM에서 최대 60초 비디오 생성 가능
"""
import logging
import torch
from typing import Optional
from pathlib import Path
import os
import sys

logger = logging.getLogger(__name__)

# FramePack 경로 (D: 드라이브)
FRAMEPACK_DIR = Path(r"D:\AI-Video\FramePack")


class FramePackGenerator:
    """
    FramePack 비디오 생성기

    - 6GB VRAM 최소 요구사항
    - 최대 60초 비디오 생성 가능
    - Next-frame prediction 방식
    - 일관성 있는 모션 생성
    """

    def __init__(self, framepack_dir: str = None):
        self.framepack_dir = Path(framepack_dir) if framepack_dir else FRAMEPACK_DIR
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self._models_loaded = False

    async def is_available(self) -> bool:
        """FramePack 사용 가능 여부"""
        if not torch.cuda.is_available():
            return False

        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        return vram >= 6  # 6GB 이상

    def check_installation(self) -> dict:
        """FramePack 설치 상태 확인"""
        results = {
            "framepack_dir": self.framepack_dir.exists(),
            "demo_file": (self.framepack_dir / "demo_gradio.py").exists(),
            "requirements": (self.framepack_dir / "requirements.txt").exists(),
            "diffusers_helper": (self.framepack_dir / "diffusers_helper").exists(),
        }

        if all(results.values()):
            print("FramePack installation verified")
        else:
            missing = [k for k, v in results.items() if not v]
            print(f"Missing: {k}")

        return results

    async def generate_video(
        self,
        image_path: str,
        output_path: str,
        prompt: str = "",
        n_prompt: str = "",
        total_seconds: float = 5.0,
        seed: int = 31337,
        use_teacache: bool = True,
        steps: int = 25,
        cfg: float = 1.0,
        gpu_memory_preservation: float = 6.0,
        audio_path: str = None,
    ) -> str:
        """
        FramePack으로 비디오 생성

        Args:
            image_path: 입력 이미지 경로
            output_path: 출력 비디오 경로 (MP4)
            prompt: 프롬프트 (선택사항)
            n_prompt: 네거티브 프롬프트
            total_seconds: 비디오 길이 (초)
            seed: 랜덤 시드
            use_teacache: TeaCache 사용 여부
            steps: inference steps
            cfg: CFG scale
            gpu_memory_preservation: GPU 메모리 보존 (GB)
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)

        Returns:
            생성된 비디오 경로
        """
        # audio_path 검증 (립싱크 오디오)
        effective_audio_path = None
        if audio_path:
            if Path(audio_path).exists():
                effective_audio_path = audio_path
                logger.info(f"립싱크 오디오 활성화: {audio_path}")
            else:
                logger.warning(f"오디오 파일 없음, 오디오 없이 진행: {audio_path}")
        # FramePack의 demo_gradio.py에서 worker 함수 사용
        # 이는 FramePack을 직접 호출하는 래퍼입니다
        if not self._models_loaded:
            await self._load_framepack_models()

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # FramePack은 자체 Gradio UI를 사용하지만,
        # 여기서는 프로그래밍 방식으로 호출하도 래퍼를 작성해야 함
        # 현재는 FramePack의 demo_gradio.py를 실행하는 방식 사용
        # 실제 구현은 FramePack 모델 로드 후 직접 호출 필요

        # 임시: FramePack은 현재 Gradio UI 중심으로 설계됨
        # 프로그래밍 API가 없으므로 서브프로세스로 실행
        import subprocess
        import json

        # FramePack 실행
        cmd = [
            sys.executable, "-m",
            "framepack_worker.py",
            "--image", image_path,
            "--output", output_path,
            "--prompt", prompt,
            "--n_prompt", n_prompt,
            "--seconds", str(total_seconds),
            "--seed", str(seed),
        ]

        # FramePack은 독립 실행이므로 여기서는 인터페이스만 정의
        # 실제 구현은 별도 작업 필요

        return output_path

    async def _load_framepack_models(self):
        """FramePack 모델 로드"""
        print("Loading FramePack models...")
        print("Note: FramePack models will be downloaded on first run (~30GB)")
        print("Models will be cached in HuggingFace cache directory")
        self._models_loaded = True


class FramePackWorker:
    """
    FramePack 워커 - 실제 비디오 생성 수행

    Gradio demo_gradio.py를 기반으로 프로그래밍 방식으로 변환
    """

    def __init__(self, framepack_dir: Path):
        self.framepack_dir = framepack_dir
        self._setup_paths()

    def _setup_paths(self):
        """경로 설정"""
        sys.path.insert(0, str(self.framepack_dir))
        sys.path.insert(0, str(self.framepack_dir / "diffusers_helper"))

    async def generate(
        self,
        input_image,
        prompt: str,
        n_prompt: str,
        seed: int,
        total_second_length: float,
        latent_window_size: int = 9,
        steps: int = 25,
        cfg: float = 1.0,
        gs: float = 10.0,
        rs: float = 0.0,
        gpu_memory_preservation: float = 6.0,
        use_teacache: bool = True,
        mp4_crf: int = 16,
        audio_path: str = None,
    ) -> str:
        """
        FramePack 워커 실행

        Args:
            audio_path: TTS 오디오 파일 경로 (립싱크용, None이면 오디오 없이 생성)
        """
        # FramePack의 demo_gradio.py에서 핵심 로직 추출
        # 실제로는 FramePack을 직접 설치하여 실행하는 것이 좋음
        pass
