from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_request_meta
from app.core.security import (
    create_access_token,
    create_refresh_token,
    stable_token_hash,
    verify_password,
)
from app.db import get_db
from app.models.auth import AuditLog, RefreshToken, User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_access_token(subject=str(user.id), role=user.role.value)
    refresh = create_refresh_token(subject=str(user.id))

    now = datetime.now(timezone.utc)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=stable_token_hash(refresh),
        expires_at=now + timedelta(days=14),
    )
    db.add(rt)

    meta = get_request_meta(request)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            ip=meta["ip"],
            user_agent=meta["user_agent"],
            meta={},
        )
    )
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    # We only store refresh token hash. If it's revoked/expired/missing -> reject.
    token_hash = stable_token_hash(payload.refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()
    if not rt or rt.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = datetime.now(timezone.utc)
    if rt.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    access = create_access_token(subject=str(user.id), role=user.role.value)
    refresh2 = create_refresh_token(subject=str(user.id))

    # Rotate: revoke old, insert new
    rt.revoked_at = now
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=stable_token_hash(refresh2),
            expires_at=now + timedelta(days=14),
        )
    )
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh2)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )

