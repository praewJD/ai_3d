# -*- coding: utf-8 -*-
"""
MiniMax Image API Debug
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def debug_minimax_image():
    """MiniMax 이미지 API 디버그"""
    api_key = os.getenv("STORY_API_KEY")
    url = "https://api.minimax.io/v1/image_generation"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "image-01",
        "prompt": "A cute golden retriever puppy, Disney 3D style",
        "image_size": "1024x1024",
        "num_images": 1,
    }

    print(f"[*] URL: {url}")
    print(f"[*] Key: {api_key[:20]}..." if api_key else "No key")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"[*] Status: {response.status_code}")
            print(f"[*] Response: {response.text}")
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(debug_minimax_image())