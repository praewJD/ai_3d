# -*- coding: utf-8 -*-
"""
SDXL + 3D Disney LoRA 테스트 스크립트

Civitai에서 찾은 3D模型可爱化SDXL版 (Pixar 스타일) LoRA를 테스트합니다.

LoRA 정보:
- 이름: 3D模型可爱化SDXL版 (v2.0)
- 트리거: MG_ip, pixar
- 다운로드: 5.4만+
- 리뷰: 1000개 (압도적 긍정)
- URL: https://civitai.com/models/138583/3dsdxl
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
OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/test_outputs/sdxl_disney_lora")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LoRA 설정
LORA_CONFIG = {
    "local_path": "D:/AI-Video/autonomous-creator/data/lora/3dModel_sdxl_v2.safetensors",
    "civitai_url": "https://civitai.com/api/download/models/177483?type=Model&format=SafeTensor",
    "trigger_words": "MG_ip, pixar",
    "weight": 0.9,  # 권장: 0.8 ~ 1.2
    "clip_skip": 2,
}

# 베이스 모델
BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


class SDXLDisneyLoRATester:
    """SDXL + 3D Disney LoRA 테스터"""

    def __init__(self):
        self.pipeline = None
        self.device = "cuda"

    def load_model(self):
        """SDXL 모델 로드"""
        import torch
        from diffusers import StableDiffusionXLPipeline

        print(f"\n[SDXL] Loading {BASE_MODEL}...")

        self.pipeline = StableDiffusionXLPipeline.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        )

        # RTX 3060 (6GB) 최적화
        self.pipeline.enable_model_cpu_offload()
        # self.pipeline.enable_vae_slicing()  # 추가 메모리 절약

        print(f"[SDXL] Model loaded (CPU offload mode)")

    def download_lora(self) -> bool:
        """LoRA 다운로드 (Civitai)"""
        local_path = Path(LORA_CONFIG["local_path"])

        if local_path.exists():
            print(f"[LoRA] Already exists: {local_path}")
            return True

        print(f"[LoRA] Downloading from Civitai...")
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import requests

            response = requests.get(LORA_CONFIG["civitai_url"], stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            print(f"[LoRA] File size: {total_size / 1024 / 1024:.1f} MB")

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[LoRA] Downloaded: {local_path}")
            return True

        except Exception as e:
            print(f"[LoRA] Download failed: {e}")
            print(f"[LoRA] Please download manually from: {LORA_CONFIG['civitai_url']}")
            return False

    def load_lora(self) -> bool:
        """LoRA 로드 (PEFT 방식)"""
        if self.pipeline is None:
            self.load_model()

        local_path = Path(LORA_CONFIG["local_path"])

        if not local_path.exists():
            if not self.download_lora():
                return False

        try:
            print(f"[LoRA] Loading into pipeline...")
            # PEFT 방식으로 로드
            from peft import PeftModel
            self.pipeline.load_lora_weights(
                str(local_path.parent),
                weight_name=local_path.name,
            )
            print(f"[LoRA] Loaded successfully!")
            return True
        except Exception as e:
            print(f"[LoRA] Load failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate(
        self,
        prompt: str,
        use_lora: bool = True,
        seed: int = 42,
        width: int = 768,   # 6GB VRAM 권장
        height: int = 1024,
        num_inference_steps: int = 35,
        guidance_scale: float = 7.5,
        lora_scale: float = 0.9,
    ) -> "PIL.Image":
        """이미지 생성"""
        import torch

        if self.pipeline is None:
            self.load_model()

        # LoRA 로드
        if use_lora:
            if not self.load_lora():
                print("[Warning] LoRA could not be loaded, using base model")
                use_lora = False

        # 프롬프트 구성
        if use_lora:
            trigger = LORA_CONFIG["trigger_words"]
            full_prompt = f"{trigger}, {prompt}"
        else:
            full_prompt = prompt

        print(f"\n[Generating]")
        print(f"  Prompt: {full_prompt[:100]}...")
        print(f"  Size: {width}x{height}")
        print(f"  LoRA: {'ON' if use_lora else 'OFF'}")

        # Generator
        generator = torch.Generator(device="cpu").manual_seed(seed)

        # 생성
        cross_attention_kwargs = {"scale": lora_scale} if use_lora else None

        result = self.pipeline(
            prompt=full_prompt,
            negative_prompt="blurry, low quality, distorted, watermark, text, bad anatomy, ugly, deformed",
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            generator=generator,
            cross_attention_kwargs=cross_attention_kwargs,
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
            print("[SDXL] Model unloaded")


def test_disney_style():
    """Disney/Pixar 3D 스타일 테스트"""
    print("\n" + "=" * 60)
    print("Testing SDXL + 3D Disney LoRA")
    print("=" * 60)

    tester = SDXLDisneyLoRATester()

    # 테스트 프롬프트 (다양한 캐릭터/장면)
    test_cases = [
        {
            "prompt": "cute young girl with big eyes, wearing red dress, standing in magical forest, soft lighting, vibrant colors",
            "desc": "소녀 캐릭터"
        },
        {
            "prompt": "brave hero with cape, standing on rooftop at night, city lights background, dramatic lighting, epic pose",
            "desc": "영웅 캐릭터"
        },
        {
            "prompt": "cute robot character, round shape, big expressive eyes, friendly smile, sci-fi laboratory background",
            "desc": "로봇 캐릭터"
        },
        {
            "prompt": "magical creature, small dragon with big eyes, colorful scales, fantasy forest, sparkles",
            "desc": "판타지 크리처"
        },
    ]

    for i, case in enumerate(test_cases):
        print(f"\n--- Test {i+1}: {case['desc']} ---")

        image = tester.generate(
            prompt=case["prompt"],
            use_lora=True,
            seed=42 + i,
            width=768,
            height=1024,
            lora_scale=LORA_CONFIG["weight"],
        )

        # 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"disney_3d_test{i+1}_{timestamp}.png"
        image.save(output_path, quality=95)

        size_kb = os.path.getsize(output_path) / 1024
        print(f"  Saved: {output_path.name} ({size_kb:.1f} KB)")

    # 비교: LoRA 없이
    print("\n--- Comparison: Without LoRA ---")
    image = tester.generate(
        prompt="cute young girl with big eyes, wearing red dress, standing in magical forest, soft lighting, vibrant colors",
        use_lora=False,
        seed=42,
        width=768,
        height=1024,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"base_model_comparison_{timestamp}.png"
    image.save(output_path, quality=95)
    print(f"  Saved: {output_path.name}")

    tester.unload()
    print("\n[OK] All tests completed!")


def main():
    print("=" * 60)
    print("SDXL + 3D Disney LoRA Test")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")
    print(f"Base Model: {BASE_MODEL}")
    print(f"LoRA: 3D模型可爱化SDXL版 v2.0")
    print(f"Trigger: {LORA_CONFIG['trigger_words']}")
    print(f"GPU: RTX 3060 (6GB) - CPU offload mode")

    test_disney_style()

    # 결과 요약
    print("\n" + "=" * 60)
    print("Generated Files:")
    print("=" * 60)

    for f in sorted(OUTPUT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
