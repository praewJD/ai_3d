"""
Base API Client - 모든 API 클라이언트의 기본 클래스

기능:
- 재시도 로직 (exponential backoff)
- Rate limiting
- 타임아웃 처리
- 에러 핸들링
"""
import asyncio
import time
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import httpx
from abc import ABC, abstractmethod


class APIError(Exception):
    """API 에러 기본 클래스"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """Rate limit 초과 에러"""
    def __init__(self, retry_after: int = None):
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """인증 에러"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


@dataclass
class RetryPolicy:
    """재시도 정책"""
    max_retries: int = 3
    base_delay: float = 1.0  # 초
    max_delay: float = 60.0  # 초
    exponential_base: float = 2.0
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)

    def get_delay(self, attempt: int) -> float:
        """시도 횟수에 따른 대기 시간 계산"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class RateLimitConfig:
    """Rate limit 설정"""
    requests_per_minute: int = 60
    requests_per_second: int = 10
    burst_size: int = 20  # 초기 버스트 허용량


class RateLimiter:
    """
    Token Bucket 기반 Rate Limiter
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._tokens = config.burst_size
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """
        토큰 획득 (필요시 대기)

        Args:
            tokens: 필요한 토큰 수
        """
        async with self._lock:
            while True:
                now = time.time()
                elapsed = now - self._last_update
                self._last_update = now

                # 토큰 충전 (초당)
                self._tokens += elapsed * self.config.requests_per_second
                self._tokens = min(self._tokens, self.config.burst_size)

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                # 토큰이 부족하면 대기
                wait_time = (tokens - self._tokens) / self.config.requests_per_second
                await asyncio.sleep(wait_time)


class BaseAPIClient(ABC):
    """
    API 클라이언트 기본 클래스

    모든 외부 API 클라이언트가 상속받아야 함
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = None,
        timeout: float = 60.0,
        retry_policy: RetryPolicy = None,
        rate_limit_config: RateLimitConfig = None
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())

        # HTTP 클라이언트
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> None:
        """클라이언트 시작"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_default_headers()
            )

    async def close(self) -> None:
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_default_headers(self) -> Dict[str, str]:
        """기본 헤더"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        재시도 + Rate Limiting이 적용된 요청

        Args:
            method: HTTP 메서드
            endpoint: 엔드포인트 (base_url 이후)
            **kwargs: httpx.request에 전달할 인자

        Returns:
            httpx.Response

        Raises:
            APIError: API 호출 실패
        """
        if not self._client:
            await self.start()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                # Rate limit 대기
                await self.rate_limiter.acquire()

                # 요청 실행
                response = await self._client.request(method, url, **kwargs)

                # 성공
                if response.status_code < 400:
                    return response

                # Rate limit 초과
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.retry_policy.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(retry_after)

                # 인증 에러
                if response.status_code == 401:
                    raise AuthenticationError()

                # 재시도 가능한 에러
                if response.status_code in self.retry_policy.retryable_status_codes:
                    if attempt < self.retry_policy.max_retries:
                        delay = self.retry_policy.get_delay(attempt)
                        await asyncio.sleep(delay)
                        continue

                # 기타 에러
                raise APIError(
                    f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )

            except httpx.TimeoutException:
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.get_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise APIError("Request timeout")

            except httpx.RequestError as e:
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.get_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise APIError(f"Request error: {str(e)}")

        raise APIError("Max retries exceeded")

    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """GET 요청"""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """POST 요청"""
        return await self.request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> httpx.Response:
        """PUT 요청"""
        return await self.request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """DELETE 요청"""
        return await self.request("DELETE", endpoint, **kwargs)

    # ============================================================
    # 헬스체크 및 상태 확인
    # ============================================================

    @abstractmethod
    async def health_check(self) -> bool:
        """
        API 상태 확인

        Returns:
            정상 여부
        """
        pass

    async def get_usage(self) -> Dict[str, Any]:
        """
        API 사용량 조회 (구현 선택)

        Returns:
            사용량 정보
        """
        return {"available": True}
