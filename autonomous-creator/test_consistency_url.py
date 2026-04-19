# -*- coding: utf-8 -*-
"""
Character Consistency Test - External URL
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


async def test_with_url():
    """외부 URL로 참조 이미지 테스트"""

    ref_url = "https://img.freepik.com/premium-photo/3d-cute-smile-little-tiger-kawaii-character-realistic-cub-with-big-eyes_726113-2506.jpg"

    print("=" * 60)
    print("Character Consistency Test - External URL")
    print("=" * 60)
    print(f"참조: {ref_url}")

    api_key = os.getenv("STORY_API_KEY")
    if not api_key:
        print("[ERROR] API key not found")
        return

    prompt = "A cute tiger cub with orange fur, big eyes, smiling, Disney 3D animation style, Pixar quality"

    output_dir = Path("outputs/consistency_url")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3가지 테스트
    tests = [
        ("base64_local", "로컬 파일 base64"),
        ("url_direct", "외부 URL 직접"),
        ("prompt_focus", "프롬프트 집중형"),
    ]

    for test_name, desc in tests:
        print(f"\n[*] Test: {test_name} ({desc})")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if test_name == "base64_local":
            # 로컬 파일 base64
            local_file = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"
            if Path(local_file).exists():
                with open(local_file, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()
                image_file = f"data:image/png;base64,{image_data}"
            else:
                print("    [SKIP] 로컬 파일 없음")
                continue

        elif test_name == "url_direct":
            # 외부 URL 직접 사용
            image_file = ref_url

        elif test_name == "prompt_focus":
            # 프롬프트에 캐릭터 상세 설명 집중
            image_file = ref_url
            prompt = "A majestic golden tiger with luxurious golden-orange fur, warm expressive eyes, gentle smile, soft lighting, Disney 3D animation style, Pixar quality, high detail"

        payload = {
            "model": "image-01",
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "subject_reference": [
                {
                    "type": "character",
                    "image_file": image_file
                }
            ]
        }

        output_path = output_dir / f"{test_name}.png"

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
                        print(f"    [OK] 저장됨: {output_path}")
                    else:
                        print(f"    [FAIL] data null: {data}")
                else:
                    print(f"    [FAIL] HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print("완료! 결과 확인:")
    print("  base64_local.png - 로컬 파일 base64")
    print("  url_direct.png - 외부 URL 직접")
    print("  prompt_focus.png - 프롬프트 집중형")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_with_url())