from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Competitor, Developer, NewsItem
from app.schemas.news import NewsItemListOut, NewsItemOut
from app.services.news_entity_sync import sync_news_entity_links_from_sources

router = APIRouter(prefix="/news", tags=["news"])


class NewsSyncEntityLinksOut(BaseModel):
    checked: int
    updated_developer: int
    updated_competitor: int
    sources_touched: int
    overwrite: bool
    source_id: str | None = None


def _competitor_names_by_ids(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.query(Competitor.id, Competitor.name).filter(Competitor.id.in_(ids)).all()
    return {r.id: r.name for r in rows}


def _developer_names_by_ids(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.query(Developer.id, Developer.name).filter(Developer.id.in_(ids)).all()
    return {r.id: r.name for r in rows}


@router.get("", response_model=NewsItemListOut)
def list_news(
    q: str | None = Query(default=None, description="Search in title, snippet"),
    source_id: uuid.UUID | None = Query(default=None, description="Filter by source"),
    competitor_id: uuid.UUID | None = Query(default=None, description="Filter: news where this competitor is mentioned"),
    developer_id: uuid.UUID | None = Query(default=None, description="Filter: news linked to this developer"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> NewsItemListOut:
    base = db.query(NewsItem).options(joinedload(NewsItem.source))
    if source_id:
        base = base.filter(NewsItem.source_id == source_id)
    if competitor_id:
        base = base.filter(
            or_(
                NewsItem.competitor_id == competitor_id,
                NewsItem.competitor_mentions.contains([competitor_id]),
            )
        )
    if developer_id:
        base = base.filter(
            or_(
                NewsItem.developer_id == developer_id,
                NewsItem.developer_mentions.contains([developer_id]),
            )
        )
    if q:
        q_pattern = f"%{q}%"
        base = base.filter(
            or_(
                NewsItem.title.ilike(q_pattern),
                NewsItem.snippet.ilike(q_pattern),
                NewsItem.content_text.ilike(q_pattern),
            )
        )
    total = base.with_entities(func.count(NewsItem.id)).scalar() or 0
    items = (
        base.order_by(NewsItem.published_at.desc().nullslast(), NewsItem.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    competitor_ids = set()
    developer_ids = set()
    for n in items:
        competitor_ids.update(n.competitor_mentions or [])
        developer_ids.update(n.developer_mentions or [])
    names_map = _competitor_names_by_ids(db, list(competitor_ids))
    dev_names_map = _developer_names_by_ids(db, list(developer_ids))

    out_items = []
    for n in items:
        d = NewsItemOut.model_validate(n, from_attributes=True)
        if n.source:
            d.source_name = (
                n.source.name
                or n.source.base_url
                or n.source.feed_url
                or (f"@{n.source.tg_channel_username}" if n.source.tg_channel_username else None)
            )
        d.competitor_mentions_names = [names_map[cid] for cid in (n.competitor_mentions or []) if names_map.get(cid)]
        d.developer_mentions_names = [dev_names_map[did] for did in (n.developer_mentions or []) if dev_names_map.get(did)]
        out_items.append(d)
    return NewsItemListOut(items=out_items, total=total)


@router.post("/sync-entity-links", response_model=NewsSyncEntityLinksOut)
def sync_entity_links_all(
    source_id: uuid.UUID | None = Query(default=None, description="Только этот источник; без id — все"),
    overwrite: bool = Query(default=False, description="Перезаписать существующие привязки на новостях"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> NewsSyncEntityLinksOut:
    """
    Проставить competitor_id / developer_id на новостях из карточки источника.
    Нужно после поздней привязки канала к застройщику или конкуренту.
    """
    result = sync_news_entity_links_from_sources(db, source_id=source_id, overwrite=overwrite)
    return NewsSyncEntityLinksOut(**result)


@router.delete("/{news_id}", status_code=204)
def delete_news(
    news_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    n = db.get(NewsItem, news_id)
    if not n:
        raise HTTPException(status_code=404, detail="News item not found")
    db.delete(n)
    db.commit()
