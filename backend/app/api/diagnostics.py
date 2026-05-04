from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from rq.job import Job
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Source
from app.api.monitoring import build_monitoring_alerts, summarize_monitoring_alerts
from app.schemas.diagnostics import DiagnosticsOverviewOut, EnqueueRunOut, JobStatusOut
from app.workers.jobs import fetch_source, rebuild_news_clusters_job
from app.workers.queue import get_queue, get_redis

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/overview", response_model=DiagnosticsOverviewOut)
def overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> DiagnosticsOverviewOut:
    now = dt.datetime.now(dt.timezone.utc)

    db_ok = True
    alembic_version: str | None = None
    try:
        db.execute(text("SELECT 1"))
        # Optional: if alembic_version doesn't exist yet, return null.
        try:
            row = db.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            alembic_version = row[0] if row else None
        except Exception:
            alembic_version = None
    except Exception:
        db_ok = False

    redis_ok = True
    rq_count = 0
    try:
        r = get_redis()
        redis_ok = bool(r.ping())
        rq_count = get_queue("default").count
    except Exception:
        redis_ok = False

    alert_critical_count = 0
    alert_warning_count = 0
    try:
        sources = db.query(Source).filter(Source.enabled.is_(True)).all()
        alerts = build_monitoring_alerts(sources, now=now)
        critical, warning, _ = summarize_monitoring_alerts(alerts)
        alert_critical_count = critical
        alert_warning_count = warning
    except Exception:
        # diagnostics endpoint should stay resilient even if alert calculations fail
        alert_critical_count = 0
        alert_warning_count = 0

    return DiagnosticsOverviewOut(
        now=now,
        db_ok=db_ok,
        redis_ok=redis_ok,
        rq_default_queue_count=int(rq_count),
        alembic_version=alembic_version,
        alert_critical_count=alert_critical_count,
        alert_warning_count=alert_warning_count,
    )


@router.post("/rebuild-news-clusters", response_model=EnqueueRunOut)
def rebuild_news_clusters_enqueue(
    user: User = Depends(require_role(Role.ADMIN)),
) -> EnqueueRunOut:
    """Поставить в очередь пересборку кластеров похожих новостей (simhash) за последние ~90 дней."""
    q = get_queue("default")
    job = q.enqueue(rebuild_news_clusters_job, job_timeout=900)
    return EnqueueRunOut(job_id=job.id)


@router.post("/sources/{source_id}/run-now", response_model=EnqueueRunOut)
def run_source_now(
    source_id: uuid.UUID,
    user: User = Depends(require_role(Role.ADMIN)),
) -> EnqueueRunOut:
    q = get_queue("default")
    job = q.enqueue(fetch_source, str(source_id), job_timeout=600)
    return EnqueueRunOut(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def job_status(
    job_id: str,
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> JobStatusOut:
    try:
        job = Job.fetch(job_id, connection=get_redis())
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    res = job.result if isinstance(job.result, dict) else None
    return JobStatusOut(job_id=job.id, status=job.get_status(), result=res, exc_info=job.exc_info)

