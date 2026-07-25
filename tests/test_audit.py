import httpx
import pytest

from app.core import audit

# Save the real class before any test patches httpx.AsyncClient —
# make_client must always build with the real one, never the patched name.
_RealAsyncClient = httpx.AsyncClient


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    """Bypass Redis entirely for these tests — we're testing audit logic,
    not caching, and we don't want a live Redis dependency in unit tests."""
    async def fake_get_cached(url):
        return None

    async def fake_set_cached(url, value):
        return None

    monkeypatch.setattr(audit, "get_cached", fake_get_cached)
    monkeypatch.setattr(audit, "set_cached", fake_set_cached)


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return _RealAsyncClient(transport=transport)


async def test_successful_html_audit(monkeypatch):
    def handler(request):
        html = "<html><head><title>Test Page</title></head><body></body></html>"
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: make_client(handler))

    result = await audit.audit_url("https://fake-test-site.com")

    assert result.success is True
    assert result.status_code == 200
    assert result.title == "Test Page"
    assert result.error is None


async def test_non_html_response_skips_title_parsing(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, text='{"a": 1}')

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: make_client(handler))

    result = await audit.audit_url("https://fake-test-site.com/data")

    assert result.success is True
    assert result.title is None


async def test_timeout_returns_structured_error(monkeypatch):
    def handler(request):
        raise httpx.TimeoutException("simulated timeout")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: make_client(handler))

    result = await audit.audit_url("https://fake-slow-site.com")

    assert result.success is False
    assert result.error == "TIMEOUT"
    assert result.status_code is None


async def test_connection_error_returns_structured_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("simulated connection failure")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: make_client(handler))

    result = await audit.audit_url("https://fake-unreachable-site.com")

    assert result.success is False
    assert result.error == "CONNECTION_FAILED"