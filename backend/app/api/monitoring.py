from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import MaxChannelState, RssState, Source, TgChannelState, VkGroupState
from app.schemas.monitoring import (
    EnqueueDueOut,
    MaxStateOut,
    MonitoringAlertsOut,
    MonitoringAlertOut,
    RssStateOut,
    SourceCrawlScheduleListOut,
    SourceCrawlScheduleOut,
    SourceHealthListOut,
    SourceHealthOut,
    TgStateOut,
    VkStateOut,
)
from app.workers.scheduler import enqueue_due_sources

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _source_display_label(s: Source) -> str:
    if s.name:
        return s.name
    if s.base_url:
        return s.base_url
    if s.feed_url:
        return s.feed_url
    if s.tg_channel_username:
        return f"@{s.tg_channel_username}"
    return str(s.id)


def _minutes_since(ts: dt.datetime | None, *, now: dt.datetime) -> int | None:
    if ts is None:
        return None
    return int((now - ts).total_seconds() // 60)


def build_monitoring_alerts(sources: list[Source], *, now: dt.datetime) -> list[MonitoringAlertOut]:
    alerts: list[MonitoringAlertOut] = []

    for s in sources:
        if not s.enabled:
            continue
        label = _source_display_label(s)
        source_id = s.id
        freq_min = max(1, int(s.fetch_frequency_min or 60))
        stale_threshold_min = max(180, freq_min * 2)

        if int(s.consecutive_failures or 0) >= 3:
            alerts.append(
                MonitoringAlertOut(
                    id=f"fail-critical:{source_id}",
                    severity="critical",
                    code="SOURCE_CONSECUTIVE_FAILURES_HIGH",
                    message=f"Источник падает подряд {int(s.consecutive_failures)} раз.",
                    source_id=source_id,
                    source_label=label,
                    meta={"consecutive_failures": int(s.consecutive_failures)},
                )
            )
        elif int(s.consecutive_failures or 0) > 0:
            alerts.append(
                MonitoringAlertOut(
                    id=f"fail-warning:{source_id}",
                    severity="warning",
                    code="SOURCE_CONSECUTIVE_FAILURES",
                    message=f"Есть подряд неуспешные запуски: {int(s.consecutive_failures)}.",
                    source_id=source_id,
                    source_label=label,
                    meta={"consecutive_failures": int(s.consecutive_failures)},
                )
            )

        if s.backoff_until is not None and s.backoff_until > now:
            mins_left = int((s.backoff_until - now).total_seconds() // 60)
            severity = "critical" if mins_left >= 360 else "warning"
            alerts.append(
                MonitoringAlertOut(
                    id=f"backoff:{source_id}",
                    severity=severity,
                    code="SOURCE_BACKOFF_ACTIVE",
                    message=f"Источник на паузе backoff еще ~{mins_left} мин.",
                    source_id=source_id,
                    source_label=label,
                    meta={"backoff_minutes_left": max(0, mins_left)},
                )
            )

        if s.last_success_at is None:
            if s.last_fetch_at is None:
                alerts.append(
                    MonitoringAlertOut(
                        id=f"never-run:{source_id}",
                        severity="warning",
                        code="SOURCE_NEVER_RUN",
                        message="Источник еще ни разу не запускался.",
                        source_id=source_id,
                        source_label=label,
                        meta={},
                    )
                )
            else:
                mins = _minutes_since(s.last_fetch_at, now=now) or 0
                if mins >= stale_threshold_min:
                    alerts.append(
                        MonitoringAlertOut(
                            id=f"never-success:{source_id}",
                            severity="critical",
                            code="SOURCE_NEVER_SUCCEEDED",
                            message=f"Нет успешных запусков, последний запуск был {mins} мин назад.",
                            source_id=source_id,
                            source_label=label,
                            meta={"minutes_since_last_fetch": mins},
                        )
                    )
            continue

        mins_since_success = _minutes_since(s.last_success_at, now=now) or 0
        if mins_since_success >= stale_threshold_min:
            severity = "critical" if mins_since_success >= stale_threshold_min * 2 else "warning"
            alerts.append(
                MonitoringAlertOut(
                    id=f"stale:{source_id}",
                    severity=severity,
                    code="SOURCE_STALE_SUCCESS",
                    message=f"Последний успешный запуск был {mins_since_success} мин назад.",
                    source_id=source_id,
                    source_label=label,
                    meta={"minutes_since_success": mins_since_success, "stale_threshold_min": stale_threshold_min},
                )
            )

    alerts.sort(key=lambda a: (0 if a.severity == "critical" else 1 if a.severity == "warning" else 2, a.code, a.id))
    return alerts


def summarize_monitoring_alerts(alerts: list[MonitoringAlertOut]) -> tuple[int, int, int]:
    critical = sum(1 for a in alerts if a.severity == "critical")
    warning = sum(1 for a in alerts if a.severity == "warning")
    info = sum(1 for a in alerts if a.severity == "info")
    return critical, warning, info


def _crawl_schedule_rows(sources: list[Source], *, now: dt.datetime) -> list[SourceCrawlScheduleOut]:
    rows: list[SourceCrawlScheduleOut] = []
    for s in sources:
        freq_min = int(s.fetch_frequency_min or 60)
        freq_delta = dt.timedelta(minutes=freq_min)

        if s.last_fetch_at is None:
            interval_next = now
        else:
            interval_next = s.last_fetch_at + freq_delta

        backoff_blocks = s.backoff_until is not None and s.backoff_until > now
        interval_ok = interval_next <= now
        is_due = bool(s.enabled) and interval_ok and not backoff_blocks

        next_enqueue: dt.datetime | None
        if not s.enabled:
            next_enqueue = None
        elif is_due:
            next_enqueue = now
        elif backoff_blocks and s.backoff_until is not None:
            next_enqueue = max(s.backoff_until, interval_next)
        else:
            next_enqueue = interval_next

        rows.append(
            SourceCrawlScheduleOut(
                id=s.id,
                source_type=s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type),
                name=s.name,
                display_label=_source_display_label(s),
                enabled=bool(s.enabled),
                fetch_frequency_min=freq_min,
                last_fetch_at=s.last_fetch_at,
                last_success_at=s.last_success_at,
                backoff_until=s.backoff_until,
                is_due=is_due,
                next_expected_enqueue_at=next_enqueue,
            )
        )
    rows.sort(key=lambda r: (not r.is_due, r.next_expected_enqueue_at or now, r.display_label))
    return rows


@router.get("/crawl-schedule", response_model=SourceCrawlScheduleListOut)
def crawl_schedule(
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SourceCrawlScheduleListOut:
    now = dt.datetime.now(dt.timezone.utc)
    q = db.query(Source).order_by(Source.priority.desc(), Source.name.asc().nullslast())
    if not include_disabled:
        q = q.filter(Source.enabled.is_(True))
    sources = q.all()
    items = _crawl_schedule_rows(sources, now=now)
    due_count = sum(1 for r in items if r.is_due)
    return SourceCrawlScheduleListOut(server_now=now, items=items, due_count=due_count)


@router.post("/enqueue-due", response_model=EnqueueDueOut)
def enqueue_due(
    batch_limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> EnqueueDueOut:
    """
    Поставить в очередь RQ задачи fetch_source для источников,
    которые сейчас «просрочены» по тем же правилам, что и планировщик.
    """
    n = enqueue_due_sources(batch_limit=batch_limit)
    return EnqueueDueOut(enqueued=n)


@router.get("/alerts", response_model=MonitoringAlertsOut)
def list_alerts(
    include_disabled: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> MonitoringAlertsOut:
    now = dt.datetime.now(dt.timezone.utc)
    q = db.query(Source)
    if not include_disabled:
        q = q.filter(Source.enabled.is_(True))
    sources = q.order_by(Source.priority.desc(), Source.name.asc().nullslast()).all()
    alerts = build_monitoring_alerts(sources, now=now)[:limit]
    critical, warning, info = summarize_monitoring_alerts(alerts)
    return MonitoringAlertsOut(
        generated_at=now,
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        items=alerts,
    )


@router.get("/sources", response_model=SourceHealthListOut)
def list_sources_health(
    only_enabled: bool = Query(default=True),
    only_failed: bool = Query(default=False, description="consecutive_failures>0 OR last_error not null"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SourceHealthListOut:
    q = db.query(Source)
    if only_enabled:
        q = q.filter(Source.enabled.is_(True))
    if only_failed:
        q = q.filter(or_(Source.consecutive_failures > 0, Source.last_error.isnot(None)))

    total = q.with_entities(func.count(Source.id)).scalar() or 0
    items = q.order_by(Source.consecutive_failures.desc(), Source.priority.desc()).offset(offset).limit(limit).all()
    return SourceHealthListOut(
        items=[SourceHealthOut.model_validate(s, from_attributes=True) for s in items],
        total=total,
    )


@router.get("/rss", response_model=list[RssStateOut])
def list_rss_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[RssStateOut]:
    rows = db.query(RssState).order_by(RssState.last_fetch_at.desc().nullslast()).offset(offset).limit(limit).all()
    return [RssStateOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/telegram", response_model=list[TgStateOut])
def list_tg_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[TgStateOut]:
    rows = (
        db.query(TgChannelState)
        .order_by(TgChannelState.last_fetch_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [TgStateOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/max", response_model=list[MaxStateOut])
def list_max_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[MaxStateOut]:
    rows = (
        db.query(MaxChannelState)
        .order_by(MaxChannelState.last_fetch_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [MaxStateOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/vk", response_model=list[VkStateOut])
def list_vk_state(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[VkStateOut]:
    rows = (
        db.query(VkGroupState)
        .order_by(VkGroupState.last_fetch_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [VkStateOut.model_validate(r, from_attributes=True) for r in rows]

