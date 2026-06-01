"""API: Telegram-канал для карточек в разделе «Индикаторы»."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import IndicatorTelegramPost
from app.parsers.indicator_telegram_ingestor import ingest_indicator_telegram
from app.services.indicator_telegram_config import (
    _default_config,
    get_indicator_telegram_config,
    save_indicator_telegram_config,
)
from app.services.indicator_telegram_report import default_report_groups

router = APIRouter(prefix="/indicators/telegram", tags=["indicators"])


class IndicatorTelegramReportGroupOut(BaseModel):
    title: str
    keywords: list[str]


class IndicatorTelegramConfigOut(BaseModel):
    enabled: bool
    channel_username: str
    include_keywords: list[str]
    exclude_keywords: list[str]
    match_whole_words: bool
    backfill_limit: int
    include_in_report: bool
    ai_in_report: bool
    report_groups: list[IndicatorTelegramReportGroupOut]
    last_message_id: int | None
    last_fetch_at: str | None
    last_error: str | None


class IndicatorTelegramReportGroupIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(default_factory=list)


class IndicatorTelegramConfigUpdateIn(BaseModel):
    enabled: bool | None = None
    channel_username: str | None = Field(default=None, max_length=128)
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    match_whole_words: bool | None = None
    backfill_limit: int | None = Field(default=None, ge=10, le=500)
    include_in_report: bool | None = None
    ai_in_report: bool | None = None
    report_groups: list[IndicatorTelegramReportGroupIn] | None = None


class IndicatorTelegramPostOut(BaseModel):
    id: str
    channel_username: str
    message_id: int
    post_url: str
    text: str | None
    image_path: str | None
    published_at: str | None
    matched_keywords: list[str]
    created_at: str


def _config_out(cfg: dict) -> IndicatorTelegramConfigOut:
    merged = {**_default_config(), **cfg}
    groups_raw = merged.get("report_groups") or default_report_groups()
    groups = [
        IndicatorTelegramReportGroupOut(
            title=str(g.get("title") or "").strip() or "Показатель",
            keywords=[str(k).strip() for k in (g.get("keywords") or []) if str(k).strip()],
        )
        for g in groups_raw
        if str(g.get("title") or "").strip()
    ]
    if not groups:
        groups = [
            IndicatorTelegramReportGroupOut(title=g["title"], keywords=list(g["keywords"]))
            for g in default_report_groups()
        ]
    return IndicatorTelegramConfigOut(
        enabled=bool(merged["enabled"]),
        channel_username=str(merged.get("channel_username") or ""),
        include_keywords=list(merged.get("include_keywords") or []),
        exclude_keywords=list(merged.get("exclude_keywords") or []),
        match_whole_words=bool(merged.get("match_whole_words")),
        backfill_limit=int(merged.get("backfill_limit") or 100),
        include_in_report=bool(merged.get("include_in_report", True)),
        ai_in_report=bool(merged.get("ai_in_report", False)),
        report_groups=groups,
        last_message_id=merged.get("last_message_id"),
        last_fetch_at=merged.get("last_fetch_at"),
        last_error=merged.get("last_error"),
    )


@router.get("/config", response_model=IndicatorTelegramConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> IndicatorTelegramConfigOut:
    return _config_out(get_indicator_telegram_config(db))


@router.put("/config", response_model=IndicatorTelegramConfigOut)
def update_config(
    payload: IndicatorTelegramConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> IndicatorTelegramConfigOut:
    data = payload.model_dump(exclude_unset=True)
    if "channel_username" in data and data["channel_username"] is not None:
        data["channel_username"] = data["channel_username"].strip().lstrip("@")
    if "report_groups" in data and data["report_groups"] is not None:
        data["report_groups"] = [g.model_dump() for g in data["report_groups"]]
    save_indicator_telegram_config(db, **data)
    return _config_out(get_indicator_telegram_config(db))


@router.get("/posts")
def list_posts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> dict:
    q = db.query(IndicatorTelegramPost)
    total = q.count()
    rows = (
        q.order_by(IndicatorTelegramPost.published_at.desc().nullslast(), IndicatorTelegramPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        IndicatorTelegramPostOut(
            id=str(r.id),
            channel_username=r.channel_username,
            message_id=int(r.message_id),
            post_url=r.post_url,
            text=r.text,
            image_path=r.image_path,
            published_at=r.published_at.isoformat() if r.published_at else None,
            matched_keywords=list(r.matched_keywords or []),
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return {"items": items, "total": total}


@router.post("/collect-now")
def collect_now(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    try:
        return ingest_indicator_telegram(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка сбора TG для индикаторов: {e!s}",
        )


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    row = db.get(IndicatorTelegramPost, post_id)
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(row)
    db.commit()
