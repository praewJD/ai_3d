"""
Stability AI SD 3.5 API Client

Stable Diffusion 3.5 Large API 연동
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import aiohttp
import logging
import asyncio
import base64

logger = logging.getLogger(__name__)


@dataclass
class SD35GenerationResult:
    """SD 3.5 생성 결과"""
    success: bool
    image_data: Optional[bytes] = None
    seed: int = 0
    finish_reason: str = ""
    api_cost_usd: float = 0.0
    error_message: str = ""


class StabilitySD35Client:
    """
    Stability AI SD 3.5 API Client

    Docs: https://platform.stability.ai/docs/api-reference#tag/Generate/paths/~1v2beta~1stable-image~1generate~1sd3/post
    """

    API_HOST = "https://api.stability.ai"
    DEFAULT_MODEL = "sd3.5-large"

    # 비용 (2026 기준)
    COSTS = {
        "sd3.5-large": 0.04,
        "sd3.5-large-turbo": 0.03,
        "sd3.5-medium": 0.025,
    }

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        max_retries: int = 3,
        timeout: int = 120
    ):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = f"{self.API_HOST}/v2beta/stable-image/generate/sd3"

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        aspect_ratio: str = "16:9",
        seed: int = -1,
        output_format: str = "png",
        model: str = None
    ) -> SD35GenerationResult:
        """
        이미지 생성

        Args:
            prompt: 긍정 프롬프트
            negative_prompt: 부정 프롬프트
            aspect_ratio: 비율 (1:1, 16:9, 21:9, 3:2, 2:3, 4:5, 5:4, 9:16, 9:21)
            seed: 시드 (-1이면 랜덤)
            output_format: 출력 포맷 (png, jpeg, webp)
            model: 모델 오버라이드

        Returns:
            SD35GenerationResult
        """
        model = model or self.model

        # FormData 준비
        data = aiohttp.FormData()
        data.add_field('prompt', prompt)
        data.add_field('mode', 'text-to-image')
        data.add_field('model', model)
        data.add_field('aspect_ratio', aspect_ratio)
        data.add_field('output_format', output_format)

        if negative_prompt:
            data.add_field('negative_prompt', negative_prompt)

        if seed > 0:
            data.add_field('seed', str(seed))

        # API 호출
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        headers=self._get_headers(),
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 200:
                            image_data = await response.read()

                            return SD35GenerationResult(
                                success=True,
                                image_data=image_data,
                                seed=seed if seed > 0 else self._extract_seed(response),
                                finish_reason="SUCCESS",
                                api_cost_usd=self.COSTS.get(model, 0.04)
                            )

                        elif response.status == 429:
                            # Rate limit
                            retry_after = int(response.headers.get('retry-after', 60))
                            logger.warning(f"Rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue

                        else:
                            error_text = await response.text()
                            logger.error(f"API error: {response.status} - {error_text}")

                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue

                            return SD35GenerationResult(
                                success=False,
                                error_message=f"API error {response.status}: {error_text}"
                            )

            except asyncio.TimeoutError:
                logger.warning(f"Timeout, attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue

                return SD35GenerationResult(
                    success=False,
                    error_message="Request timeout"
                )

            except aiohttp.ClientError as e:
                logger.error(f"Network error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue

                return SD35GenerationResult(
                    success=False,
                    error_message=str(e)
                )

        return SD35GenerationResult(
            success=False,
            error_message="Max retries exceeded"
        )

    async def generate_with_reference(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image: Path = None,
        strength: float = 0.35,
        seed: int = -1
    ) -> SD35GenerationResult:
        """
        참조 이미지 기반 생성

        Args:
            prompt: 프롬프트
            negative_prompt: 부정 프롬프트
            reference_image: 참조 이미지 경로
            strength: 참조 영향도 (0.0-1.0)
            seed: 시드

        Returns:
            SD35GenerationResult
        """
        if not reference_image or not reference_image.exists():
            return SD35GenerationResult(
                success=False,
                error_message="Reference image not found"
            )

        # FormData 준비
        data = aiohttp.FormData()
        data.add_field('prompt', prompt)
        data.add_field('mode', 'image-to-image')
        data.add_field('model', self.model)
        data.add_field('strength', str(strength))

        if negative_prompt:
            data.add_field('negative_prompt', negative_prompt)

        if seed > 0:
            data.add_field('seed', str(seed))

        # 참조 이미지 추가
        with open(reference_image, 'rb') as f:
            data.add_field(
                'init_image',
                f,
                filename=reference_image.name,
                content_type='image/png'
            )

        # API 호출 (generate와 동일한 로직)
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        headers=self._get_headers(),
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            return SD35GenerationResult(
                                success=True,
                                image_data=image_data,
                                seed=seed,
                                finish_reason="SUCCESS",
                                api_cost_usd=self.COSTS.get(self.model, 0.04)
                            )
                        elif response.status == 429:
                            retry_after = int(response.headers.get('retry-after', 60))
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_text = await response.text()
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return SD35GenerationResult(
                                success=False,
                                error_message=f"API error {response.status}: {error_text}"
                            )
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return SD35GenerationResult(
                    success=False,
                    error_message=str(e)
                )

        return SD35GenerationResult(
            success=False,
            error_message="Max retries exceeded"
        )

    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "image/*"
        }

    def _extract_seed(self, response) -> int:
        """응답에서 시드 추출"""
        # Stability API는 시드를 헤더나 메타데이터로 반환할 수 있음
        seed_header = response.headers.get('seed')
        if seed_header:
            return int(seed_header)
        return 0

    async def check_credits(self) -> Dict[str, Any]:
        """크레딧 확인"""
        url = f"{self.API_HOST}/v1/user/balance"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"error": f"Status {response.status}"}
        except Exception as e:
            return {"error": str(e)}


# 편의 함수
_client: Optional[StabilitySD35Client] = None


def get_stability_client(api_key: str = None) -> StabilitySD35Client:
    """Stability 클라이언트 싱글톤"""
    global _client
    if _client is None or api_key:
        _client = StabilitySD35Client(api_key=api_key)
    return _client
