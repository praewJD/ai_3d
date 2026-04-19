# -*- coding: utf-8 -*-
"""
자동 이미지 생성 - 타이틀만 입력하면 자동으로 프롬프트 확장 + 이미지 생성
"""
import os
import sys
import torch
from pathlib import Path
from datetime import datetime

# Windows UTF-8 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from prompt_expander import expand_prompt

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\auto_generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

pipeline = None


def get_pipeline():
    """파이프라인 로드 (한 번만)"""
    global pipeline
    if pipeline is not None:
        return pipeline

    print("Loading SD 3.5 Medium...")
    from diffusers import StableDiffusion3Pipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if device == "cuda" else 0
    print(f"Device: {device}, VRAM: {vram:.1f} GB")

    pipeline = StableDiffusion3Pipeline.from_pretrained(
        "stabilityai/stable-diffusion-3.5-medium",
        torch_dtype=torch.float16,
    )

    if vram < 12:
        print("Using CPU offload...")
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = pipeline.to(device)

    return pipeline


def generate_from_title(title: str, mood: str = "cinematic", seed: int = 42):
    """타이틀만 입력하면 자동으로 이미지 생성"""
    print(f"\n{'='*60}")
    print(f"Input: {title}")
    print(f"Mood: {mood}")
    print("=" * 60)

    # 프롬프트 확장
    positive, negative = expand_prompt(title, mood)

    print(f"\nExpanded prompt:")
    print(f"P: {positive[:100]}...")
    print(f"N: {negative[:80]}...")

    # 파이프라인 로드
    pipe = get_pipeline()

    # 이미지 생성
    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=positive,
        negative_prompt=negative,
        num_inference_steps=40,
        guidance_scale=4.5,
        width=576,
        height=1024,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]

    # 파일명 생성
    safe_title = title.replace(" ", "_").replace("의", "-")
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{safe_title}_{timestamp}.png"
    output_path = OUTPUT_DIR / filename

    image.save(output_path, quality=95)

    print(f"\nDone!")
    print(f"Time: {elapsed:.1f}s")
    print(f"Saved: {output_path}")

    return output_path


def main():
    print("=" * 60)
    print("Auto Image Generator - Title -> Prompt -> Image")
    print("=" * 60)

    # 테스트 타이틀들
    titles = [
        "방콕의 밤",
        "서울의 밤",
        "도쿄의 밤",
    ]

    results = []
    for title in titles:
        path = generate_from_title(title, mood="cinematic", seed=42)
        results.append((title, path))

    # 결과 요약
    print(f"\n{'='*60}")
    print("Results Summary")
    print("=" * 60)
    for title, path in results:
        size = path.stat().st_size / 1024
        print(f"  {title}: {path.name} ({size:.0f} KB)")

    print(f"\nOutput folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
