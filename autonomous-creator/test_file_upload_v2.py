# -*- coding: utf-8 -*-
"""
MiniMax File Upload API Test v2
"""
import asyncio
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


async def test_file_upload():
    """파일 업로드 API 테스트 v2"""

    api_key = os.getenv("STORY_API_KEY")
    file_path = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"

    if not Path(file_path).exists():
        print(f"[ERROR] 파일 없음: {file_path}")
        return

    print("=" * 60)
    print("MiniMax File Upload API Test v2")
    print("=" * 60)

    endpoint = "https://api.minimax.io/v1/files/upload"

    # 다양한 purpose 값들 시도
    purposes = ["image", "reference", "character", "subject", "temp", "file"]

    for purpose in purposes:
        print(f"\n[*] Trying purpose='{purpose}'...")

        try:
            with open(file_path, "rb") as f:
                files = {"file": ("reference.png", f, "image/png")}
                data = {"purpose": purpose}
                headers = {"Authorization": f"Bearer {api_key}"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        data=data,
                        files=files,
                    )

                    if response.status_code == 200:
                        resp_data = response.json()
                        if resp_data.get("file"):
                            print(f"    [OK] 업로드 성공!")
                            print(f"    File info: {resp_data['file']}")
                        else:
                            print(f"    [FAIL] {resp_data}")
                    else:
                        print(f"    [FAIL] HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(1)

    print("\n완료")


if __name__ == "__main__":
    asyncio.run(test_file_upload())