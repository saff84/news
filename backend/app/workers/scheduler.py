from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from rq import Retry
from sqlalchemy import func, or_, text

from app.db import SessionLocal
from app.models.domain import Source
from app.workers.jobs import fetch_source, rebuild_news_clusters_job, run_indicator_job
from app.workers.queue import get_queue, get_redis

log = logging.getLogger("workers.scheduler")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_due_sources(*, batch_limit: int = 100) -> int:
    """
    Select due sources and enqueue `fetch_source` jobs.

    Due criteria (initial skeleton):
    - enabled = true
    - not in backoff window
    - last_fetch_at is null OR older than fetch_frequency_min
    """
    db: Session = SessionLocal()
    q = get_queue("default")
    redis = get_redis()
    try:
        due = (
            db.query(Source)
            .filter(Source.enabled.is_(True))
            .filter(or_(Source.backoff_until.is_(None), Source.backoff_until <= func.now()))
            .filter(
                or_(
                    Source.last_fetch_at.is_(None),
                    Source.last_fetch_at
                    <= (
                        func.now()
                        - (Source.fetch_frequency_min * text("interval '1 minute'"))
                    ),
                )
            )
            .order_by(Source.priority.desc(), Source.last_fetch_at.asc().nullsfirst())
            .limit(batch_limit)
            .all()
        )

        enqueued = 0
        for src in due:
            # Prevent duplicate enqueues across scheduler loops while a job is in-flight.
            # The lock is released by the worker job in `fetch_source` (best-effort).
            lock_key = f"lock:source:{src.id}"
            try:
                locked = redis.set(lock_key, "1", nx=True, ex=60 * 15)
            except Exception:
                locked = True
            if not locked:
                continue

            job_retry = Retry(max=src.retries or 0, interval=[10, 30, 120])
            q.enqueue(fetch_source, str(src.id), retry=job_retry, job_timeout=600)
            enqueued += 1

        return enqueued
    finally:
        db.close()


def enqueue_due_indicators() -> int:
    """
    Enqueue indicator collection jobs.
    Uses Redis keys for throttling + to avoid duplicates.
    """
    q = get_queue("default")
    redis = get_redis()

    enqueued = 0

    # CNY/RUB from MOEX: refresh ~hourly is enough for admin UI
    lock_key = "lock:indicator:CNY_RUB"
    last_ok_key = "indicators:CNY_RUB:last_ok_ts"
    now = int(time.time())
    min_interval_s = int(os.getenv("INDICATOR_CNY_RUB_MIN_INTERVAL_S", "3600"))

    try:
        last_ok = int(redis.get(last_ok_key) or 0)
    except Exception:
        last_ok = 0

    if now - last_ok >= min_interval_s:
        try:
            locked = redis.set(lock_key, "1", nx=True, ex=60 * 10)
        except Exception:
            locked = True
        if locked:
            q.enqueue(run_indicator_job, "CNY_RUB", job_timeout=120)
            enqueued += 1

    return enqueued


def enqueue_rebuild_news_clusters() -> int:
    """Периодически ставит в очередь пересборку кластеров новостей. NEWS_CLUSTER_REBUILD_INTERVAL_S=0 отключает."""
    interval_s = int(os.getenv("NEWS_CLUSTER_REBUILD_INTERVAL_S", str(6 * 3600)))
    if interval_s <= 0:
        return 0
    redis = get_redis()
    q = get_queue("default")
    now = int(time.time())
    throttle_key = "news_clusters:last_enqueue_ts"
    lock_key = "lock:news_clusters:enqueue"
    try:
        last = int(redis.get(throttle_key) or 0)
    except Exception:
        last = 0
    if now - last < interval_s:
        return 0
    try:
        if not redis.set(lock_key, "1", nx=True, ex=300):
            return 0
    except Exception:
        pass
    q.enqueue(rebuild_news_clusters_job, job_timeout=900)
    try:
        redis.set(throttle_key, str(now), ex=14 * 24 * 3600)
    except Exception:
        pass
    return 1


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    sleep_s = int(os.getenv("SCHEDULER_SLEEP_SECONDS", "10"))
    batch_limit = int(os.getenv("SCHEDULER_BATCH_LIMIT", "100"))

    log.info("scheduler started", extra={"sleep_s": sleep_s, "batch_limit": batch_limit})
    while True:
        try:
            n = enqueue_due_sources(batch_limit=batch_limit)
            if n:
                log.info("enqueued sources", extra={"count": n})
            m = enqueue_due_indicators()
            if m:
                log.info("enqueued indicators", extra={"count": m})
            k = enqueue_rebuild_news_clusters()
            if k:
                log.info("enqueued news cluster rebuild", extra={"count": k})
        except Exception:
            log.exception("scheduler loop failed")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()

