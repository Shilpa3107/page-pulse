import time
import httpx
from pydantic import BaseModel


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

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

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