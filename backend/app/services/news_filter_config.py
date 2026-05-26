"""Global news keyword filters (minus/plus words for all sources)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.config import NewsFilterConfig
from app.parsers.keyword_filter import merge_filter_settings, should_keep_item


def get_news_filter_config(db: Session) -> dict[str, Any]:
    row = db.query(NewsFilterConfig).filter(NewsFilterConfig.id == 1).first()
    if row and row.settings_json:
        return dict(row.settings_json)
    return _default_config()


def save_news_filter_config(db: Session, **kwargs: Any) -> NewsFilterConfig:
    row = db.query(NewsFilterConfig).filter(NewsFilterConfig.id == 1).first()
    if not row:
        row = NewsFilterConfig(id=1, settings_json={})
        db.add(row)
    current = dict(row.settings_json or {})
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v
        elif k in current:
            del current[k]
    row.settings_json = current
    db.commit()
    db.refresh(row)
    return row


def _default_config() -> dict[str, Any]:
    return {
        "global_exclude_keywords": [],
        "global_include_keywords": [],
        "match_whole_words": False,
    }


def effective_filter_settings(db: Session, source_settings: dict | None) -> dict[str, Any]:
    """Объединить глобальные и локальные ключи источника."""
    return merge_filter_settings(source_settings, get_news_filter_config(db))


def should_keep_news_item(db: Session, text: str, source_settings: dict | None) -> bool:
    cfg = effective_filter_settings(db, source_settings)
    return should_keep_item(text, cfg)


def news_item_search_text(
    *,
    url: str | None = None,
    title: str | None = None,
    snippet: str | None = None,
    content_text: str | None = None,
) -> str:
    return " ".join([str(url or ""), str(title or ""), str(snippet or ""), str(content_text or "")])
