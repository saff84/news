from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from readability import Document


@dataclass
class ExtractedArticle:
    url: str
    title: str | None
    published_at_raw: str | None
    published_at: datetime | None
    author: str | None
    body_text: str | None
    body_html: str | None


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _text_or_none(el) -> str | None:
    if not el:
        return None
    txt = el.get_text(" ", strip=True)
    return _norm_space(txt) if txt else None


def _attr_or_text(el, attr: str | None) -> str | None:
    if not el:
        return None
    if attr:
        v = el.get(attr)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return _text_or_none(el)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # Minimal parser (expand later with rules in template):
    # - ISO8601-like
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_html(url: str, *, timeout_s: float = 20.0) -> str:
    headers = {"User-Agent": "NewsIntParser/0.1 (+https://example.invalid)"}
    with httpx.Client(follow_redirects=True, timeout=timeout_s, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def extract_from_html(url: str, html: str, template_json: dict[str, Any]) -> ExtractedArticle:
    soup = BeautifulSoup(html, "lxml")

    detail = (template_json or {}).get("detail", {}) or {}
    cleanup = (template_json or {}).get("cleanup", {}) or {}

    # Cleanup: remove nodes matching CSS selectors
    for css in cleanup.get("remove_css", []) or []:
        for el in soup.select(css):
            el.decompose()

    title_sel = (detail.get("title") or {}).get("css")
    title_attr = (detail.get("title") or {}).get("attr")
    date_sel = (detail.get("date") or {}).get("css")
    date_attr = (detail.get("date") or {}).get("attr")
    author_sel = (detail.get("author") or {}).get("css")
    author_attr = (detail.get("author") or {}).get("attr")
    body_sel = (detail.get("body") or {}).get("css")

    title = _attr_or_text(soup.select_one(title_sel) if title_sel else None, title_attr)
    published_at_raw = _attr_or_text(soup.select_one(date_sel) if date_sel else None, date_attr)
    author = _attr_or_text(soup.select_one(author_sel) if author_sel else None, author_attr)

    body_el = soup.select_one(body_sel) if body_sel else None
    body_html = str(body_el) if body_el else None
    body_text = _text_or_none(body_el)

    # Readability fallback if no body selector or very short
    min_len = int((template_json or {}).get("min_fulltext_length") or 200)
    if not body_text or len(body_text) < min_len:
        doc = Document(html)
        body_html = doc.summary(html_partial=True)
        body_text = _text_or_none(BeautifulSoup(body_html, "lxml"))
        if not title:
            title = _norm_space(doc.short_title()) if doc.short_title() else None

    return ExtractedArticle(
        url=url,
        title=title,
        published_at_raw=published_at_raw,
        published_at=_parse_datetime(published_at_raw),
        author=author,
        body_text=body_text,
        body_html=body_html,
    )


def extract_with_template(url: str, template_json: dict[str, Any]) -> ExtractedArticle:
    """
    Minimal, working extraction for detail pages (title/date/author/body) using CSS selectors.
    Template format will be expanded, but this already supports the Admin dry-run flow.
    """
    html = fetch_html(url)
    return extract_from_html(url, html, template_json)

