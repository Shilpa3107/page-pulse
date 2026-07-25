from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.core.audit import audit_url, AuditResult

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