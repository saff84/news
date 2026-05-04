from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DiagnosticsOverviewOut(BaseModel):
    now: datetime
    db_ok: bool
    redis_ok: bool
    rq_default_queue_count: int
    alembic_version: str | None
    alert_critical_count: int = 0
    alert_warning_count: int = 0


class EnqueueRunOut(BaseModel):
    job_id: str


class JobStatusOut(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    exc_info: str | None = None

