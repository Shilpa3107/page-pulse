# Page Pulse

A production-grade URL audit API — built for the Digital Heroes SDE qualification task.

**Live URL:** https://page-pulse-aa1t.onrender.com
**Interactive API docs:** https://page-pulse-aa1t.onrender.com/docs

> Note: this runs on Render's free tier, which spins down after periods of inactivity. The first request after idle time may take 30–60 seconds to respond while the instance wakes up.

## What it does

Given a URL, Page Pulse fetches it and reports:
- HTTP status code
- Response time (of the actual fetch)
- Page title (parsed from HTML `<title>`, when the response is HTML)
- Content length
- Whether the fetch succeeded, and if not, why (`TIMEOUT` or `CONNECTION_FAILED`)

## Design decisions and known tradeoffs

- **Rate limiting** uses a fixed-window counter (Redis `INCR` + `EXPIRE`), not a sliding window or token bucket. This is simple and easy to reason about, but has a known edge case: a client can send up to 2x their per-minute limit if requests land across a window boundary (e.g., late in one minute and early in the next).
- **Caching and rate limiting share one Redis instance** (Upstash, accessed via its REST API rather than a persistent TCP connection) — chosen for compatibility with free-tier serverless hosting, at the cost of slightly higher per-request latency than a native Redis client.
- **Client identification for rate limiting is by IP address** (`request.client.host`). Behind a reverse proxy (which Render's platform effectively is), this may not always reflect the true originating client unless `X-Forwarded-For` is explicitly read — this app does not currently do that.
- **Failed audits (timeout, connection error) are not cached** — only successful fetches are, so a transient outage doesn't get "stuck" as a cached failure for the full TTL window.
- **Automated tests mock all network and Redis calls** (via `httpx.MockTransport` and monkeypatching) rather than hitting live infrastructure in CI. This proves the application logic is correct but does not serve as an integration test against the real Upstash instance — that was verified manually during development instead.

## API Contract

### `POST /audit`

**Request body:**
```json
{
  "url": "https://example.com"
}
```
`url` must be a valid `http://` or `https://` URL — anything else returns a `422` before any network call is made.

**Success response (200):**
```json
{
  "url": "https://example.com",
  "status_code": 200,
  "response_time_ms": 203.05,
  "served_in_ms": 72.5,
  "title": "Example Domain",
  "content_length": 559,
  "success": true,
  "error": null,
  "cached": false
}
```
- `response_time_ms` — time taken by the actual HTTP fetch to the target URL.
- `served_in_ms` — total time this API took to respond, including cache lookup. On a cache hit, this is much smaller than `response_time_ms`, since no real fetch occurred.
- `cached` — `true` if this result was served from cache rather than a fresh fetch.

**Failure response (still 200, request succeeded — the *target* URL failed):**
```json
{
  "url": "https://slow-site.example.com",
  "status_code": null,
  "response_time_ms": 10023.4,
  "served_in_ms": 10023.9,
  "title": null,
  "content_length": 0,
  "success": false,
  "error": "TIMEOUT",
  "cached": false
}
```
`error` is one of `"TIMEOUT"` or `"CONNECTION_FAILED"`.

**Validation error (422):**
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Value error, URL must be a valid http:// or https:// address"
  }
}
```

**Rate limited (429):**
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please slow down."
  }
}
```

**Unhandled server error (500):**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Something went wrong on our end."
  }
}
```

## Configuration

Set via environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST endpoint | *(required)* |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST auth token | *(required)* |
| `CACHE_TTL_SECONDS` | How long a cached audit result stays valid | `300` |
| `RATE_LIMIT_PER_MINUTE` | Max requests per client IP per minute | `10` |

## Running locally

```bash
python -m venv venv
venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

Create a `.env` file with the variables listed above, then:

```bash
uvicorn app.main:app --reload
```

## Testing

```bash
pytest -v
```

7 tests covering core audit logic (success, timeout, connection failure, non-HTML handling) and the API layer (input validation, structured errors, rate limiting), all isolated from real network and Redis calls via mocking.

## CI

GitHub Actions runs the full test suite on every push to `main` — see `.github/workflows/ci.yml`.

## AI Usage

I used Claude to clarify concepts, discuss design decisions, and troubleshoot a few implementation issues during development. The application was implemented, tested, and refined by me, and I verified and adapted the suggestions to fit the project requirements before using them.

## Assumptions

- Audit scope is limited to status code, response time, page title, content length, and success/failure — deliberately not attempting SEO or accessibility checks, to keep Task A's scope proportionate to a solo build.
- Page title parsing is skipped for non-HTML responses (e.g. JSON, images) rather than attempted and returning nonsense.
- Failed audits (timeout, connection error) are not cached, so a target site's transient outage doesn't get "stuck" as a cached failure for the full TTL window.
- Rate limiting identifies clients by IP address; this doesn't account for shared IPs (e.g. behind a corporate NAT) or reverse proxies unless `X-Forwarded-For` handling is added.
- Task B's "live build requirement" footer note is read as applying to Task A's deployed service; Task B's own deliverables (architecture doc, tech decision record, failure analysis, observability plan) are documents, not a second live build.
