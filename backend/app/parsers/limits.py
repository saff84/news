from __future__ import annotations

import time
from urllib.parse import urlparse

from redis import Redis


def domain_key(url: str) -> str:
    p = urlparse(url)
    return (p.hostname or "unknown").lower()


def acquire_rate_slot(
    redis: Redis,
    *,
    scope: str,
    max_per_minute: int,
    delay_ms: int = 0,
) -> None:
    """
    Very small Redis rate limiter:
    - fixed 60s window via INCR + EXPIRE
    - optional delay for politeness
    """
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    if max_per_minute <= 0:
        return
    key = f"rate:{scope}:{int(time.time() // 60)}"
    n = redis.incr(key)
    if n == 1:
        redis.expire(key, 70)
    if n > max_per_minute:
        # Simple backoff: sleep until next minute window
        to_sleep = 60 - (time.time() % 60)
        time.sleep(max(0.0, to_sleep))

