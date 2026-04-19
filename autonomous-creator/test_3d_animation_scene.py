# -*- coding: utf-8 -*-
"""
3D 애니메이션 장면 생성 테스트

배경이 포함된 애니메이션의 한 장면처럼 생성
- Disney Pixar style, 3D render, Octane render, C4D
- 시네마틱 조명, 배경 포함
"""
import os
import sys
import torch
from pathlib import Path
from datetime import datetime

# Windows UTF-8 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

OUTPUT_DIR = Path(r"D:\AI-Video\autonomous-creator\output\3d_animation_scenes")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 3D 애니메이션 스타일 고정 키워드
# ============================================================
STYLE_3D_ANIMATION = (
    "Disney Pixar style, 3D animation, 3D render, Octane render, C4D, "
    "cinematic lighting, volumetric lighting, ray tracing, "
    "high quality, 8k resolution, movie scene, "
    "soft shadows, ambient occlusion, subsurface scattering"
)

STYLE_3D_NEGATIVE = (
    "realistic, photorealistic, photograph, 2D, flat, "
    "low quality, blurry, distorted, deformed, "
    "ugly, bad anatomy, extra limbs, "
    "watermark, signature, text, logo, grainy"
)

# 애니메이션 장면 프롬프트 템플릿
SCENE_TEMPLATE = (
    "{style_prefix}, "
    "{scene_description}, "
    "{character_description}, "
    "{mood_lighting}, "
    "cinematic composition, rule of thirds, "
    "depth of field, bokeh effect"
)

# 미리 정의된 장면 템플릿들
SCENE_PRESETS = {
    "cozy_room": {
        "scene": "cozy bedroom interior, warm sunlight through window, dust particles in air, books and toys scattered, soft blankets",
        "mood": "warm golden hour lighting, soft ambient light, cozy atmosphere"
    },
    "forest_adventure": {
        "scene": "magical forest path, giant mushrooms, glowing fireflies, ancient trees with bioluminescent leaves, misty atmosphere",
        "mood": "mystical blue moonlight, ethereal glow, enchanting atmosphere"
    },
    "city_night": {
        "scene": "bustling city street at night, neon signs, rain reflections on pavement, steam rising from vents, tall buildings",
        "mood": "cyberpunk neon lighting, purple and blue ambient, cinematic noir"
    },
    "ocean_sunset": {
        "scene": "beautiful beach at sunset, gentle waves, seashells on sand, distant lighthouse, seagulls flying",
        "mood": "warm orange and pink sunset lighting, golden hour, peaceful atmosphere"
    },
    "snowy_mountain": {
        "scene": "snowy mountain peak, northern lights in sky, pine trees covered in snow, ice crystals sparkling",
        "mood": "cold blue ambient lighting, aurora borealis glow, majestic atmosphere"
    },
    "underwater": {
        "scene": "colorful coral reef underwater, tropical fish swimming, sunlight rays through water, bubbles rising",
        "mood": "soft blue underwater lighting, caustic light patterns, serene atmosphere"
    }
}

# 캐릭터 프리셋
CHARACTER_PRESETS = {
    "robot": "cute round robot with big glowing eyes and antenna, metallic body with warm light",
    "girl": "young girl with short blue hair wearing yellow raincoat, curious expression",
    "cat": "fluffy orange cat with big green eyes wearing red collar, playful pose",
    "bear": "cute brown teddy bear with round glasses, holding a honey pot",
    "alien": "small friendly alien with big black eyes and green skin, wearing space suit"
}

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


def generate_animation_scene(
    scene_preset: str = "cozy_room",
    character_preset: str = "robot",
    custom_character: str = None,
    custom_scene: str = None,
    width: int = 1024,
    height: int = 576,  # 16:9 영상 비율
    steps: int = 40,
    cfg_scale: float = 4.5,
    seed: int = 42
) -> tuple:
    """
    3D 애니메이션 장면 생성

    Args:
        scene_preset: 장면 프리셋 이름
        character_preset: 캐릭터 프리셋 이름
        custom_character: 커스텀 캐릭터 설명 (우선)
        custom_scene: 커스텀 장면 설명 (우선)
        width: 이미지 너비
        height: 이미지 높이
        steps: inference steps
        cfg_scale: guidance scale
        seed: 랜덤 시드

    Returns:
        (image, prompt, output_path)
    """
    # 장면 설정
    if custom_scene:
        scene_desc = custom_scene
        mood = "cinematic lighting, atmospheric"
    elif scene_preset in SCENE_PRESETS:
        scene_desc = SCENE_PRESETS[scene_preset]["scene"]
        mood = SCENE_PRESETS[scene_preset]["mood"]
    else:
        scene_desc = SCENE_PRESETS["cozy_room"]["scene"]
        mood = SCENE_PRESETS["cozy_room"]["mood"]

    # 캐릭터 설정
    if custom_character:
        char_desc = custom_character
    elif character_preset in CHARACTER_PRESETS:
        char_desc = CHARACTER_PRESETS[character_preset]
    else:
        char_desc = CHARACTER_PRESETS["robot"]

    # 프롬프트 조합
    prompt = SCENE_TEMPLATE.format(
        style_prefix=STYLE_3D_ANIMATION,
        scene_description=scene_desc,
        character_description=char_desc,
        mood_lighting=mood
    )

    print(f"\n{'='*60}")
    print(f"Scene: {scene_preset}")
    print(f"Character: {character_preset}")
    print(f"{'='*60}")
    print(f"\nPrompt (first 200 chars):")
    print(f"{prompt[:200]}...")

    # 파이프라인 로드
    pipe = get_pipeline()

    # 이미지 생성
    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=prompt,
        negative_prompt=STYLE_3D_NEGATIVE,
        num_inference_steps=steps,
        guidance_scale=cfg_scale,
        width=width,
        height=height,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]

    # 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"3d_scene_{scene_preset}_{character_preset}_{timestamp}.png"
    output_path = OUTPUT_DIR / filename

    image.save(output_path, quality=95)

    print(f"\nDone!")
    print(f"Time: {elapsed:.1f}s")
    print(f"Saved: {output_path}")

    return image, prompt, str(output_path)


def generate_custom_scene(
    description: str,
    seed: int = 42
) -> tuple:
    """
    자유로운 설명으로 장면 생성

    Args:
        description: 장면 설명 (캐릭터 + 배경 + 분위기)
        seed: 랜덤 시드
    """
    prompt = f"{STYLE_3D_ANIMATION}, {description}, cinematic composition, depth of field"

    print(f"\n{'='*60}")
    print(f"Custom Scene")
    print(f"{'='*60}")
    print(f"\nPrompt (first 200 chars):")
    print(f"{prompt[:200]}...")

    pipe = get_pipeline()
    generator = torch.Generator(device="cpu").manual_seed(seed)

    start = datetime.now()
    result = pipe(
        prompt=prompt,
        negative_prompt=STYLE_3D_NEGATIVE,
        num_inference_steps=40,
        guidance_scale=4.5,
        width=1024,
        height=576,
        generator=generator,
    )
    elapsed = (datetime.now() - start).total_seconds()

    image = result.images[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"3d_scene_custom_{timestamp}.png"
    output_path = OUTPUT_DIR / filename
    image.save(output_path, quality=95)

    print(f"\nDone!")
    print(f"Time: {elapsed:.1f}s")
    print(f"Saved: {output_path}")

    return image, prompt, str(output_path)


def main():
    """테스트 실행"""
    print("=" * 60)
    print("3D Animation Scene Generator")
    print("Style: Disney Pixar / Cinematic / Full Scene")
    print("=" * 60)

    # 테스트 장면들
    test_scenes = [
        {"scene": "cozy_room", "character": "girl", "seed": 42},
        {"scene": "forest_adventure", "character": "cat", "seed": 42},
        {"scene": "city_night", "character": "robot", "seed": 42},
        {"scene": "ocean_sunset", "character": "bear", "seed": 42},
    ]

    results = []
    for config in test_scenes:
        try:
            image, prompt, path = generate_animation_scene(
                scene_preset=config["scene"],
                character_preset=config["character"],
                seed=config["seed"]
            )
            results.append((config["scene"], config["character"], path))
        except Exception as e:
            print(f"Error: {e}")

    # 결과 요약
    print(f"\n{'='*60}")
    print("Results Summary")
    print("=" * 60)
    for scene, char, path in results:
        if Path(path).exists():
            size = Path(path).stat().st_size / 1024
            print(f"  {scene}/{char}: {Path(path).name} ({size:.0f} KB)")

    print(f"\nOutput folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
