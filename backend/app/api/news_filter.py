"""API for global news keyword filters (minus words)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import NewsItem, Source
from app.parsers.keyword_filter import explain_filter, parse_keyword_list
from app.services.audit import write_audit_log
from app.services.news_filter_config import (
    effective_filter_settings,
    get_news_filter_config,
    news_item_search_text,
    save_news_filter_config,
    should_keep_news_item,
)

router = APIRouter(prefix="/news-filter", tags=["news-filter"])


class NewsFilterOut(BaseModel):
    global_exclude_keywords: list[str] = Field(default_factory=list)
    global_include_keywords: list[str] = Field(default_factory=list)
    match_whole_words: bool = False


class NewsFilterUpdateIn(BaseModel):
    global_exclude_keywords: list[str] | None = None
    global_include_keywords: list[str] | None = None
    match_whole_words: bool | None = None


class NewsFilterPreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    source_id: uuid.UUID | None = None


class NewsFilterPreviewOut(BaseModel):
    keep: bool
    reason: str
    matched_keywords: list[str] = Field(default_factory=list)


class NewsFilterCleanupIn(BaseModel):
    source_id: uuid.UUID | None = None
    dry_run: bool = False


class NewsFilterCleanupOut(BaseModel):
    deleted: int
    total_checked: int
    dry_run: bool


def _to_out(cfg: dict[str, Any]) -> NewsFilterOut:
    defaults = {
        "global_exclude_keywords": [],
        "global_include_keywords": [],
        "match_whole_words": False,
    }
    merged = {**defaults, **cfg}
    return NewsFilterOut(
        global_exclude_keywords=parse_keyword_list(merged.get("global_exclude_keywords")),
        global_include_keywords=parse_keyword_list(merged.get("global_include_keywords")),
        match_whole_words=bool(merged.get("match_whole_words")),
    )


@router.get("", response_model=NewsFilterOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> NewsFilterOut:
    return _to_out(get_news_filter_config(db))


@router.put("", response_model=NewsFilterOut)
def update_config(
    payload: NewsFilterUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> NewsFilterOut:
    data = payload.model_dump(exclude_unset=True)
    if "global_exclude_keywords" in data and data["global_exclude_keywords"] is not None:
        data["global_exclude_keywords"] = parse_keyword_list(data["global_exclude_keywords"])
    if "global_include_keywords" in data and data["global_include_keywords"] is not None:
        data["global_include_keywords"] = parse_keyword_list(data["global_include_keywords"])
    save_news_filter_config(db, **data)
    return _to_out(get_news_filter_config(db))


@router.post("/preview", response_model=NewsFilterPreviewOut)
def preview_filter(
    payload: NewsFilterPreviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> NewsFilterPreviewOut:
    source_settings: dict | None = None
    if payload.source_id:
        src = db.get(Source, payload.source_id)
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        source_settings = src.settings_json
    effective = effective_filter_settings(db, source_settings)
    result = explain_filter(payload.text, effective)
    return NewsFilterPreviewOut(**result)


@router.post("/cleanup", response_model=NewsFilterCleanupOut)
def cleanup_news(
    payload: NewsFilterCleanupIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> NewsFilterCleanupOut:
    """
    Удалить из БД новости, не прошедшие глобальный + локальный фильтр.
    source_id — только один источник; без id — все источники.
    """
    q = db.query(NewsItem)
    if payload.source_id:
        src = db.get(Source, payload.source_id)
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        q = q.filter(NewsItem.source_id == payload.source_id)

    items = q.all()
    sources_cache: dict[uuid.UUID, dict | None] = {}
    deleted = 0

    for n in items:
        sid = n.source_id
        if sid not in sources_cache:
            src = db.get(Source, sid) if sid else None
            sources_cache[sid] = src.settings_json if src else {}
        if not should_keep_news_item(
            db,
            news_item_search_text(
                url=n.url,
                title=n.title,
                snippet=n.snippet,
                content_text=n.content_text,
            ),
            sources_cache[sid],
        ):
            deleted += 1
            if not payload.dry_run:
                db.delete(n)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="news_filter.cleanup",
        entity_type="news_filter",
        entity_id="1",
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={
            "deleted": deleted,
            "total_checked": len(items),
            "dry_run": payload.dry_run,
            "source_id": str(payload.source_id) if payload.source_id else None,
        },
    )
    if not payload.dry_run:
        db.commit()
    return NewsFilterCleanupOut(deleted=deleted, total_checked=len(items), dry_run=payload.dry_run)
