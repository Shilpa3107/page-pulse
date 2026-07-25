import os
import time

from app.core.cache import _redis_client

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 10))


async def is_rate_limited(client_id: str) -> bool:
    current_minute = int(time.time() // 60)
    key = f"ratelimit:{client_id}:{current_minute}"

    count = await _redis_client.incr(key)
    if count == 1:
        # First request in this window — set the key to expire after 60s
        await _redis_client.expire(key, 60)

    return count > RATE_LIMIT_PER_MINUTE