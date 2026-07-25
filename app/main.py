import time
import uuid
from urllib.parse import urlparse

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from fastapi.responses import HTMLResponse

from app.core.audit import audit_url, AuditResult
from app.core.ratelimit import is_rate_limited

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

app = FastAPI(title="Page Pulse")


class AuditRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("URL must be a valid http:// or https:// address")
        return value


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    log = logger.bind(request_id=request_id, path=request.url.path, client_ip=client_ip)
    log.info("request_started")

    if request.url.path == "/audit":
        limited = await is_rate_limited(client_ip)
        if limited:
            log.info("rate_limit_exceeded")
            return error_response(429, "RATE_LIMITED", "Too many requests. Please slow down.")

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    log.info("request_finished", status_code=response.status_code, duration_ms=duration_ms)

    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    return error_response(422, "INVALID_INPUT", first_error["msg"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return error_response(500, "INTERNAL_ERROR", "Something went wrong on our end.")


@app.post("/audit", response_model=AuditResult)
async def audit(payload: AuditRequest) -> AuditResult:
    return await audit_url(payload.url)

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>Page Pulse</title>
            <style>
                * { box-sizing: border-box; }
                html, body {
                    height: 100%;
                    margin: 0;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    color: #1a1a1a;
                    line-height: 1.6;
                    display: flex;
                    flex-direction: column;
                    min-height: 100vh;
                }
                header {
                    padding: 20px 40px;
                    border-bottom: 1px solid #e5e5e5;
                }
                header .brand {
                    font-weight: 700;
                    font-size: 1.2em;
                }
                main {
                    flex: 1;
                    max-width: 680px;
                    width: 100%;
                    margin: 0 auto;
                    padding: 60px 24px;
                }
                h1 {
                    font-size: 2.4em;
                    margin-bottom: 0.1em;
                }
                .subtitle {
                    color: #555;
                    font-size: 1.1em;
                    margin-bottom: 32px;
                }
                .endpoint-box {
                    background: #f7f7f8;
                    border: 1px solid #e5e5e5;
                    border-radius: 8px;
                    padding: 20px 24px;
                    margin-bottom: 24px;
                }
                code {
                    background: #eee;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 0.9em;
                }
                a {
                    color: #2563eb;
                    text-decoration: none;
                }
                a:hover {
                    text-decoration: underline;
                }
                footer {
                    padding: 20px 40px;
                    border-top: 1px solid #e5e5e5;
                    font-size: 0.9em;
                    color: #666;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <header>
                <span class="brand">📡 Page Pulse</span>
            </header>
            <main>
                <h1>Page Pulse</h1>
                <p class="subtitle">A production-grade URL audit API — validation, timeouts, caching, rate limiting, and structured logging, built for real traffic.</p>
                <div class="endpoint-box">
                    <strong>POST</strong> <code>/audit</code>
                    <p style="margin-bottom:0;">Send a URL, get back its status, response time, title, and content length.</p>
                </div>
                <p>See <a href="/docs">/docs</a> for the full interactive API reference and request/response schema.</p>
            </main>
            <footer>
                Built for <a href="https://digitalheroesco.com" target="_blank">Digital Heroes Training Task</a>
            </footer>
        </body>
    </html>
    """
