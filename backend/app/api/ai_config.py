"""API for AI processing configuration (prompts per data type)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.services.ai_client import AIValidationError, call_provider
from app.services.ai_config import get_ai_config, save_ai_config
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai-config", tags=["ai-config"])


class AIConfigOut(BaseModel):
    provider: str
    api_key_set: bool
    model: str
    ai_request_delay_seconds: float
    ai_max_retries: int
    ai_retry_base_seconds: float
    prompt_news: str
    prompt_competitors: str
    prompt_competitor_tg: str
    prompt_developers: str
    prompt_indicators: str
    prompt_regions: str
    prompt_clusters: str


class AIConfigUpdateIn(BaseModel):
    provider: str | None = Field(default=None, max_length=50)
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    ai_request_delay_seconds: float | None = Field(default=None, ge=0, le=120)
    ai_max_retries: int | None = Field(default=None, ge=0, le=10)
    ai_retry_base_seconds: float | None = Field(default=None, ge=1, le=300)
    prompt_news: str | None = Field(default=None, max_length=10000)
    prompt_competitors: str | None = Field(default=None, max_length=10000)
    prompt_competitor_tg: str | None = Field(default=None, max_length=10000)
    prompt_developers: str | None = Field(default=None, max_length=10000)
    prompt_indicators: str | None = Field(default=None, max_length=10000)
    prompt_regions: str | None = Field(default=None, max_length=10000)
    prompt_clusters: str | None = Field(default=None, max_length=10000)
    clear_api_key: bool | None = None


def _to_out(cfg: dict[str, Any]) -> AIConfigOut:
    from app.services.ai_config import mask_api_key

    defaults = {
        "provider": "openrouter",
        "api_key": "",
        "model": "openai/gpt-4o-mini",
        "ai_request_delay_seconds": 2.0,
        "ai_max_retries": 3,
        "ai_retry_base_seconds": 5.0,
        "prompt_news": "",
        "prompt_competitors": "",
        "prompt_competitor_tg": "",
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
    clear_api_key = bool(kwargs.pop("clear_api_key", False))
    if "provider" in kwargs and kwargs["provider"] is not None:
        provider = str(kwargs["provider"]).strip().lower()
        if provider not in {"openrouter", "routerai"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="provider must be one of: openrouter, routerai",
            )
        kwargs["provider"] = provider
    if clear_api_key:
        kwargs["api_key"] = None
    elif "api_key" in kwargs:
        key_val = (kwargs.get("api_key") or "").strip()
        if key_val:
            kwargs["api_key"] = key_val
        else:
            del kwargs["api_key"]
    save_ai_config(db, **kwargs)
    cfg = get_ai_config(db)
    return _to_out(cfg)


class AITestOut(BaseModel):
    ok: bool
    provider: str
    model: str
    latency_ms: int
    message: str
    response_preview: str | None = None


@router.post("/test", response_model=AITestOut)
def test_connection(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> AITestOut:
    """Проверка API-ключа и модели (один короткий запрос к провайдеру)."""
    import time

    cfg = get_ai_config(db)
    provider = (cfg.get("provider") or "openrouter").strip()
    api_key = (cfg.get("api_key") or "").strip()
    model = (cfg.get("model") or "openai/gpt-4o-mini").strip()
    if not api_key:
        return AITestOut(
            ok=False,
            provider=provider,
            model=model,
            latency_ms=0,
            message="API ключ не задан. Сохраните ключ и повторите тест.",
        )

    t0 = time.perf_counter()
    try:
        reply = call_provider(
            provider=provider,
            api_key=api_key,
            model=model,
            prompt="Ты проверяешь подключение системы NewsInt. Ответь одним словом: OK",
            data="Тестовый запрос без бизнес-данных.",
            max_retries=1,
            retry_base_seconds=3.0,
            log_label="ai-config-test",
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        preview = (reply or "").strip()[:500]
        return AITestOut(
            ok=True,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            message="Подключение успешно",
            response_preview=preview or None,
        )
    except AIValidationError as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return AITestOut(
            ok=False,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            message=str(e),
        )
