from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

from app.api.monitoring import build_monitoring_alerts, summarize_monitoring_alerts


def _source(
    *,
    enabled: bool = True,
    name: str = "source",
    base_url: str | None = None,
    feed_url: str | None = None,
    tg_channel_username: str | None = None,
    fetch_frequency_min: int = 60,
    consecutive_failures: int = 0,
    last_fetch_at: dt.datetime | None = None,
    last_success_at: dt.datetime | None = None,
    backoff_until: dt.datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        enabled=enabled,
        name=name,
        base_url=base_url,
        feed_url=feed_url,
        tg_channel_username=tg_channel_username,
        fetch_frequency_min=fetch_frequency_min,
        consecutive_failures=consecutive_failures,
        last_fetch_at=last_fetch_at,
        last_success_at=last_success_at,
        backoff_until=backoff_until,
    )


def test_build_monitoring_alerts_detects_critical_conditions() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    src = _source(
        name="Broken feed",
        consecutive_failures=4,
        last_fetch_at=now - dt.timedelta(hours=5),
        last_success_at=now - dt.timedelta(hours=10),
        backoff_until=now + dt.timedelta(hours=7),
    )

    alerts = build_monitoring_alerts([src], now=now)
    codes = {a.code for a in alerts}
    severities = {a.severity for a in alerts}

    assert "SOURCE_CONSECUTIVE_FAILURES_HIGH" in codes
    assert "SOURCE_BACKOFF_ACTIVE" in codes
    assert "SOURCE_STALE_SUCCESS" in codes
    assert "critical" in severities


def test_summarize_monitoring_alerts_counts_by_severity() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    src_a = _source(name="Never run", last_fetch_at=None, last_success_at=None)
    src_b = _source(name="Minor fail", consecutive_failures=1, last_success_at=now - dt.timedelta(minutes=20))

    alerts = build_monitoring_alerts([src_a, src_b], now=now)
    critical, warning, info = summarize_monitoring_alerts(alerts)

    assert critical >= 0
    assert warning >= 2
    assert info == 0
