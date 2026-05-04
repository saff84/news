"""Load MAX config from DB with env fallback."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.config import MaxConfig


def get_max_config(db: Session) -> dict[str, str]:
    """
    Get MAX config: DB first, then env fallback.
    Returns dict with bot_token.
    """
    row = db.query(MaxConfig).filter(MaxConfig.id == 1).first()
    if row and row.bot_token:
        return {"bot_token": row.bot_token}
    return {"bot_token": settings.max_bot_token or ""}


def save_max_config(
    db: Session,
    *,
    bot_token: str | None = None,
) -> MaxConfig:
    """Save or update MAX config. None means field is not updated."""
    row = db.query(MaxConfig).filter(MaxConfig.id == 1).first()
    if not row:
        row = MaxConfig(id=1)
        db.add(row)
    if bot_token is not None:
        row.bot_token = (bot_token or "").strip() or None
    db.commit()
    db.refresh(row)
    return row
