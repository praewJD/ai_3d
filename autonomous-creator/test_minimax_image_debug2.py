# -*- coding: utf-8 -*-
"""
MiniMax Image API Debug v2
"""
import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def debug():
    api_key = os.getenv("STORY_API_KEY")
    url = "https://api.minimax.io/v1/image_generation"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "image-01",
        "prompt": "A cute puppy, Disney 3D style",
        "aspect_ratio": "1:1",
        "response_format": "base64",
    }

    print(f"[*] URL: {url}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        print(f"[*] Status: {response.status_code}")

        try:
            data = response.json()
            print(f"[*] Response type: {type(data)}")
            print(f"[*] Response keys: {data.keys() if isinstance(data, dict) else 'N/A'}")

            if "data" in data:
                d = data["data"]
                print(f"[*] data type: {type(d)}")
                if isinstance(d, list):
                    print(f"[*] data length: {len(d)}")
                    if len(d) > 0:
                        print(f"[*] data[0] keys: {d[0].keys() if isinstance(d[0], dict) else d[0]}")
                elif isinstance(d, dict):
                    print(f"[*] data keys: {d.keys()}")

            print(f"\n[*] Full response:\n{json.dumps(data, indent=2, ensure_ascii=False)[:2000]}")

        except Exception as e:
            print(f"[ERROR] {e}")
            print(f"[TEXT] {response.text[:1000]}")

if __name__ == "__main__":
    asyncio.run(debug())