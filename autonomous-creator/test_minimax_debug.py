# -*- coding: utf-8 -*-
"""
MiniMax API 응답 디버그
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def debug_minimax_response():
    """MiniMax API 원시 응답 확인"""
    api_key = os.getenv("STORY_API_KEY")
    api_url = os.getenv("STORY_API_URL", "https://api.minimax.io/anthropic/v1/messages")
    model = os.getenv("STORY_MODEL", "MiniMax-M2.7")

    print(f"API URL: {api_url}")
    print(f"Model: {model}")
    print(f"API Key: {api_key[:20]}..." if api_key else "No key")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": 100,
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "Say hello in Korean. Just say '안녕하세요'."}
        ],
    }

    print("\n[*] Sending request to MiniMax API...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(api_url, headers=headers, json=payload)
            print(f"[*] Status: {response.status_code}")
            print(f"[*] Response headers: {dict(response.headers)}")

            data = response.json()
            print(f"\n[*] Raw Response JSON:")
            print(data)

            # Try to extract text
            if "content" in data:
                print(f"\n[*] content field: {data['content']}")
                if isinstance(data["content"], list) and len(data["content"]) > 0:
                    print(f"[*] First element: {data['content'][0]}")

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_minimax_response())