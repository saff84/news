from __future__ import annotations

import datetime as dt
import gzip
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class SitemapUrl:
    loc: str
    lastmod: dt.datetime | None = None


def _parse_lastmod(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    raw = s.strip()
    if not raw:
        return None
    try:
        # ISO-8601-ish; tolerate trailing Z
        v = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _strip_ns(tag: str) -> str:
    # "{namespace}tag" -> "tag"
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag
def _download(url: str, *, timeout_s: float = 25.0) -> bytes:
    headers = {"User-Agent": "NewsIntParser/0.1"}
    with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def _maybe_gunzip(url: str, content: bytes) -> bytes:
    if url.lower().endswith(".gz"):
        return gzip.decompress(content)
    # Some servers omit .gz in URL but send gzip content; try sniffing.
    if content[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(content)
        except Exception:
            return content
    return content


def _iter_sitemap_locs(xml_bytes: bytes) -> tuple[str, Iterable[ET.Element]]:
    root = ET.fromstring(xml_bytes)
    root_tag = _strip_ns(root.tag)
    return root_tag, list(root)


def fetch_sitemap_urls(
    sitemap_url: str,
    *,
    max_sitemaps: int = 20,
    max_urls_total: int = 5000,
    include_regex: str | None = None,
    exclude_regex: str | None = None,
) -> list[SitemapUrl]:
    """
    Fetch a sitemap.xml (or sitemap index) and return URLs with optional lastmod.

    Supports:
    - urlset
    - sitemapindex (one level deep by default)
    - .gz sitemaps
    """
    include_re = re.compile(include_regex) if include_regex else None
    exclude_re = re.compile(exclude_regex) if exclude_regex else None

    out: list[SitemapUrl] = []
    to_visit: list[str] = [sitemap_url]
    visited: set[str] = set()

    while to_visit and len(visited) < max_sitemaps and len(out) < max_urls_total:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        raw = _download(url)
        xml_bytes = _maybe_gunzip(url, raw)

        # Basic sanity check: if server returned HTML error page, ET will fail anyway.
        try:
            kind, children = _iter_sitemap_locs(xml_bytes)
        except Exception as e:
            raise RuntimeError(f"Failed to parse sitemap XML: {url}") from e

        if kind == "sitemapindex":
            for el in children:
                if _strip_ns(el.tag) != "sitemap":
                    continue
                loc_el = None
                for ch in list(el):
                    if _strip_ns(ch.tag) == "loc":
                        loc_el = ch
                        break
                if loc_el is None or not (loc_el.text or "").strip():
                    continue
                to_visit.append((loc_el.text or "").strip())
            continue

        if kind != "urlset":
            # Unknown root type; treat as empty
            continue

        for el in children:
            if _strip_ns(el.tag) != "url":
                continue
            loc = None
            lastmod = None
            for ch in list(el):
                tag = _strip_ns(ch.tag)
                if tag == "loc" and (ch.text or "").strip():
                    loc = (ch.text or "").strip()
                elif tag == "lastmod" and (ch.text or "").strip():
                    lastmod = _parse_lastmod(ch.text)
            if not loc:
                continue
            if include_re and not include_re.search(loc):
                continue
            if exclude_re and exclude_re.search(loc):
                continue
            out.append(SitemapUrl(loc=loc, lastmod=lastmod))
            if len(out) >= max_urls_total:
                break

    return out


def same_origin(a: str, b: str) -> bool:
    pa = urlparse(a)
    pb = urlparse(b)
    return (pa.scheme or "").lower() == (pb.scheme or "").lower() and (pa.netloc or "").lower() == (pb.netloc or "").lower()

