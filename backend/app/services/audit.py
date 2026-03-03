from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.auth import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    ip: str | None,
    user_agent: str | None,
    meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=ip,
            user_agent=user_agent,
            meta=meta or {},
        )
    )

