"""API for MAX parser configuration and connectivity checks."""

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
from app.models.config import MaxConfig
from app.services.max_config import get_max_config, save_max_config

router = APIRouter(prefix="/max-parser", tags=["max-parser"])


class MaxParserStatusOut(BaseModel):
    token_configured: bool
    token_source: str = "env"  # "db" or "env"
    api_base: str
    token_valid: bool | None
    bot_info: dict[str, Any] | None = None
    verify_error: str | None = None


class MaxConfigUpdateIn(BaseModel):
    bot_token: str | None = Field(default=None, description="MAX bot token")


class MaxConfigOut(BaseModel):
    bot_token_set: bool
    token_source: str


class MaxTestFetchIn(BaseModel):
    channel_id: str = Field(description="MAX chat/channel ID")
    limit: int = Field(default=5, ge=1, le=50)


class MaxTestFetchOut(BaseModel):
    fetched: int
    sample: list[dict[str, Any]]


class MaxTestBotIn(BaseModel):
    token: str


class MaxTestBotOut(BaseModel):
    ok: bool
    bot_info: dict[str, Any] | None = None
    error: str | None = None


def _token_source(db: Session) -> str:
    row = db.query(MaxConfig).filter(MaxConfig.id == 1).first()
    if row and row.bot_token:
        return "db"
    return "env"


def _headers(token: str) -> dict[str, str]:
    # MAX docs require Authorization header with the token value.
    return {"Authorization": token}


def _extract_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("messages", "items", "data", "results"):
            arr = payload.get(key)
            if isinstance(arr, list):
                return [x for x in arr if isinstance(x, dict)]
    return []


@router.get("/config", response_model=MaxConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> MaxConfigOut:
    cfg = get_max_config(db)
    return MaxConfigOut(bot_token_set=bool(cfg.get("bot_token")), token_source=_token_source(db))


@router.put("/config", response_model=MaxConfigOut)
def update_config(
    payload: MaxConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> MaxConfigOut:
    kwargs = payload.model_dump(exclude_unset=True)
    save_max_config(db, **kwargs)
    cfg = get_max_config(db)
    return MaxConfigOut(bot_token_set=bool(cfg.get("bot_token")), token_source="db")


@router.get("/status", response_model=MaxParserStatusOut)
def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> MaxParserStatusOut:
    cfg = get_max_config(db)
    token = (cfg.get("bot_token") or "").strip()
    api_base = (settings.max_api_base or "https://platform-api.max.ru").rstrip("/")
    token_valid: bool | None = None
    verify_error: str | None = None
    bot_info: dict[str, Any] | None = None
    if token:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                # According to MAX docs, GET /bots returns bot information.
                resp = client.get(f"{api_base}/bots", headers=_headers(token))
                resp.raise_for_status()
                token_valid = True
                try:
                    bot_info = resp.json() if isinstance(resp.json(), dict) else {"raw": resp.json()}
                except Exception:
                    bot_info = {"raw_text": resp.text[:500]}
        except Exception as e:
            token_valid = False
            verify_error = str(e)
    return MaxParserStatusOut(
        token_configured=bool(token),
        token_source=_token_source(db),
        api_base=api_base,
        token_valid=token_valid,
        bot_info=bot_info,
        verify_error=verify_error,
    )


@router.post("/test-fetch", response_model=MaxTestFetchOut)
def test_fetch(
    payload: MaxTestFetchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> MaxTestFetchOut:
    cfg = get_max_config(db)
    token = (cfg.get("bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="MAX bot token is not configured")

    api_base = (settings.max_api_base or "https://platform-api.max.ru").rstrip("/")
    params = {"chat_id": payload.channel_id, "limit": payload.limit}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(f"{api_base}/messages", headers=_headers(token), params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"MAX API request failed: {e}")

    messages = _extract_messages(data)
    sample: list[dict[str, Any]] = []
    for m in messages[:5]:
        sample.append(
            {
                "id": m.get("id") or m.get("message_id") or m.get("messageId"),
                "text": (m.get("text") or (m.get("body") or {}).get("text") or "")[:180],
                "date": m.get("created_at") or m.get("createdAt") or m.get("date") or m.get("timestamp"),
            }
        )
    return MaxTestFetchOut(fetched=len(messages), sample=sample)


@router.post("/test-bot", response_model=MaxTestBotOut)
def test_bot(
    payload: MaxTestBotIn,
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> MaxTestBotOut:
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    api_base = (settings.max_api_base or "https://platform-api.max.ru").rstrip("/")
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(f"{api_base}/bots", headers=_headers(token))
            resp.raise_for_status()
            body = resp.json()
    except Exception as e:
        return MaxTestBotOut(ok=False, error=str(e))
    return MaxTestBotOut(ok=True, bot_info=body if isinstance(body, dict) else {"raw": body})
