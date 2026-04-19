# -*- coding: utf-8 -*-
"""
Character Consistency Final Test
Freepik 이미지로 subject_reference 재확인
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


async def test():
    # Freepik tiger cub 이미지
    ref_url = "https://img.freepik.com/premium-photo/3d-cute-smile-little-tiger-kawaii-character-realistic-cub-with-big-eyes_726113-2506.jpg"

    api_key = os.getenv("STORY_API_KEY")

    print("=" * 60)
    print("Freepik 이미지로 subject_reference 재확인")
    print("=" * 60)

    # 같은 참조로 3번 생성 (일관성 테스트)
    prompts = [
        "A cute tiger cub in a forest, Disney 3D animation style",
        "A cute tiger cub playing with butterflies, Disney 3D animation style",
        "A cute tiger cub sleeping on a cloud, Disney 3D animation style",
    ]

    output_dir = Path("outputs/consistency_final")
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, prompt in enumerate(prompts, start=1):
        print(f"\n[*] 시도 {i}: {prompt[:50]}...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "image-01",
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "subject_reference": [
                {
                    "type": "character",
                    "image_file": ref_url
                }
            ]
        }

        output_path = output_dir / f"test_{i}.png"

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
                        img_bytes = base64.b64decode(data["data"]["image_base64"][0])
                        with open(output_path, "wb") as f:
                            f.write(img_bytes)
                        print(f"    [OK] 저장됨")
                    else:
                        print(f"    [FAIL] {data}")
                else:
                    print(f"    [FAIL] HTTP {response.status_code}")

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print("완료! 3개 이미지가 모두 같은 Tiger Cub인가 확인")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())