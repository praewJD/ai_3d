# -*- coding: utf-8 -*-
"""
Character Consistency Test v3
type 값들을 테스트
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.api.providers.image.minimax_image import MiniMaxImageClient


async def test_type_variations():
    ref_image = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"

    if not Path(ref_image).exists():
        print(f"[ERROR] 참조 이미지 없음")
        return

    client = MiniMaxImageClient()

    prompt = "A majestic golden tiger with golden-orange fur, Disney 3D animation style"

    output_dir = Path("outputs/consistency_v3")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 다양한 type 값들 테스트
    types_to_test = ["character", "subject", "image", "reference", "style"]

    print("=" * 60)
    print("Test v3 - subject_reference type 값 테스트")
    print("=" * 60)

    for type_val in types_to_test:
        print(f"\n[*] Testing type='{type_val}'...")

        output_path = output_dir / f"test_type_{type_val}.png"

        # 직접 API 호출
        import httpx
        import base64

        with open(ref_image, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "image-01",
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "subject_reference": [
                {
                    "type": type_val,
                    "image_file": f"data:image/png;base64,{image_base64}"
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=client.timeout) as http_client:
                response = await http_client.post(
                    client.API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("data") and data["data"].get("image_base64"):
                        img_data = base64.b64decode(data["data"]["image_base64"][0])
                        with open(output_path, "wb") as f:
                            f.write(img_data)
                        print(f"    [OK] 저장됨: {output_path}")
                    else:
                        print(f"    [FAIL] data null: {data}")
                else:
                    print(f"    [FAIL] HTTP {response.status_code}: {response.text[:100]}")

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print("완료! 각 type 값별 결과 확인")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_type_variations())