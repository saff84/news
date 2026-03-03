from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    reason: str | None = None


def _robots_url(url: str) -> str:
    p = urlparse(url)
    scheme = (p.scheme or "http").lower()
    netloc = (p.netloc or "").lower()
    return f"{scheme}://{netloc}/robots.txt"


def _download_robots(robots_url: str, *, timeout_s: float = 10.0) -> str | None:
    headers = {"User-Agent": "NewsIntParser/0.1"}
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
            r = client.get(robots_url)
            if r.status_code >= 400:
                return None
            return r.text
    except Exception:
        return None


def can_fetch(
    url: str,
    *,
    user_agent: str = "NewsIntParser",
    redis=None,
    cache_ttl_s: int = 6 * 60 * 60,
) -> RobotsDecision:
    """
    Best-effort robots.txt check.

    - If robots.txt cannot be fetched/parsed: allow (but provide reason).
    - Cache robots.txt text in Redis to avoid repeated downloads.
    """
    robots_url = _robots_url(url)
    cache_key = f"robots:{robots_url}"

    txt: str | None = None
    if redis is not None:
        try:
            cached = redis.get(cache_key)
            if cached:
                txt = cached.decode("utf-8", errors="ignore")
        except Exception:
            txt = None

    if txt is None:
        txt = _download_robots(robots_url)
        if txt is None:
            return RobotsDecision(allowed=True, reason="robots_unavailable")
        if redis is not None:
            try:
                redis.setex(cache_key, cache_ttl_s, txt)
            except Exception:
                pass

    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        # RobotFileParser expects split lines, but parse() accepts list[str]
        rp.parse(txt.splitlines())
        allowed = bool(rp.can_fetch(user_agent, url))
        return RobotsDecision(allowed=allowed, reason=None if allowed else "robots_disallow")
    except Exception:
        return RobotsDecision(allowed=True, reason="robots_parse_error")

