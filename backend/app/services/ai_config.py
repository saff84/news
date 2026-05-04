"""Load/save AI config (prompts per data type)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.config import AIConfig


def get_ai_config(db: Session) -> dict[str, Any]:
    """Get AI config. Returns default dict if not set. Merges with defaults for new keys."""
    defaults = _default_config()
    row = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if row and row.settings_json:
        return {**defaults, **dict(row.settings_json)}
    return defaults


def save_ai_config(db: Session, **kwargs: Any) -> AIConfig:
    """Update AI config. Merges with existing."""
    row = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not row:
        row = AIConfig(id=1, settings_json={})
        db.add(row)
    current = dict(row.settings_json or {})
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v
        elif k in current:
            del current[k]
    row.settings_json = current
    db.commit()
    db.refresh(row)
    return row


def _default_config() -> dict[str, Any]:
    return {
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


def mask_api_key(api_key: str | None) -> bool:
    """Return True if api_key is set (non-empty)."""
    return bool(api_key and api_key.strip())
