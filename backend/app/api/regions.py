from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Region
from app.schemas.regions import RegionCreate, RegionListOut, RegionOut, RegionUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=RegionListOut)
def list_regions(
    q: str | None = Query(default=None, description="Search by name"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> RegionListOut:
    base = db.query(Region)
    if q:
        base = base.filter(Region.name.ilike(f"%{q}%"))

    total = base.with_entities(func.count(Region.id)).scalar() or 0
    items = base.order_by(Region.name.asc()).offset(offset).limit(limit).all()
    return RegionListOut(items=[RegionOut.model_validate(r, from_attributes=True) for r in items], total=total)


@router.get("/{region_id}", response_model=RegionOut)
def get_region(
    region_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> RegionOut:
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    return RegionOut.model_validate(region, from_attributes=True)


@router.post("", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
def create_region(
    payload: RegionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> RegionOut:
    exists = db.query(Region).filter(Region.name == payload.name).one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Region name already exists")

    region = Region(
        name=payload.name,
        federal_subjects=payload.federal_subjects,
        keywords=payload.keywords,
        geographic_aliases=payload.geographic_aliases,
        is_active=payload.is_active,
    )
    db.add(region)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="regions.create",
        entity_type="region",
        entity_id=None,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": payload.name},
    )
    db.commit()
    db.refresh(region)

    write_audit_log(
        db,
        actor_user_id=user.id,
        action="regions.create.commit",
        entity_type="region",
        entity_id=str(region.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={},
    )
    db.commit()
    return RegionOut.model_validate(region, from_attributes=True)


@router.patch("/{region_id}", response_model=RegionOut)
def update_region(
    region_id: uuid.UUID,
    payload: RegionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> RegionOut:
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")

    if payload.name and payload.name != region.name:
        exists = db.query(Region).filter(Region.name == payload.name).one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Region name already exists")
        region.name = payload.name

    if payload.federal_subjects is not None:
        region.federal_subjects = payload.federal_subjects
    if payload.keywords is not None:
        region.keywords = payload.keywords
    if payload.geographic_aliases is not None:
        region.geographic_aliases = payload.geographic_aliases
    if payload.is_active is not None:
        region.is_active = payload.is_active

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="regions.update",
        entity_type="region",
        entity_id=str(region.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta=payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(region)
    return RegionOut.model_validate(region, from_attributes=True)


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_region(
    region_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="regions.delete",
        entity_type="region",
        entity_id=str(region.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": region.name},
    )
    db.delete(region)
    db.commit()
    return None

