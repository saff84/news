"""Синхронизация competitor_id / developer_id у новостей с карточки источника."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import NewsItem, Source


def sync_news_entity_links_from_sources(
    db: Session,
    *,
    source_id: uuid.UUID | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Проставить на новостях primary competitor_id / developer_id с источника.

    overwrite=False — только если поле на новости пустое (безопасно после поздней привязки).
    overwrite=True — перезаписать у всех новостей источника значениями с карточки источника
    (в т.ч. очистить, если на источнике связь снята).
    """
    q = db.query(Source)
    if source_id is not None:
        q = q.filter(Source.id == source_id)
    sources = q.all()

    updated_developer = 0
    updated_competitor = 0
    checked = 0
    sources_touched = 0

    for src in sources:
        if not src.developer_id and not src.competitor_id:
            continue
        items = db.query(NewsItem).filter(NewsItem.source_id == src.id).all()
        if not items:
            continue
        sources_touched += 1
        for n in items:
            checked += 1
            if src.developer_id is not None:
                if overwrite or n.developer_id is None:
                    if n.developer_id != src.developer_id:
                        n.developer_id = src.developer_id
                        updated_developer += 1
            elif overwrite and n.developer_id is not None:
                n.developer_id = None
                updated_developer += 1

            if src.competitor_id is not None:
                if overwrite or n.competitor_id is None:
                    if n.competitor_id != src.competitor_id:
                        n.competitor_id = src.competitor_id
                        updated_competitor += 1
            elif overwrite and n.competitor_id is not None:
                n.competitor_id = None
                updated_competitor += 1

    db.commit()
    return {
        "checked": checked,
        "updated_developer": updated_developer,
        "updated_competitor": updated_competitor,
        "sources_touched": sources_touched,
        "overwrite": overwrite,
        "source_id": str(source_id) if source_id else None,
    }
