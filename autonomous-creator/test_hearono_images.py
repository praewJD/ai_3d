# -*- coding: utf-8 -*-
"""
Hearono Episode 1 - Image Generation Test

SD 3.5 + IP-Adapter로 장면 이미지 생성
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, str(Path(__file__).parent))

OUTPUT_DIR = Path("D:/AI-Video/autonomous-creator/output/hearono_ep1/images")

# 장면별 프롬프트
SCENES = [
    {
        "name": "scene_01_raven_enters",
        "prompt": "male adult, average build, dark hair, wearing black armor, air tubes, menacing look, standing on rooftop, Bangkok futuristic cityscape at night, neon lights, cyberpunk atmosphere, cinematic lighting, 8k, detailed",
        "negative": "blurry, low quality, watermark, text, female, bright colors, cartoon"
    },
    {
        "name": "scene_02_hearono_reveals",
        "prompt": "male young adult, short dark hair, wearing hooded cloak, large headphones around neck, determined eyes, standing on rooftop edge, Bangkok 20xx night skyline, neon city lights, dramatic lighting, cinematic composition, 8k",
        "negative": "blurry, low quality, watermark, text, villain, evil, dark, female"
    },
    {
        "name": "scene_03_final_battle",
        "prompt": "male young adult hero jumping, short dark hair, hooded cloak flowing, large headphones, sonic energy waves around fist, punching futuristic transmitter device, Bangkok night rooftop, blue energy glow, action scene, dynamic pose, cinematic, 8k",
        "negative": "blurry, low quality, watermark, text, static pose, female"
    },
    {
        "name": "scene_04_headphones",
        "prompt": "single large headphone left on concrete rooftop floor, smoke clearing, Bangkok futuristic night cityscape in background, dramatic lighting, cinematic aftermath scene, melancholic atmosphere, 8k, detailed",
        "negative": "blurry, low quality, watermark, text, people, characters"
    }
]


async def test_image_generation():
    """SD 3.5로 이미지 생성"""
    print("\n" + "="*60)
    print("  Hearono Episode 1 - Image Generation Test")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Output: {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from infrastructure.image.sd35_generator import SD35Generator
        from core.domain.entities.preset import StylePreset

        # 제너레이터 생성
        print("\n[1/3] Loading SD 3.5 Medium...")
        generator = SD35Generator()

        # 모델 로드
        await generator.load_model()
        print("  Model loaded!")

        # 프리셋 설정
        preset = StylePreset(
            name="cinematic",
            base_prompt="cinematic composition, film grain, professional photography",
            negative_prompt="blurry, low quality, watermark, text, oversaturated",
            steps=30,
            cfg_scale=7.0,
            seed=42
        )

        # 각 장면 생성
        print(f"\n[2/3] Generating {len(SCENES)} scene images...")
        image_paths = []

        for i, scene in enumerate(SCENES):
            print(f"\n  Scene {i+1}: {scene['name']}")
            print(f"    Prompt: {scene['prompt'][:60]}...")

            output_path = str(OUTPUT_DIR / f"{scene['name']}.png")

            try:
                result = await generator.generate(
                    prompt=scene['prompt'],
                    preset=preset,
                    output_path=output_path,
                    width=576,
                    height=1024
                )

                size = os.path.getsize(result) / 1024
                print(f"    Done: {size:.1f} KB")
                image_paths.append(result)

            except Exception as e:
                print(f"    Error: {e}")

        # 결과 요약
        print(f"\n[3/3] Summary")
        print(f"  Generated: {len(image_paths)}/{len(SCENES)} images")
        print(f"  Output: {OUTPUT_DIR}")

        # 모델 언로드
        await generator.unload_model()

        print("\n" + "="*60)
        print("  Image Generation Complete!")
        print("="*60)

        return image_paths

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    asyncio.run(test_image_generation())
