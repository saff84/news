from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from rq import Retry
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.domain import Source
from app.workers.jobs import fetch_source
from app.workers.indicators import fetch_indicator_cny_rub
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
            q.enqueue(_run_indicator_job, "CNY_RUB", job_timeout=120)
            enqueued += 1

    return enqueued


def _run_indicator_job(series: str) -> dict:
    """
    Wrapper to run indicator jobs with DB session and update Redis timestamps.
    """
    redis = get_redis()
    db: Session = SessionLocal()
    try:
        if series == "CNY_RUB":
            res = fetch_indicator_cny_rub(db)
        else:
            raise ValueError(f"Unknown indicator series: {series}")
        try:
            redis.set("indicators:CNY_RUB:last_ok_ts", str(int(time.time())), ex=7 * 24 * 60 * 60)
        except Exception:
            pass
        return res
    finally:
        try:
            redis.delete(f"lock:indicator:{series}")
        except Exception:
            pass
        db.close()


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
        except Exception:
            log.exception("scheduler loop failed")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()

