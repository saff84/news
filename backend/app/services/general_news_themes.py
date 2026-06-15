"""Тематические подразделы в блоке «Общие новости» отчёта."""

from __future__ import annotations

from typing import Any

from app.parsers.keyword_filter import parse_keyword_list


def default_general_news_themes() -> list[dict[str, Any]]:
    return [
        {
            "title": "Ипотека и ставка",
            "keywords": ["ипотек", "ипотеч", "ключев", "ставк", "цб", "центробанк", "рефинанс"],
        },
        {
            "title": "Ввод жилья и строительство",
            "keywords": ["ввод", "введен", "росстат", "жиль", "строитель", "млн м", "млн кв"],
        },
        {
            "title": "Законодательство и регулирование",
            "keywords": ["закон", "госдум", "минстрой", "регулир", "норматив", "постановлен"],
        },
        {
            "title": "Рынок и цены",
            "keywords": ["цен", "стоимост", "продаж", "спрос", "предложен", "рынок", "новостро", "девелоп"],
        },
        {
            "title": "Госпрограммы и субсидии",
            "keywords": ["семейн", "льгот", "субсид", "господдерж", "dom.rf", "дом.рф", "госпрограмм"],
        },
        {"title": "Прочее", "keywords": []},
    ]


def normalize_general_news_themes(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, list) and raw:
        themes: list[dict[str, Any]] = []
        for g in raw:
            if not isinstance(g, dict):
                continue
            title = str(g.get("title") or "").strip()
            if not title:
                continue
            themes.append({"title": title, "keywords": parse_keyword_list(g.get("keywords"))})
        if themes:
            if not any(not t["keywords"] for t in themes):
                themes.append({"title": "Прочее", "keywords": []})
            return themes
    return default_general_news_themes()


def _text_haystack(item: Any) -> str:
    return f"{getattr(item, 'title', '') or ''} {getattr(item, 'snippet', '') or ''}".lower()


def _matches_keywords(haystack: str, keywords: list[str]) -> bool:
    for kw in keywords:
        if kw and kw in haystack:
            return True
    return False


def group_general_news_by_themes(
    items: list,
    themes: list[dict[str, Any]],
) -> list[tuple[str, list]]:
    """Разнести общие новости по темам (первая подходящая; без ключей — «Прочее»)."""
    if not items:
        return []
    normalized = normalize_general_news_themes(themes)
    buckets: dict[str, list] = {t["title"]: [] for t in normalized}
    catch_all = next((t["title"] for t in reversed(normalized) if not t["keywords"]), "Прочее")

    for n in items:
        haystack = _text_haystack(n)
        placed = False
        for t in normalized:
            kws = t.get("keywords") or []
            if not kws:
                continue
            if _matches_keywords(haystack, kws):
                buckets[t["title"]].append(n)
                placed = True
                break
        if not placed:
            buckets.setdefault(catch_all, []).append(n)

    return [(t["title"], buckets[t["title"]]) for t in normalized if buckets.get(t["title"])]
