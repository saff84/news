"""Keyword-based filtering for news items at ingestion time."""

from __future__ import annotations

import re
from typing import Any


def _normalize(s: str) -> str:
    return (s or "").lower().strip()


def parse_keyword_list(v: object) -> list[str]:
    """Список ключей из массива, строки с запятыми или построчно."""
    if v is None:
        return []
    if isinstance(v, list):
        return [_normalize(x) for x in v if isinstance(x, str) and _normalize(x)]
    if isinstance(v, str):
        parts: list[str] = []
        for line in v.replace(",", "\n").replace(";", "\n").split("\n"):
            for token in line.split():
                t = _normalize(token)
                if t:
                    parts.append(t)
        return parts
    return []


def _keyword_hits(haystack: str, keywords: list[str], *, whole_words: bool) -> list[str]:
    if not haystack or not keywords:
        return []
    found: list[str] = []
    for kw in keywords:
        if not kw:
            continue
        if whole_words:
            if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", haystack, flags=re.UNICODE):
                found.append(kw)
        elif kw in haystack:
            found.append(kw)
    return found


def merge_filter_settings(
    source_settings: dict | None,
    global_settings: dict | None,
) -> dict[str, Any]:
    """
    Глобальные минус-слова добавляются к локальным exclude.
    Глобальные плюс-слова (если заданы) объединяются с локальными include (OR внутри списка).
  match_whole_words берётся из глобальных настроек, если включено.
    """
    src = source_settings or {}
    glob = global_settings or {}

    include = parse_keyword_list(src.get("include_keywords")) + parse_keyword_list(
        glob.get("global_include_keywords")
    )
    # dedupe preserving order
    include = list(dict.fromkeys(include))

    exclude = parse_keyword_list(src.get("exclude_keywords")) + parse_keyword_list(
        glob.get("global_exclude_keywords")
    )
    exclude = list(dict.fromkeys(exclude))

    whole = bool(glob.get("match_whole_words")) or bool(src.get("match_whole_words"))

    return {
        "include_keywords": include,
        "exclude_keywords": exclude,
        "match_whole_words": whole,
    }


def should_keep_item(text: str, settings_json: dict | None) -> bool:
    """
    Сохранять ли новость по ключевым словам.

    - exclude_keywords / global (через merge): если любое совпало — отбросить
    - include_keywords: если список не пуст — нужно хотя бы одно совпадение
    - match_whole_words: целые слова (границы \\w), иначе подстрока
    """
    cfg = settings_json or {}
    include = parse_keyword_list(cfg.get("include_keywords"))
    exclude = parse_keyword_list(cfg.get("exclude_keywords"))
    whole = bool(cfg.get("match_whole_words"))

    haystack = _normalize(text or "")

    if exclude and _keyword_hits(haystack, exclude, whole_words=whole):
        return False

    if include:
        return bool(_keyword_hits(haystack, include, whole_words=whole))

    return True


def explain_filter(text: str, settings_json: dict | None) -> dict[str, Any]:
    """Для превью в UI: почему новость прошла или отсеялась."""
    cfg = settings_json or {}
    include = parse_keyword_list(cfg.get("include_keywords"))
    exclude = parse_keyword_list(cfg.get("exclude_keywords"))
    whole = bool(cfg.get("match_whole_words"))
    haystack = _normalize(text or "")

    hit_exclude = _keyword_hits(haystack, exclude, whole_words=whole)
    if hit_exclude:
        return {"keep": False, "reason": "exclude", "matched_keywords": hit_exclude}

    if include:
        hit_include = _keyword_hits(haystack, include, whole_words=whole)
        if not hit_include:
            return {"keep": False, "reason": "include_missing", "matched_keywords": []}
        return {"keep": True, "reason": "include", "matched_keywords": hit_include}

    return {"keep": True, "reason": "no_filter", "matched_keywords": []}
