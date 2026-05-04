"""Load VK config from DB with env fallback."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.config import VkConfig


def get_vk_config(db: Session) -> dict[str, str]:
    row = db.query(VkConfig).filter(VkConfig.id == 1).first()
    if row and row.access_token:
        return {"access_token": row.access_token}
    return {"access_token": settings.vk_access_token or ""}


def save_vk_config(db: Session, *, access_token: str | None = None) -> VkConfig:
    row = db.query(VkConfig).filter(VkConfig.id == 1).first()
    if not row:
        row = VkConfig(id=1)
        db.add(row)
    if access_token is not None:
        row.access_token = (access_token or "").strip() or None
    db.commit()
    db.refresh(row)
    return row
