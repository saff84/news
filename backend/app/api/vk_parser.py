"""API for VK parser configuration and connectivity checks."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.settings import settings
from app.db import get_db
from app.models.auth import Role, User
from app.models.config import VkConfig
from app.services.vk_config import get_vk_config, save_vk_config

router = APIRouter(prefix="/vk-parser", tags=["vk-parser"])


class VkParserStatusOut(BaseModel):
    token_configured: bool
    token_source: str = "env"  # db|env
    api_base: str
    api_version: str
    token_valid: bool | None
    verify_error: str | None = None


class VkConfigUpdateIn(BaseModel):
    access_token: str | None = Field(default=None, description="VK API token")


class VkConfigOut(BaseModel):
    access_token_set: bool
    token_source: str


class VkTestFetchIn(BaseModel):
    group_id: str = Field(description="VK group id/public/club/domain/url")
    limit: int = Field(default=5, ge=1, le=50)


class VkTestFetchOut(BaseModel):
    fetched: int
    sample: list[dict[str, Any]]


class VkTestTokenIn(BaseModel):
    token: str


class VkTestTokenOut(BaseModel):
    ok: bool
    error: str | None = None


def _token_source(db: Session) -> str:
    row = db.query(VkConfig).filter(VkConfig.id == 1).first()
    if row and row.access_token:
        return "db"
    return "env"


def _normalize_group(group_id_raw: str) -> tuple[str | None, str | None]:
    gid = (group_id_raw or "").strip()
    if gid.startswith("https://vk.com/"):
        gid = gid.replace("https://vk.com/", "").strip("/")
    if gid.startswith("vk.com/"):
        gid = gid.replace("vk.com/", "").strip("/")
    if gid.startswith("public"):
        n = gid.replace("public", "").strip()
        if n.isdigit():
            return str(-abs(int(n))), None
    if gid.startswith("club"):
        n = gid.replace("club", "").strip()
        if n.isdigit():
            return str(-abs(int(n))), None
    if gid.lstrip("-").isdigit():
        return str(-abs(int(gid))), None
    return None, gid


def _wall_get(*, token: str, group_id: str, count: int = 5) -> list[dict[str, Any]]:
    owner_id, domain = _normalize_group(group_id)
    params: dict[str, Any] = {
        "access_token": token,
        "v": settings.vk_api_version,
        "count": max(1, min(count, 100)),
        "filter": "owner",
    }
    if owner_id:
        params["owner_id"] = owner_id
    else:
        params["domain"] = domain

    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
        resp = client.get(f"{settings.vk_api_base.rstrip('/')}/wall.get", params=params)
        resp.raise_for_status()
        body = resp.json()
    if "error" in body:
        err = body.get("error") or {}
        msg = err.get("error_msg") or str(err)
        raise RuntimeError(f"VK API error: {msg}")
    data = body.get("response") or {}
    items = data.get("items") or []
    return [x for x in items if isinstance(x, dict)]


@router.get("/config", response_model=VkConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> VkConfigOut:
    cfg = get_vk_config(db)
    return VkConfigOut(access_token_set=bool(cfg.get("access_token")), token_source=_token_source(db))


@router.put("/config", response_model=VkConfigOut)
def update_config(
    payload: VkConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> VkConfigOut:
    kwargs = payload.model_dump(exclude_unset=True)
    save_vk_config(db, **kwargs)
    cfg = get_vk_config(db)
    return VkConfigOut(access_token_set=bool(cfg.get("access_token")), token_source="db")


@router.get("/status", response_model=VkParserStatusOut)
def status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> VkParserStatusOut:
    cfg = get_vk_config(db)
    token = (cfg.get("access_token") or "").strip()
    token_valid: bool | None = None
    verify_error: str | None = None
    if token:
        try:
            _wall_get(token=token, group_id="vk", count=1)
            token_valid = True
        except Exception as e:
            token_valid = False
            verify_error = str(e)
    return VkParserStatusOut(
        token_configured=bool(token),
        token_source=_token_source(db),
        api_base=settings.vk_api_base,
        api_version=settings.vk_api_version,
        token_valid=token_valid,
        verify_error=verify_error,
    )


@router.post("/test-token", response_model=VkTestTokenOut)
def test_token(
    payload: VkTestTokenIn,
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> VkTestTokenOut:
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    try:
        _wall_get(token=token, group_id="vk", count=1)
        return VkTestTokenOut(ok=True)
    except Exception as e:
        return VkTestTokenOut(ok=False, error=str(e))


@router.post("/test-fetch", response_model=VkTestFetchOut)
def test_fetch(
    payload: VkTestFetchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> VkTestFetchOut:
    cfg = get_vk_config(db)
    token = (cfg.get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="VK access token is not configured")
    try:
        items = _wall_get(token=token, group_id=payload.group_id, count=payload.limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"VK API request failed: {e}")

    sample: list[dict[str, Any]] = []
    for post in items[:5]:
        post_id = post.get("id")
        owner_id = post.get("owner_id")
        text = str(post.get("text") or "")
        sample.append(
            {
                "id": f"{owner_id}_{post_id}",
                "date": post.get("date"),
                "text": text[:180],
                "url": f"https://vk.com/wall{owner_id}_{post_id}" if post_id and owner_id else None,
            }
        )
    return VkTestFetchOut(fetched=len(items), sample=sample)
