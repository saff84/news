from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta, require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import ParsingTemplate
from app.schemas.parsing_templates import (
    ParsingTemplateCreate,
    ParsingTemplateListOut,
    ParsingTemplateOut,
    ParsingTemplateUpdate,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/parsing-templates", tags=["parsing_templates"])


@router.get("", response_model=ParsingTemplateListOut)
def list_parsing_templates(
    q: str | None = Query(default=None, description="Search by name"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> ParsingTemplateListOut:
    base = db.query(ParsingTemplate)
    if q:
        base = base.filter(ParsingTemplate.name.ilike(f"%{q}%"))
    total = base.with_entities(func.count(ParsingTemplate.id)).scalar() or 0
    items = base.order_by(ParsingTemplate.name.asc(), ParsingTemplate.version.desc()).offset(offset).limit(limit).all()
    return ParsingTemplateListOut(items=[ParsingTemplateOut.model_validate(t, from_attributes=True) for t in items], total=total)


@router.get("/{template_id}", response_model=ParsingTemplateOut)
def get_parsing_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> ParsingTemplateOut:
    t = db.get(ParsingTemplate, template_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return ParsingTemplateOut.model_validate(t, from_attributes=True)


@router.post("", response_model=ParsingTemplateOut, status_code=status.HTTP_201_CREATED)
def create_parsing_template(
    payload: ParsingTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ParsingTemplateOut:
    exists = (
        db.query(ParsingTemplate)
        .filter(ParsingTemplate.name == payload.name, ParsingTemplate.version == payload.version)
        .one_or_none()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name+version already exists")

    t = ParsingTemplate(
        name=payload.name,
        version=payload.version,
        template_json=payload.template_json,
        is_active=payload.is_active,
    )
    db.add(t)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="parsing_templates.create",
        entity_type="parsing_template",
        entity_id=None,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": payload.name, "version": payload.version},
    )
    db.commit()
    db.refresh(t)
    return ParsingTemplateOut.model_validate(t, from_attributes=True)


@router.patch("/{template_id}", response_model=ParsingTemplateOut)
def update_parsing_template(
    template_id: uuid.UUID,
    payload: ParsingTemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ParsingTemplateOut:
    t = db.get(ParsingTemplate, template_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if payload.name is not None:
        t.name = payload.name
    if payload.version is not None:
        t.version = payload.version
    if payload.template_json is not None:
        t.template_json = payload.template_json
    if payload.is_active is not None:
        t.is_active = payload.is_active

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="parsing_templates.update",
        entity_type="parsing_template",
        entity_id=str(t.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta=payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(t)
    return ParsingTemplateOut.model_validate(t, from_attributes=True)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parsing_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    t = db.get(ParsingTemplate, template_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="parsing_templates.delete",
        entity_type="parsing_template",
        entity_id=str(t.id),
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"name": t.name, "version": t.version},
    )
    db.delete(t)
    db.commit()
    return None

