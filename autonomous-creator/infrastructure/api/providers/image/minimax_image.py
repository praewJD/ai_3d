"""
MiniMax Image Generation API Client

MiniMax T2I (Text-to-Image) API 연동
"""
import httpx
import base64
import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()


@dataclass
class MiniMaxImageResult:
    """이미지 생성 결과"""
    success: bool
    image_data: Optional[bytes] = None
    image_url: Optional[str] = None
    seed: int = 0
    error_message: str = ""


class MiniMaxImageClient:
    """
    MiniMax Image Generation API Client

    MiniMax API를 사용한 텍스트→이미지 생성
    """

    API_URL = "https://api.minimax.io/v1/image_generation"
    MODEL = "image-01"

    def __init__(
        self,
        api_key: str = None,
        timeout: int = 120
    ):
        self.api_key = api_key or os.getenv("MINIMAX_IMAGE_API_KEY") or os.getenv("STORY_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("MiniMax API key not found. Set MINIMAX_IMAGE_API_KEY or STORY_API_KEY")

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        aspect_ratio: str = "1:1",
        response_format: str = "base64",
    ) -> MiniMaxImageResult:
        """
        이미지 생성

        Args:
            prompt: 프롬프트
            negative_prompt: 네거티브 프롬프트 (현재 미지원)
            aspect_ratio: 비율 (1:1, 16:9, 9:16, etc)
            response_format: "base64" 또는 "url"

        Returns:
            MiniMaxImageResult
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": response_format,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_response(data)
                else:
                    error_text = response.text
                    logger.error(f"MiniMax Image API error: {response.status_code} - {error_text}")
                    return MiniMaxImageResult(
                        success=False,
                        error_message=f"API error {response.status_code}: {error_text}"
                    )

        except Exception as e:
            logger.error(f"MiniMax Image API error: {e}")
            return MiniMaxImageResult(
                success=False,
                error_message=str(e)
            )

    async def generate_and_save(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: str = "",
        aspect_ratio: str = "1:1",
    ) -> MiniMaxImageResult:
        """이미지 생성 후 파일로 저장"""
        result = await self.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            response_format="base64",
        )

        if result.success and result.image_data:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(result.image_data)

        return result

    async def generate_with_reference(
        self,
        prompt: str,
        reference_image_path: str,
        aspect_ratio: str = "16:9",
        response_format: str = "base64",
    ) -> MiniMaxImageResult:
        """
        참조 이미지로 캐릭터 일관성 유지しながら 이미지 생성

        Args:
            prompt: 프롬프트
            reference_image_path: 참조 이미지 경로 (캐릭터 일관성용)
            aspect_ratio: 비율 (1:1, 16:9, 9:16)
            response_format: "base64" 또는 "url"

        Returns:
            MiniMaxImageResult
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 참조 이미지 base64 인코딩 (png 형식)
        with open(reference_image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": response_format,
            "subject_reference": [
                {
                    "type": "character",
                    "image_file": f"data:image/png;base64,{image_base64}"
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_response(data)
                else:
                    error_text = response.text
                    logger.error(f"MiniMax Image API error: {response.status_code} - {error_text}")
                    return MiniMaxImageResult(
                        success=False,
                        error_message=f"API error {response.status_code}: {error_text}"
                    )

        except Exception as e:
            logger.error(f"MiniMax Image API error: {e}")
            return MiniMaxImageResult(
                success=False,
                error_message=str(e)
            )

    async def generate_with_reference_and_save(
        self,
        prompt: str,
        reference_image_path: str,
        output_path: str,
        aspect_ratio: str = "16:9",
    ) -> MiniMaxImageResult:
        """참조 이미지로 캐릭터 일관성 유지 + 파일 저장"""
        result = await self.generate_with_reference(
            prompt=prompt,
            reference_image_path=reference_image_path,
            aspect_ratio=aspect_ratio,
            response_format="base64",
        )

        if result.success and result.image_data:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(result.image_data)

        return result

    def _parse_response(self, data: Dict[str, Any]) -> MiniMaxImageResult:
        """응답 파싱"""
        try:
            # MiniMax API 응답: { data: { image_base64: ["base64...", ...] } }
            if "data" in data:
                data_item = data["data"]

                if isinstance(data_item, dict):
                    image_base64_list = data_item.get("image_base64")

                    # 리스트인 경우 (실제 응답)
                    if isinstance(image_base64_list, list) and len(image_base64_list) > 0:
                        return MiniMaxImageResult(
                            success=True,
                            image_data=base64.b64decode(image_base64_list[0]),
                            seed=data.get("seed", 0),
                        )
                    # 문자열인 경우 (폴백)
                    elif isinstance(image_base64_list, str):
                        return MiniMaxImageResult(
                            success=True,
                            image_data=base64.b64decode(image_base64_list),
                            seed=data.get("seed", 0),
                        )

            return MiniMaxImageResult(
                success=False,
                error_message=f"Unexpected response format: {data}"
            )

        except Exception as e:
            return MiniMaxImageResult(
                success=False,
                error_message=f"Parse error: {e}"
            )


async def test_minimax_image():
    """MiniMax 이미지 생성 테스트"""
    print("=" * 60)
    print("MiniMax Image Generation API Test")
    print("=" * 60)

    prompt = "A cute golden retriever puppy playing in a park, Disney 3D animation style, Pixar quality, vibrant colors"

    try:
        client = MiniMaxImageClient()

        print(f"[*] Generating image...")
        print(f"[*] Prompt: {prompt[:50]}...")

        result = await client.generate_and_save(
            prompt=prompt,
            output_path="outputs/test_minimax_image.png",
            aspect_ratio="1:1",
        )

        if result.success:
            print(f"[OK] Image saved to: outputs/test_minimax_image.png")
        else:
            print(f"[FAIL] {result.error_message}")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_minimax_image())