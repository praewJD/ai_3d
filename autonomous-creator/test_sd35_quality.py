# -*- coding: utf-8 -*-
"""
SD 3.5 품질 비교 테스트
- 프롬프트 개선
- 파라미터 조정
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

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\sd35_quality_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_image(pipeline, prompt, negative_prompt, seed, name, width=576, height=1024, steps=40, cfg=4.5):
    """이미지 생성"""
    print(f"\n{'='*60}")
    print(f"Generating: {name}")
    print(f"Steps: {steps}, CFG: {cfg}")
    print(f"{'='*60}")

    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipeline(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=steps,
        guidance_scale=cfg,
        width=width,
        height=height,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]
    timestamp = datetime.now().strftime("%H%M%S")
    output_path = OUTPUT_DIR / f"{name}_{timestamp}.png"
    image.save(output_path, quality=95)

    print(f"Time: {elapsed:.1f}s, Size: {output_path.stat().st_size / 1024:.0f} KB")
    return output_path


def main():
    print("=" * 60)
    print("SD 3.5 품질 비교 테스트")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if device == "cuda" else 0
    print(f"Device: {device}, VRAM: {vram:.1f} GB")

    # 모델 로드
    print("\nLoading SD 3.5 Medium...")
    from diffusers import StableDiffusion3Pipeline

    pipeline = StableDiffusion3Pipeline.from_pretrained(
        "stabilityai/stable-diffusion-3.5-medium",
        torch_dtype=torch.float16,
    )

    if vram < 12:
        print("Using CPU offload...")
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = pipeline.to(device)

    # ========== 태국 방콕 특화 프롬프트 ==========
    prompt1 = """Bangkok Thailand street at night, authentic Thai atmosphere,
    colorful tuk-tuks on the road, Thai language neon signs,
    pink and green taxis, street food vendors selling pad thai,
    wat temple silhouette in background, humid tropical atmosphere,
    photorealistic, 8k, cinematic lighting"""
    negative1 = "chinese, hong kong, japanese, korean, chinese characters, lanterns, chinese architecture"

    prompt2 = """Bangkok Sukhumvit Road Thailand, night scene,
    tuk-tuk drivers waiting for passengers, Thai food cart with som tam,
    pink taxi, green taxi, yellow taxi, BTS skytrain overhead,
    Thai script neon signs, street vendors, tropical palm trees,
    rainy season wet streets, authentic Bangkok photography,
    shot on location, National Geographic style"""
    negative2 = "chinese, hong kong, japan, korea, chinese text, chinese buildings, red lanterns, dragons"

    prompt3 = """Khao San Road Bangkok Thailand at night,
    backpacker area, tuk-tuks, Thai street food,
    young Thai locals, neon lights, chaotic energy,
    tropical humidity, authentic Southeast Asian atmosphere,
    documentary photography, raw, unfiltered"""
    negative3 = "chinese, east asian, hong kong, western, european, chinese architecture"

    # 실행
    results = []

    # Test 1: 기본 태국 프롬프트
    results.append(generate_image(pipeline, prompt1, negative1, seed=42, name="thai1_sukhumvit", steps=40, cfg=4.5))

    # Test 2: 구체적 태국 요소
    results.append(generate_image(pipeline, prompt2, negative2, seed=42, name="thai2_bts", steps=40, cfg=4.5))

    # Test 3: 카오산 로드
    results.append(generate_image(pipeline, prompt3, negative3, seed=42, name="thai3_khaosan", steps=40, cfg=4.5))

    # 결과 요약
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    for i, path in enumerate(results, 1):
        size = path.stat().st_size / 1024
        print(f"  {i}. {path.name} ({size:.0f} KB)")

    print(f"\nOutput folder: {OUTPUT_DIR}")

    del pipeline
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
