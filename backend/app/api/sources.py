from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import NewsItem, RssState, Source, SourceType, TgChannelState
from app.parsers.keyword_filter import should_keep_item
from app.schemas.sources import SourceCreate, SourceListOut, SourceOut, SourceUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/sources", tags=["sources"])


def _validate_source_payload(source_type: SourceType, base_url: str | None, feed_url: str | None, tg_username: str | None, parsing_template_id):
    if source_type == SourceType.RSS_ATOM:
        if not feed_url:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="feed_url required for RSS_ATOM")
    if source_type in (SourceType.HTML_LIST_DETAIL, SourceType.HTML_DETAIL_ONLY, SourceType.SITEMAP):
        if not base_url:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="base_url required for HTML sources")
        if source_type != SourceType.SITEMAP and not parsing_template_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="parsing_template_id required for HTML_* sources"
            )
    if source_type == SourceType.TELEGRAM_CHANNEL:
        if not tg_username:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tg_channel_username required")


@router.get("", response_model=SourceListOut)
def list_sources(
    source_type: str | None = Query(default=None),
    competitor_id: uuid.UUID | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SourceListOut:
    q = db.query(Source)
    if source_type:
        q = q.filter(Source.source_type == SourceType(source_type))
    if competitor_id:
        q = q.filter(Source.competitor_id == competitor_id)
    if enabled is not None:
        q = q.filter(Source.enabled.is_(enabled))
    total = q.with_entities(func.count(Source.id)).scalar() or 0
    items = q.order_by(Source.priority.desc(), Source.created_at.desc()).offset(offset).limit(limit).all()
    return SourceListOut(items=[SourceOut.model_validate(s, from_attributes=True) for s in items], total=total)


@router.get("/{source_id}", response_model=SourceOut)
def get_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SourceOut:
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceOut.model_validate(s, from_attributes=True)


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> SourceOut:
    st = SourceType(payload.source_type)
    tg_username = payload.tg_channel_username.lstrip("@") if payload.tg_channel_username else None
    _validate_source_payload(st, payload.base_url, payload.feed_url, tg_username, payload.parsing_template_id)

    s = Source(
        source_type=st,
        name=payload.name,
        base_url=payload.base_url,
        feed_url=payload.feed_url,
        tg_channel_username=tg_username,
        region_tags=payload.region_tags,
        competitor_id=payload.competitor_id,
        enabled=payload.enabled,
        fetch_frequency_min=payload.fetch_frequency_min,
        priority=payload.priority,
        delay_ms=payload.delay_ms,
        max_requests_per_minute=payload.max_requests_per_minute,
        retries=payload.retries,
        respect_robots_txt=payload.respect_robots_txt,
        parsing_template_id=payload.parsing_template_id,
        settings_json=payload.settings_json,
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # Ensure per-type state row exists
    if st == SourceType.RSS_ATOM:
        db.add(RssState(source_id=s.id))
    if st == SourceType.TELEGRAM_CHANNEL:
        db.add(TgChannelState(source_id=s.id, channel_username=tg_username or ""))
    db.commit()

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="sources.create",
        entity_type="source",
        entity_id=str(s.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"source_type": st.value, "name": payload.name},
    )
    db.commit()

    return SourceOut.model_validate(s, from_attributes=True)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> SourceOut:
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    st = SourceType(payload.source_type) if payload.source_type else s.source_type

    # Apply updates
    if payload.source_type is not None:
        s.source_type = st
    if payload.name is not None:
        s.name = payload.name
    if payload.base_url is not None:
        s.base_url = payload.base_url
    if payload.feed_url is not None:
        s.feed_url = payload.feed_url
    if payload.tg_channel_username is not None:
        s.tg_channel_username = payload.tg_channel_username.lstrip("@") if payload.tg_channel_username else None
    if payload.region_tags is not None:
        s.region_tags = payload.region_tags
    if payload.competitor_id is not None:
        s.competitor_id = payload.competitor_id
    if payload.enabled is not None:
        s.enabled = payload.enabled
    if payload.fetch_frequency_min is not None:
        s.fetch_frequency_min = payload.fetch_frequency_min
    if payload.priority is not None:
        s.priority = payload.priority
    if payload.delay_ms is not None:
        s.delay_ms = payload.delay_ms
    if payload.max_requests_per_minute is not None:
        s.max_requests_per_minute = payload.max_requests_per_minute
    if payload.retries is not None:
        s.retries = payload.retries
    if payload.respect_robots_txt is not None:
        s.respect_robots_txt = payload.respect_robots_txt
    if payload.parsing_template_id is not None:
        s.parsing_template_id = payload.parsing_template_id
    if payload.settings_json is not None:
        s.settings_json = payload.settings_json

    _validate_source_payload(st, s.base_url, s.feed_url, s.tg_channel_username, s.parsing_template_id)

    # Ensure per-type state row exists
    if st == SourceType.RSS_ATOM:
        exists = db.query(RssState).filter(RssState.source_id == s.id).one_or_none()
        if not exists:
            db.add(RssState(source_id=s.id))
    if st == SourceType.TELEGRAM_CHANNEL:
        exists = db.query(TgChannelState).filter(TgChannelState.source_id == s.id).one_or_none()
        if not exists:
            db.add(TgChannelState(source_id=s.id, channel_username=s.tg_channel_username or ""))

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="sources.update",
        entity_type="source",
        entity_id=str(s.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta=payload.model_dump(exclude_none=True, mode="json"),
    )
    db.commit()
    db.refresh(s)
    return SourceOut.model_validate(s, from_attributes=True)


@router.post("/{source_id}/cleanup-news")
def cleanup_news_by_filter(
    source_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    """
    Удаляет из БД новости источника, не прошедшие текущий фильтр по ключевым словам.
    Полезно после добавления include_keywords — старые записи, собранные до фильтра, останутся иначе.
    """
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    items = db.query(NewsItem).filter(NewsItem.source_id == source_id).all()
    deleted = 0
    for n in items:
        search_text = " ".join(
            [
                str(n.url or ""),
                str(n.title or ""),
                str(n.snippet or ""),
                str(n.content_text or ""),
            ]
        )
        if not should_keep_item(search_text, s.settings_json):
            db.delete(n)
            deleted += 1

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="sources.cleanup_news",
        entity_type="source",
        entity_id=str(s.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"deleted": deleted, "total_checked": len(items)},
    )
    db.commit()
    return {"deleted": deleted, "total_checked": len(items)}


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="sources.delete",
        entity_type="source",
        entity_id=str(s.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"source_type": s.source_type.value, "name": s.name},
    )
    db.delete(s)
    db.commit()
    return None

