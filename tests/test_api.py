from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.audit import AuditResult
import app.main as main_module

client = TestClient(app)


def make_fake_result():
    return AuditResult(
        url="https://example.com",
        status_code=200,
        response_time_ms=100.0,
        served_in_ms=100.0,
        title="Example",
        content_length=500,
        success=True,
        error=None,
        cached=False,
    )


def test_valid_request_returns_audit_result(monkeypatch):
    monkeypatch.setattr(main_module, "is_rate_limited", AsyncMock(return_value=False))
    monkeypatch.setattr(main_module, "audit_url", AsyncMock(return_value=make_fake_result()))

    response = client.post("/audit", json={"url": "https://example.com"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["title"] == "Example"


def test_invalid_url_returns_structured_error(monkeypatch):
    monkeypatch.setattr(main_module, "is_rate_limited", AsyncMock(return_value=False))

    response = client.post("/audit", json={"url": "not-a-url"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_INPUT"


def test_rate_limit_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(main_module, "is_rate_limited", AsyncMock(return_value=True))
    mock_audit = AsyncMock(return_value=make_fake_result())
    monkeypatch.setattr(main_module, "audit_url", mock_audit)

    response = client.post("/audit", json={"url": "https://example.com"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    mock_audit.assert_not_called()