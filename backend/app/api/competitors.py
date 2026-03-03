from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Competitor
from app.schemas.competitors import CompetitorCreate, CompetitorListOut, CompetitorOut, CompetitorUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("", response_model=CompetitorListOut)
def list_competitors(
    q: str | None = Query(default=None, description="Search by name"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> CompetitorListOut:
    base = db.query(Competitor)
    if q:
        base = base.filter(Competitor.name.ilike(f"%{q}%"))

    total = base.with_entities(func.count(Competitor.id)).scalar() or 0
    items = base.order_by(Competitor.name.asc()).offset(offset).limit(limit).all()
    return CompetitorListOut(items=[CompetitorOut.model_validate(c, from_attributes=True) for c in items], total=total)


@router.get("/{competitor_id}", response_model=CompetitorOut)
def get_competitor(
    competitor_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> CompetitorOut:
    c = db.get(Competitor, competitor_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    return CompetitorOut.model_validate(c, from_attributes=True)


@router.post("", response_model=CompetitorOut, status_code=status.HTTP_201_CREATED)
def create_competitor(
    payload: CompetitorCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> CompetitorOut:
    exists = db.query(Competitor).filter(Competitor.name == payload.name).one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Competitor name already exists")

    c = Competitor(
        name=payload.name,
        aliases=payload.aliases,
        tags=payload.tags,
        region_ids=payload.region_ids,
        is_active=payload.is_active,
    )
    db.add(c)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="competitors.create",
        entity_type="competitor",
        entity_id=None,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": payload.name},
    )
    db.commit()
    db.refresh(c)
    return CompetitorOut.model_validate(c, from_attributes=True)


@router.patch("/{competitor_id}", response_model=CompetitorOut)
def update_competitor(
    competitor_id: uuid.UUID,
    payload: CompetitorUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> CompetitorOut:
    c = db.get(Competitor, competitor_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    if payload.name and payload.name != c.name:
        exists = db.query(Competitor).filter(Competitor.name == payload.name).one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Competitor name already exists")
        c.name = payload.name
    if payload.aliases is not None:
        c.aliases = payload.aliases
    if payload.tags is not None:
        c.tags = payload.tags
    if payload.region_ids is not None:
        c.region_ids = payload.region_ids
    if payload.is_active is not None:
        c.is_active = payload.is_active

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="competitors.update",
        entity_type="competitor",
        entity_id=str(c.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta=payload.model_dump(exclude_none=True, mode="json"),
    )
    db.commit()
    db.refresh(c)
    return CompetitorOut.model_validate(c, from_attributes=True)


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competitor(
    competitor_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    c = db.get(Competitor, competitor_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="competitors.delete",
        entity_type="competitor",
        entity_id=str(c.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": c.name},
    )
    db.delete(c)
    db.commit()
    return None

