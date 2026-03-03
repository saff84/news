from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import NewsItem
from app.schemas.news import NewsItemListOut, NewsItemOut

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsItemListOut)
def list_news(
    q: str | None = Query(default=None, description="Search in title, snippet"),
    source_id: uuid.UUID | None = Query(default=None, description="Filter by source"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> NewsItemListOut:
    base = db.query(NewsItem).options(joinedload(NewsItem.source))
    if source_id:
        base = base.filter(NewsItem.source_id == source_id)
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
        out_items.append(d)
    return NewsItemListOut(items=out_items, total=total)


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
