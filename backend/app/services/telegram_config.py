"""Load Telegram config from DB with env fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.config import TelegramConfig


def get_telegram_config(db: Session) -> dict[str, Any]:
    """
    Get Telegram config: DB first, then env fallback.
    Returns dict with api_id, api_hash, session_string (all optional).
    """
    row = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if row and (row.api_id or row.api_hash or row.session_string):
        return {
            "api_id": row.api_id,
            "api_hash": row.api_hash or "",
            "session_string": row.session_string or "",
        }
    # Env fallback
    return {
        "api_id": settings.telegram_api_id,
        "api_hash": settings.telegram_api_hash or "",
        "session_string": settings.telegram_session_string or "",
    }


def save_telegram_config(
    db: Session,
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    session_string: str | None = None,
) -> TelegramConfig:
    """Save or update Telegram config. Pass only fields to update; None = don't change."""
    row = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if not row:
        row = TelegramConfig(id=1)
        db.add(row)
    if api_id is not None:
        row.api_id = api_id if api_id != 0 else None
    if api_hash is not None:
        row.api_hash = (api_hash or "").strip() or None
    if session_string is not None:
        row.session_string = (session_string or "").strip() or None
    db.commit()
    db.refresh(row)
    return row
