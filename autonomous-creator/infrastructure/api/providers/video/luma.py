"""
Luma Dream Machine Provider - Luma AI 비디오 생성 API

지원 모델:
- Ray 3.14 (Luma 자체)
- Kling 2.6 (고품질)
- Veo 3 / 3.1 (Google)
- Sora 2 (OpenAI)

가격 (2025.04 기준):
- Ray 3.14 1080p: 80 credits/초
- Kling 2.6 1080p: 29 credits/초 (오디오 포함 시 58)
- Veo 3 1080p: 140 credits/초
- Sora 2 720p: 35 credits/초
"""
import asyncio
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

from infrastructure.api.base_client import BaseAPIClient, APIError, RetryPolicy, RateLimitConfig
from infrastructure.api.providers.video.base import (
    BaseVideoProvider,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoGenerationStatus,
    VideoResolution
)


class LumaProvider(BaseVideoProvider, BaseAPIClient):
    """
    Luma Dream Machine API 프로바이더

    멀티모델 지원: Ray, Kling, Veo, Sora
    """

    PROVIDER_NAME = "luma"
    API_BASE_URL = "https://api.lumalabs.ai/dream-machine/v1"

    SUPPORTED_MODELS = [
        "ray-3.14",       # Luma 자체 모델
        "kling-2.6",      # Kling (아시아 콘텐츠 강점)
        "veo-3",          # Google Veo 3
        "veo-3.1",        # Google Veo 3.1
        "sora-2",         # OpenAI Sora 2
    ]
    DEFAULT_MODEL = "kling-2.6"

    # 모델별 크레딧 비용 (초당)
    CREDITS_PER_SECOND = {
        "ray-3.14": {
            "540p": 10,
            "720p": 20,
            "1080p": 80
        },
        "kling-2.6": {
            "720p": 29,
            "1080p": 29
        },
        "veo-3": {
            "720p": 140,
            "1080p": 140
        },
        "veo-3.1": {
            "720p": 140,
            "1080p": 140
        },
        "sora-2": {
            "720p": 35
        }
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = None,
        default_resolution: str = "1080p"
    ):
        # BaseVideoProvider 초기화
        BaseVideoProvider.__init__(self, api_key)

        # BaseAPIClient 초기화
        BaseAPIClient.__init__(
            self,
            base_url=self.API_BASE_URL,
            api_key=api_key,
            timeout=120.0,
            retry_policy=RetryPolicy(max_retries=3, base_delay=2.0),
            rate_limit_config=RateLimitConfig(
                requests_per_minute=30,
                requests_per_second=5
            )
        )

        self.default_model = default_model or self.DEFAULT_MODEL
        self.default_resolution = default_resolution

    def _get_default_headers(self) -> Dict[str, str]:
        """Luma API 헤더"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # ============================================================
    # 핵심 메서드
    # ============================================================

    async def generate(
        self,
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """
        비디오 생성 요청

        Luma API는 비동기이므로 ID만 반환하고 상태는 별도 조회
        """
        if not self._client:
            await self.start()

        # 엔드포인트 선택
        endpoint = "/generations"

        # 요청 바디 구성
        payload = self._build_request_payload(request)

        try:
            response = await self.post(endpoint, json=payload)
            data = response.json()

            return VideoGenerationResult(
                id=data.get("id", ""),
                status=self._map_status(data.get("status", "pending")),
                created_at=data.get("created_at", ""),
                credits_used=data.get("credits_used", 0)
            )

        except APIError as e:
            return VideoGenerationResult(
                id="",
                status=VideoGenerationStatus.FAILED,
                error_message=str(e)
            )

    async def get_status(self, generation_id: str) -> VideoGenerationResult:
        """생성 상태 조회"""
        if not self._client:
            await self.start()

        response = await self.get(f"/generations/{generation_id}")
        data = response.json()

        result = VideoGenerationResult(
            id=data.get("id", generation_id),
            status=self._map_status(data.get("status", "pending")),
            created_at=data.get("created_at", "")
        )

        # 완료된 경우 결과 URL
        if result.status == VideoGenerationStatus.COMPLETED:
            result.video_url = data.get("assets", {}).get("video")
            result.thumbnail_url = data.get("assets", {}).get("thumbnail")
            result.duration = data.get("metadata", {}).get("duration", 0)
            result.resolution = data.get("metadata", {}).get("resolution", "")
            result.credits_used = data.get("credits_used", 0)

        # 실패한 경우
        if result.status == VideoGenerationStatus.FAILED:
            result.error_message = data.get("error", {}).get("message", "Unknown error")

        return result

    async def download(
        self,
        result: VideoGenerationResult,
        output_path: str
    ) -> str:
        """비디오 다운로드"""
        if not result.video_url:
            raise ValueError("No video URL available")

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 다운로드
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.get(result.video_url)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        return output_path

    # ============================================================
    # 헬퍼 메서드
    # ============================================================

    def _build_request_payload(
        self,
        request: VideoGenerationRequest
    ) -> Dict[str, Any]:
        """API 요청 페이로드 구성"""
        model = request.model or self.default_model
        resolution = request.resolution.value if isinstance(request.resolution, VideoResolution) else self.default_resolution

        payload = {
            "model": model,
            "prompt": request.prompt,
            "resolution": resolution,
            "duration": request.duration
        }

        # 이미지 투비디오
        if request.image_path:
            payload["image"] = self._encode_image(request.image_path)

        # 고급 설정
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        if request.seed is not None:
            payload["seed"] = request.seed

        if request.style:
            payload["style"] = request.style

        # 모션 강도 (모델 지원 시)
        if request.motion_strength and model.startswith("ray"):
            payload["motion_strength"] = request.motion_strength

        return payload

    def _encode_image(self, image_path: str) -> str:
        """이미지를 base64로 인코딩"""
        import base64
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _map_status(self, luma_status: str) -> VideoGenerationStatus:
        """Luma 상태를 공통 상태로 매핑"""
        mapping = {
            "pending": VideoGenerationStatus.PENDING,
            "queued": VideoGenerationStatus.PENDING,
            "processing": VideoGenerationStatus.PROCESSING,
            "generating": VideoGenerationStatus.PROCESSING,
            "completed": VideoGenerationStatus.COMPLETED,
            "success": VideoGenerationStatus.COMPLETED,
            "failed": VideoGenerationStatus.FAILED,
            "error": VideoGenerationStatus.FAILED
        }
        return mapping.get(luma_status.lower(), VideoGenerationStatus.PENDING)

    # ============================================================
    # 정보 메서드
    # ============================================================

    async def estimate_cost(
        self,
        request: VideoGenerationRequest
    ) -> Dict[str, float]:
        """예상 비용 계산"""
        model = request.model or self.default_model
        resolution = request.resolution.value if isinstance(request.resolution, VideoResolution) else self.default_resolution

        # 모델별 크레딧 계산
        model_prices = self.CREDITS_PER_SECOND.get(model, {})
        credits_per_sec = model_prices.get(resolution, 50)  # 기본값

        total_credits = credits_per_sec * request.duration

        # Luma Pro 플랜 기준 (월 $90 = 9000 credits 가정)
        cost_usd = (total_credits / 9000) * 90 / 30  # 일일 비용

        return {
            "credits": total_credits,
            "usd": round(cost_usd, 4),
            "breakdown": {
                "per_second": credits_per_sec,
                "duration": request.duration,
                "resolution": resolution,
                "model": model
            }
        }

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """모델 상세 정보"""
        info = {
            "ray-3.14": {
                "name": "Ray 3.14",
                "provider": "Luma",
                "strengths": ["빠른 생성", "자연스러운 모션"],
                "resolutions": ["540p", "720p", "1080p"],
                "max_duration": 10,
                "recommended_for": "일반적인 비디오 생성"
            },
            "kling-2.6": {
                "name": "Kling 2.6",
                "provider": "Kuaishou (via Luma)",
                "strengths": ["아시아 콘텐츠", "인물 모션", "가성비"],
                "resolutions": ["720p", "1080p"],
                "max_duration": 10,
                "recommended_for": "아시아 캐릭터, 인물 영상"
            },
            "veo-3": {
                "name": "Veo 3",
                "provider": "Google (via Luma)",
                "strengths": ["고품질", "자연스러운 모션"],
                "resolutions": ["720p", "1080p"],
                "max_duration": 8,
                "recommended_for": "고품질 영상"
            },
            "sora-2": {
                "name": "Sora 2",
                "provider": "OpenAI (via Luma)",
                "strengths": ["창의적 영상", "복잡한 장면"],
                "resolutions": ["720p"],
                "max_duration": 20,
                "recommended_for": "실험적 영상"
            }
        }
        return info.get(model, {"name": model, "provider": "Unknown"})

    async def health_check(self) -> bool:
        """API 상태 확인"""
        try:
            if not self._client:
                await self.start()
            response = await self.get("/health")
            return response.status_code == 200
        except:
            return False


# ============================================================
# 팩토리 함수
# ============================================================

def create_luma_provider(
    api_key: str = None,
    model: str = None
) -> LumaProvider:
    """
    Luma 프로바이더 생성

    Args:
        api_key: API 키 (없으면 환경변수에서 로드)
        model: 기본 모델

    Returns:
        LumaProvider 인스턴스
    """
    if api_key is None:
        from infrastructure.api.config.api_config import get_api_config
        config = get_api_config()
        api_key = config.luma_api_key
        model = model or config.luma_default_model

    if not api_key:
        raise ValueError("Luma API key is required")

    return LumaProvider(api_key=api_key, default_model=model)
