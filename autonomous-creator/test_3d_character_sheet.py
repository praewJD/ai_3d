# -*- coding: utf-8 -*-
"""
3D 스타일 캐릭터 시트 생성 테스트

3D 스타일은 '디자인 가이드'를 만드는 과정:
- Disney Pixar style, 3D render, Octane render, C4D, claymation 등 구체적 키워드
- 캐릭터 시트(Character Sheet): 앞, 옆, 뒤 모습이 담긴 시트를 먼저 생성
- 이를 영상 모델의 Reference Image로 사용
"""
import os
import sys
import torch
from pathlib import Path
from datetime import datetime

# Windows UTF-8 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\3d_character_sheets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 3D 스타일 고정 키워드
# ============================================================
STYLE_3D_PREFIX = (
    "Disney Pixar style, 3D render, Octane render, C4D, "
    "claymation, smooth shading, soft lighting, "
    "high quality 3D model, professional character design, "
    "turnaround sheet, character reference sheet"
)

STYLE_3D_NEGATIVE = (
    "realistic, photorealistic, photograph, 2D, flat, "
    "low quality, blurry, distorted, deformed, "
    "ugly, bad anatomy, extra limbs, "
    "watermark, signature, text, logo"
)

# 캐릭터 시트 프롬프트 템플릿
CHARACTER_SHEET_TEMPLATE = (
    "{style_prefix}, "
    "character sheet, turnaround view, "
    "front view, side view, back view, "
    "same character shown from multiple angles, "
    "white background, clean design, "
    "{character_description}"
)

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


def generate_character_sheet(
    character_description: str,
    style_prefix: str = STYLE_3D_PREFIX,
    negative_prompt: str = STYLE_3D_NEGATIVE,
    width: int = 1024,
    height: int = 576,  # 가로 형식 (시트에 적합)
    steps: int = 40,
    cfg_scale: float = 4.5,
    seed: int = 42
) -> tuple:
    """
    3D 스타일 캐릭터 시트 생성

    Args:
        character_description: 캐릭터 설명 (예: "cute robot with round head")
        style_prefix: 3D 스타일 키워드
        negative_prompt: 부정 프롬프트
        width: 이미지 너비
        height: 이미지 높이
        steps: inference steps
        cfg_scale: guidance scale
        seed: 랜덤 시드

    Returns:
        (image, prompt, output_path)
    """
    # 프롬프트 조합
    prompt = CHARACTER_SHEET_TEMPLATE.format(
        style_prefix=style_prefix,
        character_description=character_description
    )

    print(f"\n{'='*60}")
    print(f"Character: {character_description}")
    print(f"{'='*60}")
    print(f"\nPrompt:")
    print(f"P: {prompt}")
    print(f"N: {negative_prompt}")

    # 파이프라인 로드
    pipe = get_pipeline()

    # 이미지 생성
    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=steps,
        guidance_scale=cfg_scale,
        width=width,
        height=height,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]

    # 파일명 생성
    safe_desc = character_description.replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"3d_sheet_{safe_desc}_{timestamp}.png"
    output_path = OUTPUT_DIR / filename

    image.save(output_path, quality=95)

    print(f"\nDone!")
    print(f"Time: {elapsed:.1f}s")
    print(f"Saved: {output_path}")

    return image, prompt, str(output_path)


def generate_single_view(
    character_description: str,
    view_type: str = "front",  # front, side, back
    reference_style: str = None,
    seed: int = 42
):
    """
    단일 뷰 생성 (필요시 사용)

    Args:
        character_description: 캐릭터 설명
        view_type: 뷰 타입 (front/side/back)
        reference_style: 추가 스타일 참조
        seed: 랜덤 시드
    """
    view_prompts = {
        "front": "front view, facing camera, full body",
        "side": "side view, profile, full body",
        "back": "back view, from behind, full body"
    }

    prompt = (
        f"{STYLE_3D_PREFIX}, "
        f"{view_prompts.get(view_type, view_prompts['front'])}, "
        f"{character_description}"
    )

    if reference_style:
        prompt += f", {reference_style}"

    pipe = get_pipeline()
    generator = torch.Generator(device="cpu").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        negative_prompt=STYLE_3D_NEGATIVE,
        num_inference_steps=40,
        guidance_scale=4.5,
        width=576,
        height=1024,
        generator=generator,
    )

    image = result.images[0]

    # 저장
    safe_desc = character_description.replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"3d_{view_type}_{safe_desc}_{timestamp}.png"
    output_path = OUTPUT_DIR / filename
    image.save(output_path, quality=95)

    return image, str(output_path)


def main():
    """테스트 실행"""
    print("=" * 60)
    print("3D Character Sheet Generator")
    print("Style: Disney Pixar / 3D Render / Octane / C4D")
    print("=" * 60)

    # 테스트 캐릭터들
    test_characters = [
        # 기본 테스트
        "cute round robot with big eyes and antenna",

        # 인간형 캐릭터
        "young girl with short blue hair wearing yellow raincoat",

        # 동물 캐릭터
        "fluffy orange cat with big green eyes wearing a red collar",
    ]

    results = []
    for desc in test_characters:
        try:
            image, prompt, path = generate_character_sheet(
                character_description=desc,
                seed=42
            )
            results.append((desc, path))
        except Exception as e:
            print(f"Error generating '{desc}': {e}")

    # 결과 요약
    print(f"\n{'='*60}")
    print("Results Summary")
    print("=" * 60)
    for desc, path in results:
        if Path(path).exists():
            size = Path(path).stat().st_size / 1024
            print(f"  {desc[:30]}: {Path(path).name} ({size:.0f} KB)")

    print(f"\nOutput folder: {OUTPUT_DIR}")
    print("\nTIP: 생성된 캐릭터 시트를 영상 모델의 Reference Image로 사용하세요!")


if __name__ == "__main__":
    main()
