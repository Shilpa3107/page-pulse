import os
import hashlib

from upstash_redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()

_redis_client = Redis(
    url=os.environ["UPSTASH_REDIS_REST_URL"],
    token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
)
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 300))


def _cache_key(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()
    return f"audit:{digest}"


async def get_cached(url: str) -> str | None:
    return await _redis_client.get(_cache_key(url))


async def set_cached(url: str, result_json: str) -> None:
    await _redis_client.set(_cache_key(url), result_json, ex=CACHE_TTL_SECONDS)