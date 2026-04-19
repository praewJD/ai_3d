# -*- coding: utf-8 -*-
"""
Prompt-based Character Consistency Test
프롬프트로 캐릭터 외형 고정한状态下로 2장 생성 테스트
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import httpx
import base64


async def test_prompt_consistency():
    """프롬프트 일관성 테스트 - 캐릭터 핵심 설명 고정"""

    api_key = os.getenv("STORY_API_KEY")

    # 캐릭터 핵심 설명 (고정)
    CHARACTER_CORE = (
        "A majestic golden tiger cub with lustrous golden-orange fur with darker orange stripes, "
        "warm expressive emerald green eyes with delicate black eyeliner, "
        "distinctive black forehead stripes arranged in W shape, "
        "soft rounded ears with pink inner ear, "
        "gentle warm smile, fluffy tail with black and orange stripes, "
        "disney 3d animation style, pixar quality, high detail, soft warm lighting"
    )

    #_scene 설명들 (장면만 변경)
    scene_prompts = [
        f"{CHARACTER_CORE}, standing proudly on a mossy rock in bamboo forest, morning light filtering through",
        f"{CHARACTER_CORE}, sitting contentedly on a wooden dock at sunset, golden hour lighting, gentle breeze"
    ]

    print("=" * 60)
    print("프롬프트 일관성 테스트 - 캐릭터核心 설명 고정")
    print("=" * 60)
    print(f"\n[캐릭터 핵심]\n{CHARACTER_CORE[:80]}...")

    output_dir = Path("outputs/prompt_consistency_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, scene_prompt in enumerate(scene_prompts, start=1):
        print(f"\n[*] 이미지 {i} 생성 중...")
        print(f"    프롬프트: {scene_prompt[:60]}...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "image-01",
            "prompt": scene_prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
        }

        output_path = output_dir / f"scene_{i}.png"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.minimax.io/v1/image_generation",
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("data") and data["data"].get("image_base64"):
                        # image_base64는 리스트
                        img_bytes = base64.b64decode(data["data"]["image_base64"][0])
                        with open(output_path, "wb") as f:
                            f.write(img_bytes)
                        print(f"    [OK] 저장됨: {output_path}")
                    else:
                        print(f"    [FAIL] data: {data}")
                else:
                    print(f"    [FAIL] HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(3)

    print("\n" + "=" * 60)
    print("완료! 두 이미지 비교:")
    print("  - 같은 Tiger Cub인가?")
    print("  - 눈 색, 줄무늬, 표정 같은가?")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_prompt_consistency())
