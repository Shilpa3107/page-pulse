import asyncio
import time
import httpx
from pydantic import BaseModel

from app.core.cache import get_cached, set_cached

CONCURRENCY_LIMIT = 10
_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


class AuditResult(BaseModel):
    url: str
    status_code: int | None
    response_time_ms: float
    served_in_ms: float
    title: str | None
    content_length: int
    success: bool
    error: str | None = None
    cached: bool = False


async def audit_url(url: str) -> AuditResult:
    request_start = time.perf_counter()

    cached_value = await get_cached(url)
    if cached_value is not None:
        try:
            result = AuditResult.model_validate_json(cached_value)
            result.cached = True
            result.served_in_ms = round((time.perf_counter() - request_start) * 1000, 2)
            return result
        except Exception:
            # Stale or schema-incompatible cache entry — treat as a cache miss
            # rather than letting deserialization failure crash the request.
            pass

    start = time.perf_counter()

    async with _semaphore:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            return AuditResult(
                url=url, status_code=None,
                response_time_ms=round((time.perf_counter() - start) * 1000, 2),
                served_in_ms=round((time.perf_counter() - request_start) * 1000, 2),
                title=None, content_length=0, success=False,
                error="TIMEOUT",
            )
        except httpx.ConnectError:
            return AuditResult(
                url=url, status_code=None,
                response_time_ms=round((time.perf_counter() - start) * 1000, 2),
                served_in_ms=round((time.perf_counter() - request_start) * 1000, 2),
                title=None, content_length=0, success=False,
                error="CONNECTION_FAILED",
            )

    elapsed_ms = (time.perf_counter() - start) * 1000

    title = None
    if "text/html" in response.headers.get("content-type", ""):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.title:
            title = soup.title.string

    result = AuditResult(
        url=url,
        status_code=response.status_code,
        response_time_ms=round(elapsed_ms, 2),
        served_in_ms=round((time.perf_counter() - request_start) * 1000, 2),
        title=title,
        content_length=len(response.content),
        success=response.is_success,
    )

    await set_cached(url, result.model_dump_json())
    return result