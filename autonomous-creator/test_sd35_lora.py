# -*- coding: utf-8 -*-
"""
SD 3.5 LoRA 테스트 스크립트

Hugging Face에서 찾은 SD 3.5 호환 LoRA 모델을 테스트합니다.

모델 목록:
1. dashabalashova/dreambooth-GPT-girl-and-cat-stable-diffusion-3.5-large-lora-v1
2. batusalmanoglu/stable-diffusion-3.5-large-lora-differant-validation-merged1
3. sorensenjg/stable-diffusion-3.5-large-grot-lora

참고: SD 3.5용 3D 애니메이션/Pixar 스타일 LoRA는 아직 매우 적습니다
대신 프롬프트 엔지니어링으로 스타일을 구현하세요.
"""

import sys
import io
from pathlib import Path
from datetime import datetime
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 출력 디렉토리
OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/test_outputs/sd35_lora_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LoRA 모델 설정
LORA_MODELS = {
    "dreambooth_gpt_girl": {
        "hf_path": "dashabalashova/dreambooth-GPT-girl-and-cat-stable-diffusion-3.5-large-lora-v1",
        "weight_name": "pytorch_lora_weights.safetensors",
        "trigger_words": "pencil sketch of qwe girl and asd cat",
        "description": "DreamBooth LoRA for GPT girl and cat style",
        "compatible_with": "stabilityai/stable-diffusion-3.5-large"
    },
    "validation_merged": {
        "hf_path": "batusalmanoglu/stable-diffusion-3.5-large-lora-differant-validation-merged1",
        "weight_name": "pytorch_lora_weights.safetensors",
        "trigger_words": None,
        "description": "Validation merged LoRA",
        "compatible_with": "stabilityai/stable-diffusion-3.5-large"
    },
    "grot_lora": {
        "hf_path": "sorensenjg/stable-diffusion-3.5-large-grot-lora",
        "weight_name": "pytorch_lora_weights.safetensors",
        "trigger_words": "grot, fantasy creature",
        "description": "Grot fantasy creature LoRA",
        "compatible_with": "stabilityai/stable-diffusion-3.5-large"
    }
}

# 베이스 모델 설정
BASE_MODEL = "stabilityai/stable-diffusion-3.5-large"  # 또는 "stabilityai/stable-diffusion-3.5-medium"


class SD35LoRATester:
    """SD 3.5 LoRA 테스터"""

    def __init__(self, use_medium: bool = False):
        self.pipeline = None
        self.device = "cuda"
        self.use_medium = use_medium

    def load_model(self):
        """SD 3.5 모델 로드"""
        import torch
        from diffusers import StableDiffusion3Pipeline

        model_name = "stabilityai/stable-diffusion-3.5-medium" if self.use_medium else "stabilityai/stable-diffusion-3.5-large"

        print(f"\n[SD 3.5] Loading {model_name}...")

        # dtype 설정 (Large: bfloat16, Medium: float16)
        dtype = torch.float16 if self.use_medium else torch.bfloat16

        self.pipeline = StableDiffusion3Pipeline.from_pretrained(
            model_name,
            torch_dtype=dtype,
        )

        # Low VRAM 모드에서 CPU offload 사용
        self.pipeline.enable_model_cpu_offload()
        print(f"[SD 3.5] Model loaded (CPU offload mode)")

    def download_lora(self, lora_key: str, local_path: str = None) -> bool:
        """LoRA 다운로드"""
        import torch

        lora_info = LORA_MODELS[lora_key]
        hf_path = lora_info["hf_path"]
        weight_name = lora_info["weight_name"]

        if local_path is None:
            # 로컬 경로 생성
            local_path = Path(f"D:/AI-Video/autonomous-creator/data/lora/{lora_key}.safetensors")

        if local_path.exists():
            print(f"[LoRA] Already exists: {local_path}")
            return True

        print(f"[LoRA] Downloading from {hf_path}...")

        try:
            from huggingface_hub import hf_hub_download

            # 파일 다운로드
            hf_hub_download(
                repo_id=hf_path,
                filename=weight_name,
                local_dir=local_path.parent,
                local_dir_use_symlinks=False
            )

            # 다운로드된 파일명 변경
            downloaded_path = local_path.parent / weight_name
            if downloaded_path != local_path:
                downloaded_path.rename(local_path)

            print(f"[LoRA] Downloaded: {local_path}")
            return True

        except Exception as e:
            print(f"[LoRA] Download failed: {e}")
            return False

    def load_lora(self, lora_key: str, local_path: str = None) -> bool:
        """LoRA 로드 into pipeline"""
        if self.pipeline is None:
            self.load_model()

        lora_info = LORA_MODELS[lora_key]

        if local_path is None:
            local_path = Path(f"D:/AI-Video/autonomous-creator/data/lora/{lora_key}.safetensors")

        if not local_path.exists():
            print(f"[LoRA] File not found: {local_path}")
            print("[LoRA] Attempting download...")
            if not self.download_lora(lora_key, local_path):
                return False

        try:
            print(f"[LoRA] Loading into pipeline...")
            self.pipeline.load_lora_weights(
                str(local_path),
                adapter_name=lora_key
            )
            print(f"[LoRA] Loaded successfully: {lora_key}")
            return True
        except Exception as e:
            print(f"[LoRA] Load failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        lora_key: str = None,
        trigger_words: str = None,
        seed: int = 42,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 28,
        guidance_scale: float = 7.0,
        lora_scale: float = 1.0
    ) -> str:
        """이미지 생성"""
        import torch

        if self.pipeline is None:
            self.load_model()

        # LoRA 로드
        if lora_key:
            if not self.load_lora(lora_key):
                print(f"[Warning] LoRA {lora_key} could not be loaded, using base model only")
                lora_key = None

        # 프롬프트 구성
        full_prompt = prompt
        if trigger_words:
            full_prompt = f"{trigger_words}, {prompt}"

        print(f"\n[Generating]")
        print(f"  Prompt: {full_prompt[:80]}...")
        if lora_key:
            print(f"  LoRA: {lora_key}")

        # Generator 설정
        generator = torch.Generator(device="cpu").manual_seed(seed)

        # 이미지 생성
        result = self.pipeline(
            prompt=full_prompt,
            negative_prompt="blurry, low quality, distorted, watermark, text, signature, bad anatomy",
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            generator=generator,
            cross_attention_kwargs={"scale": lora_scale} if lora_key else None
        )

        return result.images[0]

    def unload(self):
        """메모리 정리"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
            import torch
            import gc
            gc.collect()
            torch.cuda.empty_cache()
            print("[SD 3.5] Model unloaded")


def test_lora_model(lora_key: str, use_medium: bool = False):
    """특정 LoRA 모델 테스트"""
    print("\n" + "=" * 60)
    print(f"Testing LoRA: {lora_key}")
    print("=" * 60)

    lora_info = LORA_MODELS[lora_key]

    tester = SD35LoRATester(use_medium=use_medium)

    # 테스트 프롬프트
    test_prompts = [
        "a beautiful landscape with mountains and a river",
        "a portrait of a young woman with flowers",
        "a fantasy creature in a magical forest"
    ]

    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Test {i+1}: {prompt[:50]}...")

        image = tester.generate(
            prompt=prompt,
            lora_key=lora_key,
            trigger_words=lora_info.get("trigger_words"),
            seed=42 + i,
            width=1024,
            height=1024,
            lora_scale=0.85
        )

        # 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_key = lora_key.replace("/", "_")
        output_path = OUTPUT_DIR / f"{safe_key}_test{i+1}_{timestamp}.png"
        image.save(output_path, quality=95)

        size_kb = os.path.getsize(output_path) / 1024
        print(f"  Saved: {output_path.name} ({size_kb:.1f} KB)")

    # 메모리 정리
    tester.unload()

    print(f"\n[OK] LoRA test completed: {lora_key}")


def test_without_lora(use_medium: bool = False):
    """LoRA 없이 기본 모델 테스트"""
    print("\n" + "=" * 60)
    print("Testing Base Model (No LoRA)")
    print("=" * 60)

    tester = SD35LoRATester(use_medium=use_medium)

    test_prompts = [
        "3D animation style, cute character, vibrant colors, disney style",
        "pixar style, animated movie scene, cinematic lighting, expressive face",
        "a heroic character in action pose, epic background, detailed textures"
    ]

    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Base Test {i+1}: {prompt[:50]}...")

        image = tester.generate(
            prompt=prompt,
            seed=42 + i,
            width=1024,
            height=1024,
        )

        # 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"base_test{i+1}_{timestamp}.png"
        image.save(output_path, quality=95)

        size_kb = os.path.getsize(output_path) / 1024
        print(f"  Saved: {output_path.name} ({size_kb:.1f} KB)")

    tester.unload()

    print("\n[OK] Base model test completed")


def main():
    print("=" * 60)
    print("SD 3.5 LoRA Test Suite")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")

    # 1. 기본 모델 테스트 (LoRA 없이)
    print("\n[Step 1] Testing base model without LoRA...")
    test_without_lora(use_medium=True)  # Medium 사용 (더 빠름)

    # 2. DreamBooth LoRA 테스트
    print("\n[Step 2] Testing DreamBooth LoRA...")
    if "dreambooth_gpt_girl" in LORA_MODELS:
        test_lora_model("dreambooth_gpt_girl", use_medium=True)

    # 3. Grot LoRA 테스트
    print("\n[Step 3] Testing Grot LoRA...")
    if "grot_lora" in LORA_MODELS:
        test_lora_model("grot_lora", use_medium=True)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

    # 결과 요약
    print("\nGenerated files:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.1f} KB")

    print("\nNote: For 3D animation/Pixar style, use prompt engineering:")
    print('  - Add "3D animation style, disney style, pixar style" to prompts')
    print('  - Use "cinematic lighting, expressive face, vibrant colors"')
    print('  - Example: "3D animation style, brave hero with cape, pixar style, cinematic lighting"')


if __name__ == "__main__":
    main()
