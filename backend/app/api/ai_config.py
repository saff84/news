"""API for AI processing configuration (prompts per data type)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.services.ai_config import get_ai_config, save_ai_config
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai-config", tags=["ai-config"])


class AIConfigOut(BaseModel):
    provider: str
    api_key_set: bool
    model: str
    prompt_news: str
    prompt_competitors: str
    prompt_developers: str
    prompt_indicators: str
    prompt_regions: str
    prompt_clusters: str


class AIConfigUpdateIn(BaseModel):
    provider: str | None = Field(default=None, max_length=50)
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    prompt_news: str | None = Field(default=None, max_length=10000)
    prompt_competitors: str | None = Field(default=None, max_length=10000)
    prompt_developers: str | None = Field(default=None, max_length=10000)
    prompt_indicators: str | None = Field(default=None, max_length=10000)
    prompt_regions: str | None = Field(default=None, max_length=10000)
    prompt_clusters: str | None = Field(default=None, max_length=10000)


def _to_out(cfg: dict[str, Any]) -> AIConfigOut:
    from app.services.ai_config import mask_api_key

    defaults = {
        "provider": "openrouter",
        "api_key": "",
        "model": "openai/gpt-4o-mini",
        "prompt_news": "",
        "prompt_competitors": "",
        "prompt_developers": "",
        "prompt_indicators": "",
        "prompt_regions": "",
        "prompt_clusters": "",
    }
    merged = {**defaults, **cfg}
    out = {k: merged.get(k, v) for k, v in defaults.items() if k != "api_key"}
    out["api_key_set"] = mask_api_key(merged.get("api_key"))
    return AIConfigOut(**out)


@router.get("", response_model=AIConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> AIConfigOut:
    """Get AI config (prompts per data type)."""
    cfg = get_ai_config(db)
    return _to_out(cfg)


@router.put("", response_model=AIConfigOut)
def update_config(
    payload: AIConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> AIConfigOut:
    """Update AI config (Admin only)."""
    kwargs = payload.model_dump(exclude_unset=True)
    if "provider" in kwargs and kwargs["provider"] is not None:
        provider = str(kwargs["provider"]).strip().lower()
        if provider not in {"openrouter", "routerai"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="provider must be one of: openrouter, routerai",
            )
        kwargs["provider"] = provider
    # Empty string = clear api_key
    if "api_key" in kwargs:
        kwargs["api_key"] = kwargs["api_key"] or None
    save_ai_config(db, **kwargs)
    cfg = get_ai_config(db)
    return _to_out(cfg)
