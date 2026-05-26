"""Chronological sort for Russian/ISO period labels in indicators and charts."""

from __future__ import annotations

import re

_RU_MONTHS = {
    "января": 1, "янв": 1, "февраля": 2, "фев": 2, "марта": 3, "мар": 3,
    "апреля": 4, "апр": 4, "мая": 5, "май": 5, "июня": 6, "июн": 6,
    "июля": 7, "июл": 7, "августа": 8, "авг": 8, "сентября": 9, "сен": 9,
    "октября": 10, "окт": 10, "ноября": 11, "ноя": 11, "декабря": 12, "дек": 12,
}


def period_sort_key(period: str) -> tuple[int, int, int]:
    """Extract (year, month, day) from period string for chronological sorting (oldest first)."""
    s = period.split(" - ")[0].strip() if " - " in period else period.strip()
    s_lower = s.lower().replace("г.", "").strip()
    m_year = re.match(r"^(\d{4})$", s_lower)
    if m_year:
        return (int(m_year.group(1)), 1, 1)
    m_abbr = re.search(r"(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\.?\s*(\d{4})", s_lower)
    if m_abbr:
        mo = _RU_MONTHS.get(m_abbr.group(1).lower(), 1)
        return (int(m_abbr.group(2)), mo, 1)
    for month_name, month_num in _RU_MONTHS.items():
        if month_name in s_lower:
            m = re.search(r"(\d{1,2})\s+.*?(\d{4})", s_lower)
            if m:
                day, year = int(m.group(1)), int(m.group(2))
                return (year, month_num, min(day, 31))
    m = re.search(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s_lower)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        d = int(m.group(3)) if m.group(3) else 1
        return (y, mo, min(d, 31))
    return (9999, 99, 99)
