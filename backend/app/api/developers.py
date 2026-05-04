from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Developer
from app.schemas.developers import DeveloperCreate, DeveloperListOut, DeveloperOut, DeveloperUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/developers", tags=["developers"])


@router.get("", response_model=DeveloperListOut)
def list_developers(
    q: str | None = Query(default=None, description="Search by name"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> DeveloperListOut:
    base = db.query(Developer)
    if q:
        base = base.filter(Developer.name.ilike(f"%{q}%"))

    total = base.with_entities(func.count(Developer.id)).scalar() or 0
    items = base.order_by(Developer.name.asc()).offset(offset).limit(limit).all()
    return DeveloperListOut(items=[DeveloperOut.model_validate(d, from_attributes=True) for d in items], total=total)


@router.get("/{developer_id}", response_model=DeveloperOut)
def get_developer(
    developer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> DeveloperOut:
    d = db.get(Developer, developer_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")
    return DeveloperOut.model_validate(d, from_attributes=True)


@router.post("", response_model=DeveloperOut, status_code=status.HTTP_201_CREATED)
def create_developer(
    payload: DeveloperCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> DeveloperOut:
    exists = db.query(Developer).filter(Developer.name == payload.name).one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Developer name already exists")

    d = Developer(
        name=payload.name,
        aliases=payload.aliases,
        tags=payload.tags,
        region_ids=payload.region_ids,
        is_active=payload.is_active,
    )
    db.add(d)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="developers.create",
        entity_type="developer",
        entity_id=None,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": payload.name},
    )
    db.commit()
    db.refresh(d)
    return DeveloperOut.model_validate(d, from_attributes=True)


@router.patch("/{developer_id}", response_model=DeveloperOut)
def update_developer(
    developer_id: uuid.UUID,
    payload: DeveloperUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> DeveloperOut:
    d = db.get(Developer, developer_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")

    if payload.name is not None and payload.name != d.name:
        exists = db.query(Developer).filter(Developer.name == payload.name).one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Developer name already exists")
        d.name = payload.name
    if payload.aliases is not None:
        d.aliases = payload.aliases
    if payload.tags is not None:
        d.tags = payload.tags
    if payload.region_ids is not None:
        d.region_ids = payload.region_ids
    if payload.is_active is not None:
        d.is_active = payload.is_active

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="developers.update",
        entity_type="developer",
        entity_id=str(d.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta=payload.model_dump(exclude_none=True, mode="json"),
    )
    db.commit()
    db.refresh(d)
    return DeveloperOut.model_validate(d, from_attributes=True)


@router.delete("/{developer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_developer(
    developer_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    d = db.get(Developer, developer_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="developers.delete",
        entity_type="developer",
        entity_id=str(d.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": d.name},
    )
    db.delete(d)
    db.commit()
    return None
