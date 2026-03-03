"""Keyword-based filtering for news items at ingestion time."""

from __future__ import annotations


def _normalize(s: str) -> str:
    return (s or "").lower().strip()


def _to_list(v: object) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [_normalize(x) for x in v if isinstance(x, str) and _normalize(x)]
    if isinstance(v, str):
        return [_normalize(x) for x in v.replace(",", "\n").split() if _normalize(x)]
    return []


def should_keep_item(text: str, settings_json: dict | None) -> bool:
    """
    Decide whether to keep a news item based on source's keyword filters.

    - include_keywords: if non-empty, item must contain at least one (OR). Empty = no filter.
    - exclude_keywords: if item contains any of these, skip. Empty = no filter.

    Matching is case-insensitive, substring-based.
    """
    cfg = settings_json or {}
    include = _to_list(cfg.get("include_keywords"))
    exclude = _to_list(cfg.get("exclude_keywords"))

    haystack = _normalize(text or "")

    if exclude:
        for kw in exclude:
            if kw and kw in haystack:
                return False

    if include:
        for kw in include:
            if kw and kw in haystack:
                return True
        return False

    return True
