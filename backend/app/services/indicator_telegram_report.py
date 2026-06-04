"""Telegram-посты для раздела «Индикаторы» в HTML/PDF отчёте."""

from __future__ import annotations

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
        {"title": "Ввод жилья", "keywords": ["ввод жилья"]},
        {"title": "Ввод МКД", "keywords": ["многоквартирных", "мкд"]},
    ]


def _norm_kw(s: str) -> str:
    return (s or "").strip().lower()


def _post_matches_group(post: IndicatorTelegramPost, group_keywords: list[str]) -> bool:
    keys = [_norm_kw(k) for k in group_keywords if _norm_kw(k)]
    if not keys:
        return False
    matched = [_norm_kw(m) for m in (post.matched_keywords or [])]
    for k in keys:
        if k in matched:
            return True
        for m in matched:
            if k in m or m in k:
                return True
    text = (post.text or "").lower()
    return any(k in text for k in keys)


def post_to_dict(post: IndicatorTelegramPost) -> dict[str, Any]:
    pub = post.published_at
    return {
        "id": str(post.id),
        "text": post.text,
        "image_path": post.image_path,
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
            img = ""
            if p.get("image_path"):
                src = escape(str(p["image_path"]))
                img = f'<img src="{src}" alt="" class="tg-post-img" loading="lazy" />'
            text_html = ""
            if p.get("text"):
                text_html = f'<p class="tg-post-text">{escape(str(p["text"]))}</p>'
            link = ""
            if p.get("post_url"):
                link = (
                    f'<a class="tg-post-link" href="{escape(str(p["post_url"]))}" '
                    f'target="_blank" rel="noopener noreferrer">Telegram</a>'
                )
            meta = ""
            if p.get("published_at"):
                meta = f'<div class="muted tg-post-meta">{escape(str(p["published_at"])[:10])}</div>'
            cards.append(f'<article class="tg-post-card">{img}{meta}{text_html}{link}</article>')

        grid = f'<div class="tg-post-grid">{"".join(cards)}</div>' if cards else ""
        parts.append(f'<div class="tg-indicator-block"><h3>{title}</h3>{inner}{grid}</div>')

    return f'<div class="tg-indicators">{"".join(parts)}</div>'
