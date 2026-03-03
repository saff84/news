from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import RssState, Source, TgChannelState
from app.schemas.monitoring import (
    RssStateOut,
    SourceHealthListOut,
    SourceHealthOut,
    TgStateOut,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/sources", response_model=SourceHealthListOut)
def list_sources_health(
    only_enabled: bool = Query(default=True),
    only_failed: bool = Query(default=False, description="consecutive_failures>0 OR last_error not null"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SourceHealthListOut:
    q = db.query(Source)
    if only_enabled:
        q = q.filter(Source.enabled.is_(True))
    if only_failed:
        q = q.filter(or_(Source.consecutive_failures > 0, Source.last_error.isnot(None)))

    total = q.with_entities(func.count(Source.id)).scalar() or 0
    items = q.order_by(Source.consecutive_failures.desc(), Source.priority.desc()).offset(offset).limit(limit).all()
    return SourceHealthListOut(
        items=[SourceHealthOut.model_validate(s, from_attributes=True) for s in items],
        total=total,
    )


@router.get("/rss", response_model=list[RssStateOut])
def list_rss_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[RssStateOut]:
    rows = db.query(RssState).order_by(RssState.last_fetch_at.desc().nullslast()).offset(offset).limit(limit).all()
    return [RssStateOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/telegram", response_model=list[TgStateOut])
def list_tg_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[TgStateOut]:
    rows = (
        db.query(TgChannelState)
        .order_by(TgChannelState.last_fetch_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [TgStateOut.model_validate(r, from_attributes=True) for r in rows]

