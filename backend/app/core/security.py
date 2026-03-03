from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, subject: str, role: str, ttl_min: int | None = None) -> str:
    ttl = ttl_min if ttl_min is not None else settings.access_token_ttl_min
    exp = _now() + timedelta(minutes=ttl)
    payload: dict[str, Any] = {"sub": subject, "role": role, "type": "access", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(*, subject: str, ttl_days: int | None = None) -> str:
    ttl = ttl_days if ttl_days is not None else settings.refresh_token_ttl_days
    exp = _now() + timedelta(days=ttl)
    payload: dict[str, Any] = {"sub": subject, "type": "refresh", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def stable_token_hash(token: str) -> str:
    # Store only a stable hash of refresh tokens.
    digest = hmac.new(settings.secret_key.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

