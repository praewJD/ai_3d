# -*- coding: utf-8 -*-
"""
SD 3.5 이미지 생성 테스트
"""
import sys
import io
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import torch
from pathlib import Path
from datetime import datetime

# 출력 경로
OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\sd35_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("=" * 60)
    print("SD 3.5 Medium 이미지 생성 테스트")
    print("=" * 60)

    # 프롬프트
    prompt = """Bangkok street at night, neon lights, busy road with cars and tuk-tuks,
    vibrant city atmosphere, wet pavement reflections, cinematic lighting,
    photorealistic, 4k, detailed, night photography"""

    negative_prompt = """blurry, low quality, distorted, cartoon, anime,
    watermark, text, signature, oversaturated, underexposed"""

    print(f"\nPrompt: {prompt[:80]}...")

    # 디바이스 확인
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    if device == "cuda":
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"VRAM: {vram:.1f} GB")

    # 모델 로드
    print("\n[1/3] Loading SD 3.5 Medium...")
    from diffusers import StableDiffusion3Pipeline

    pipeline = StableDiffusion3Pipeline.from_pretrained(
        "stabilityai/stable-diffusion-3.5-medium",
        torch_dtype=torch.float16,
    )

    # 6GB VRAM용 CPU offload
    if device == "cuda" and vram < 12:
        print("Enabling CPU offload for low VRAM...")
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = pipeline.to(device)

    print("[2/3] Generating image...")

    # 시드 설정
    seed = 42
    generator = torch.Generator(device="cpu").manual_seed(seed)

    # 이미지 생성 (세로 비율 9:16)
    start_time = datetime.now()

    result = pipeline(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=28,
        guidance_scale=7.0,
        width=576,
        height=1024,
        generator=generator,
    )

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Generation time: {elapsed:.1f}s")

    # 저장
    print("[3/3] Saving...")
    image = result.images[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"bangkok_night_{timestamp}.png"
    image.save(output_path, quality=95)

    size_mb = output_path.stat().st_size / 1024
    print(f"\n{'='*60}")
    print(f"SUCCESS!")
    print(f"  File: {output_path}")
    print(f"  Size: {size_mb:.1f} KB")
    print(f"  Resolution: {image.width}x{image.height}")
    print(f"{'='*60}")

    # 메모리 정리
    del pipeline
    torch.cuda.empty_cache()

    return str(output_path)


if __name__ == "__main__":
    main()
