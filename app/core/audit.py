import time
import httpx
from pydantic import BaseModel
import asyncio
import time
import httpx
from pydantic import BaseModel

# Shared across all requests — created once at import time, not per-call.
CONCURRENCY_LIMIT = 10
_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


class AuditResult(BaseModel):
    url: str
    status_code: int | None
    response_time_ms: float
    title: str | None
    content_length: int
    success: bool
    error: str | None = None


async def audit_url(url: str) -> AuditResult:
    start = time.perf_counter()

    async with _semaphore:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            return AuditResult(
                url=url, status_code=None,
                response_time_ms=round((time.perf_counter() - start) * 1000, 2),
                title=None, content_length=0, success=False,
                error="TIMEOUT",
            )
        except httpx.ConnectError:
            return AuditResult(
                url=url, status_code=None,
                response_time_ms=round((time.perf_counter() - start) * 1000, 2),
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

    return AuditResult(
        url=url,
        status_code=response.status_code,
        response_time_ms=round(elapsed_ms, 2),
        title=title,
        content_length=len(response.content),
        success=response.is_success,
    )