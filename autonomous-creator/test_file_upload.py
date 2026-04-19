# -*- coding: utf-8 -*-
"""
MiniMax File Upload API Test
"""
import asyncio
import httpx
import os
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


async def test_file_upload():
    """파일 업로드 API 테스트"""

    api_key = os.getenv("STORY_API_KEY")

    # 다양한 업로드 엔드포인트 시도
    upload_endpoints = [
        "https://api.minimax.io/v1/files/upload",
        "https://api.minimax.io/v1/upload",
        "https://api.minimax.io/v1/image/upload",
    ]

    file_path = "outputs/character_consistency_test/char_1_Shan,_the_Golden_Tiger_ref.png"

    if not Path(file_path).exists():
        print(f"[ERROR] 파일 없음: {file_path}")
        return

    print("=" * 60)
    print("MiniMax File Upload API Test")
    print("=" * 60)

    for endpoint in upload_endpoints:
        print(f"\n[*] Trying: {endpoint}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": ("reference.png", f, "image/png")}
                headers = {"Authorization": f"Bearer {api_key}"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        files=files,
                    )

                    print(f"    Status: {response.status_code}")
                    print(f"    Response: {response.text[:500]}")

                    if response.status_code == 200:
                        data = response.json()
                        print(f"    [OK] 업로드 성공!")
                        print(f"    Data: {data}")
                        return data

        except Exception as e:
            print(f"    [ERROR] {e}")

        await asyncio.sleep(1)

    print("\n[FAIL] 모든 업로드 엔드포인트 실패")


if __name__ == "__main__":
    asyncio.run(test_file_upload())