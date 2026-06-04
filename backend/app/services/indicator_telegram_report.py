"""Telegram-посты для раздела «Индикаторы» в HTML/PDF отчёте."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.domain import IndicatorTelegramPost
from app.services.indicator_telegram_config import get_indicator_telegram_config


def default_report_groups() -> list[dict[str, Any]]:
    return [
        {"title": "Ввод жилья", "keywords": ["ввод жилья", "введено"]},
        {"title": "Ввод МКД", "keywords": ["многоквартир", "мкд"]},
    ]


_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF]+",
    flags=re.UNICODE,
)
_FOOTER_LINE_RE = re.compile(
    r"подпишитесь|подписывайтесь|подписаться",
    re.IGNORECASE,
)


def clean_telegram_post_text(text: str | None) -> str:
    """Убрать эмодзи, подпись канала и лишние пустые строки."""
    if not text:
        return ""
    t = _EMOJI_RE.sub("", text)
    lines: list[str] = []
    for raw in t.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _FOOTER_LINE_RE.search(line) and re.search(r"ерз|max", line, re.IGNORECASE):
            continue
        lines.append(line)
    return "\n\n".join(lines)


def _post_image_paths(post: IndicatorTelegramPost) -> list[str]:
    paths = [p for p in (post.image_paths or []) if p]
    if not paths and post.image_path:
        paths = [post.image_path]
    return paths


def _post_haystack(post: IndicatorTelegramPost) -> tuple[str, list[str]]:
    matched = [_norm_kw(m) for m in (post.matched_keywords or [])]
    haystack = (post.text or "").lower()
    if matched:
        haystack = f"{haystack} {' '.join(matched)}"
    return haystack, matched


def _post_report_kind(post: IndicatorTelegramPost) -> str | None:
    """mkd | housing — для разнесения по блокам отчёта."""
    haystack, matched = _post_haystack(post)
    if _token_matches_haystack("многоквартир", haystack, matched) or _token_matches_haystack("мкд", haystack, matched):
        return "mkd"
    if "многоквартир" in haystack:
        return "mkd"
    if _token_matches_haystack("введено", haystack, matched):
        return "housing"
    if _token_matches_haystack("жиль", haystack, matched):
        return "housing"
    for k in ("ввод жилья",):
        parts = k.split()
        if all(_token_matches_haystack(p, haystack, matched) for p in parts):
            return "housing"
    return None


def _section_report_kind(title: str) -> str | None:
    t = title.lower()
    if "мкд" in t or "многоквартир" in t:
        return "mkd"
    if "жиль" in t:
        return "housing"
    return None


def _norm_kw(s: str) -> str:
    return (s or "").strip().lower()


def _stem_overlap(a: str, b: str, *, min_prefix: int = 6) -> bool:
    """Совпадение с учётом русских окончаний (многоквартирных / многоквартирного)."""
    a, b = _norm_kw(a), _norm_kw(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    n = min(len(a), len(b), 14)
    for cut in range(n, min_prefix - 1, -1):
        if a[:cut] == b[:cut]:
            return True
    return False


def _token_matches_haystack(token: str, haystack: str, matched: list[str]) -> bool:
    token = _norm_kw(token)
    if not token:
        return False
    if token in haystack:
        return True
    for m in matched:
        if _stem_overlap(token, m):
            return True
    if len(token) <= 4:
        return bool(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", haystack, flags=re.UNICODE))
    root_len = max(5, len(token) - 3)
    if token[:root_len] in haystack:
        return True
    if token.startswith("ввод") and "введ" in haystack:
        return True
    return False


def _post_matches_group(post: IndicatorTelegramPost, group_keywords: list[str]) -> bool:
    keys = [_norm_kw(k) for k in group_keywords if _norm_kw(k)]
    if not keys:
        return False
    matched = [_norm_kw(m) for m in (post.matched_keywords or [])]
    haystack = (post.text or "").lower()
    if matched:
        haystack = f"{haystack} {' '.join(matched)}"

    for k in keys:
        if " " in k:
            parts = k.split()
            if all(_token_matches_haystack(p, haystack, matched) for p in parts):
                return True
        elif _token_matches_haystack(k, haystack, matched):
            return True
    return False


def post_to_dict(post: IndicatorTelegramPost) -> dict[str, Any]:
    pub = post.published_at
    image_paths = _post_image_paths(post)
    display_text = clean_telegram_post_text(post.text)
    return {
        "id": str(post.id),
        "text": display_text or None,
        "image_path": image_paths[0] if image_paths else post.image_path,
        "image_paths": image_paths,
        "post_url": post.post_url,
        "published_at": pub.isoformat() if pub else None,
        "matched_keywords": list(post.matched_keywords or []),
    }


def group_posts_by_report_sections(
    posts: list[IndicatorTelegramPost],
    report_groups: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Разнести посты по группам отчёта (первое совпадение — одна группа)."""
    groups = report_groups or default_report_groups()
    sections: list[dict[str, Any]] = [
        {"title": str(g.get("title") or "").strip() or "Показатель", "keywords": list(g.get("keywords") or []), "posts": []}
        for g in groups
        if str(g.get("title") or "").strip()
    ]
    if not sections:
        sections = [{"title": "Telegram", "keywords": [], "posts": []}]

    assigned: set[str] = set()
    for post in posts:
        pid = str(post.id)
        if pid in assigned:
            continue
        kind = _post_report_kind(post)
        placed = False
        if kind:
            for sec in sections:
                if _section_report_kind(str(sec["title"])) == kind:
                    sec["posts"].append(post_to_dict(post))
                    assigned.add(pid)
                    placed = True
                    break
        if placed:
            continue
        for sec in sections:
            if _post_matches_group(post, sec["keywords"]):
                sec["posts"].append(post_to_dict(post))
                assigned.add(pid)
                break

    return [
        {
            "title": sec["title"],
            "keywords": sec["keywords"],
            "posts": sec["posts"],
            "ai_text": None,
            "ai_json": None,
        }
        for sec in sections
        if sec["posts"]
    ]


def fetch_indicator_telegram_posts_for_period(
    db: Session,
    *,
    date_from: date,
    date_to: date,
) -> list[IndicatorTelegramPost]:
    dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
    return (
        db.query(IndicatorTelegramPost)
        .filter(
            or_(
                and_(
                    IndicatorTelegramPost.published_at.isnot(None),
                    IndicatorTelegramPost.published_at >= dt_from,
                    IndicatorTelegramPost.published_at <= dt_to,
                ),
                and_(
                    IndicatorTelegramPost.published_at.is_(None),
                    IndicatorTelegramPost.created_at >= dt_from,
                    IndicatorTelegramPost.created_at <= dt_to,
                ),
            )
        )
        .order_by(IndicatorTelegramPost.published_at.asc().nullslast(), IndicatorTelegramPost.created_at.asc())
        .all()
    )


def build_indicator_telegram_sections(
    db: Session,
    posts: list[IndicatorTelegramPost],
) -> list[dict[str, Any]]:
    cfg = get_indicator_telegram_config(db)
    if not cfg.get("include_in_report", True):
        return []
    return group_posts_by_report_sections(posts, cfg.get("report_groups"))


def serialize_section_for_ai(section: dict[str, Any]) -> str:
    lines = [f"Показатель: {section.get('title', '')}"]
    for i, p in enumerate(section.get("posts") or [], 1):
        lines.append(f"\n--- Пост {i} ---")
        if p.get("published_at"):
            lines.append(f"Дата: {p['published_at']}")
        if p.get("post_url"):
            lines.append(f"Ссылка: {p['post_url']}")
        if p.get("text"):
            lines.append(str(p["text"]))
    return "\n".join(lines).strip() or "(нет текста)"


def merge_ai_into_sections(
    sections: list[dict[str, Any]],
    ai_by_title: dict[str, tuple[str | None, dict[str, Any] | None]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sec in sections:
        title = str(sec.get("title") or "")
        text, payload = ai_by_title.get(title, (None, None))
        out.append({**sec, "ai_text": text, "ai_json": payload})
    return out


def _text_to_html(text: str) -> str:
    paragraphs = [escape(p.strip()) for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [escape(line.strip()) for line in text.splitlines() if line.strip()]
    if not paragraphs:
        return ""
    inner = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f'<div class="tg-post-text">{inner}</div>'


def image_path_to_filesystem(image_path: str | None) -> Path | None:
    if not image_path:
        return None
    name = image_path.rstrip("/").split("/")[-1]
    if not name:
        return None
    p = Path(settings.storage_dir) / "indicator_tg" / name
    return p if p.is_file() else None


def indicator_telegram_sections_to_html(sections: list[dict[str, Any]] | None) -> str:
    if not sections:
        return ""
    parts: list[str] = []
    for sec in sections:
        title = escape(str(sec.get("title") or ""))
        inner = ""
        ai_json = sec.get("ai_json")
        if isinstance(ai_json, dict) and ai_json:
            from app.services.report_section_render import section_dict_to_html_fragment

            frag = section_dict_to_html_fragment(ai_json).strip()
            if frag:
                inner = f'<div class="summary rich structured">{frag}</div>'
        if not inner and sec.get("ai_text"):
            from app.services.report_markup import markdown_links_to_html

            inner = f'<div class="summary rich">{markdown_links_to_html(str(sec["ai_text"]))}</div>'

        cards: list[str] = []
        for p in sec.get("posts") or []:
            paths = list(p.get("image_paths") or [])
            if not paths and p.get("image_path"):
                paths = [str(p["image_path"])]
            imgs = "".join(
                f'<img src="{escape(src)}" alt="" class="tg-post-img" loading="lazy" />' for src in paths
            )
            images_html = f'<div class="tg-post-images">{imgs}</div>' if imgs else ""
            text_html = _text_to_html(str(p["text"])) if p.get("text") else ""
            link = ""
            if p.get("post_url"):
                link = (
                    f'<a class="tg-post-link" href="{escape(str(p["post_url"]))}" '
                    f'target="_blank" rel="noopener noreferrer">Открыть в Telegram</a>'
                )
            meta = ""
            if p.get("published_at"):
                meta = f'<div class="muted tg-post-meta">{escape(str(p["published_at"])[:10])}</div>'
            cards.append(f'<article class="tg-post-card">{images_html}{meta}{text_html}{link}</article>')

        grid = f'<div class="tg-post-stack">{"".join(cards)}</div>' if cards else ""
        parts.append(f'<div class="tg-indicator-block"><h3>{title}</h3>{inner}{grid}</div>')

    return f'<div class="tg-indicators">{"".join(parts)}</div>'
