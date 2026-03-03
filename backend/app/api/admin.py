from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import get_request_meta
from app.core.settings import settings
from app.core.security import hash_password
from app.db import get_db
from app.models.auth import Role, User
from app.schemas.auth import UserOut
from app.services.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])

class BootstrapAdminIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, max_length=200)
    # Optional hint for proper Unicode handling (no functional impact),
    # keep here for later encoding fixes in storage/DB.


@router.post("/bootstrap", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminIn, request: Request, db: Session = Depends(get_db)) -> UserOut:
    """
    DEV-ONLY: Create the first Admin user if there are no users yet.
    This endpoint is automatically disabled in production via APP_ENV.
    """
    if settings.app_env.lower() in ("prod", "production"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    users_exist = db.query(User.id).limit(1).first() is not None
    if users_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Users already exist")

    email = payload.email.strip().lower()
    password = payload.password
    full_name = payload.full_name

    user = User(email=email, full_name=full_name, role=Role.ADMIN, is_active=True, password_hash=hash_password(password))
    db.add(user)

    meta = get_request_meta(request)
    write_audit_log(
        db,
        actor_user_id=None,
        action="admin.bootstrap",
        entity_type="user",
        entity_id=None,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        meta={"email": email},
    )
    db.commit()
    db.refresh(user)

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )

