from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

from bs4 import BeautifulSoup


def canonicalize_url(url: str) -> str:
    """
    Basic canonicalization:
    - strip fragment
    - drop common tracking params (utm_*)
    - normalize scheme/host casing
    """
    u = url.strip()
    p = urlparse(u)
    q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    new = p._replace(
        scheme=(p.scheme or "http").lower(),
        netloc=p.netloc.lower(),
        fragment="",
        query=urlencode(q, doseq=True),
    )
    return urlunparse(new)


_WS_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return normalize_text(soup.get_text(" ", strip=True))


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip())


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def simhash64(text: str) -> int:
    """
    Simple 64-bit simhash. Good enough for near-dup clustering later.
    """
    tokens = re.findall(r"[0-9A-Za-zА-Яа-яЁё]{3,}", (text or "").lower())
    if not tokens:
        return 0
    v = [0] * 64
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)  # noqa: S324 (ok for simhash)
        for i in range(64):
            bit = (h >> i) & 1
            v[i] += 1 if bit else -1
    out = 0
    for i in range(64):
        if v[i] >= 0:
            out |= 1 << i
    # PostgreSQL BIGINT is signed (int64). Convert unsigned 64-bit -> signed range.
    out &= (1 << 64) - 1
    if out >= (1 << 63):
        out -= 1 << 64
    return int(out)

