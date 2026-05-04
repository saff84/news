from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.orm import Session
from telethon.errors import FloodWaitError

from app.db import SessionLocal
from app.models.domain import MaxChannelState, RssState, Source, SourceType, TgChannelState, VkGroupState
from app.parsers.html_ingestor import ingest_html
from app.parsers.max_ingestor import ingest_max_channel
from app.parsers.rss_ingestor import ingest_rss
from app.parsers.telegram_ingestor import ingest_telegram
from app.parsers.vk_ingestor import ingest_vk_group
from app.workers.indicators import fetch_indicator_cny_rub
from app.workers.queue import get_redis

log = logging.getLogger("workers.jobs")


def run_indicator_job(series: str) -> dict:
    """
    Run indicator collection job (CNY_RUB etc). Used by RQ worker.
    Must be in a proper module (not __main__) so RQ can import it.
    """
    import time

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(*, failures: int, floor_s: int = 60, cap_s: int = 24 * 60 * 60) -> int:
    """
    Exponential-ish backoff for persistent failures.
    failures=1 -> 60s, 2 -> 5m, 3 -> 15m, 4 -> 1h, 5 -> 6h, 6+ -> 24h (cap)
    """
    if failures <= 1:
        s = 60
    elif failures == 2:
        s = 5 * 60
    elif failures == 3:
        s = 15 * 60
    elif failures == 4:
        s = 60 * 60
    elif failures == 5:
        s = 6 * 60 * 60
    else:
        s = 24 * 60 * 60
    return max(floor_s, min(cap_s, s))


def fetch_source(source_id: str) -> dict:
    """
    Fetch/parse a single source.
    For now this is a safe skeleton that updates health fields and returns stats.
    Concrete parsers (HTML/RSS/TG) will be plugged in next.
    """
    sid = uuid.UUID(source_id)
    db: Session = SessionLocal()
    try:
        src = db.get(Source, sid)
        if not src:
            return {"status": "missing", "source_id": source_id}
        if not src.enabled:
            return {"status": "disabled", "source_id": source_id}

        # Mark attempt start
        src.last_fetch_at = _now()
        db.commit()

        # Ensure per-type state rows exist
        if src.source_type == SourceType.RSS_ATOM:
            if not db.query(RssState).filter(RssState.source_id == src.id).one_or_none():
                db.add(RssState(source_id=src.id))
                db.commit()
        if src.source_type == SourceType.TELEGRAM_CHANNEL:
            if not db.query(TgChannelState).filter(TgChannelState.source_id == src.id).one_or_none():
                db.add(TgChannelState(source_id=src.id, channel_username=src.tg_channel_username or ""))
                db.commit()
        if src.source_type == SourceType.MAX_CHANNEL:
            cfg = src.settings_json or {}
            max_channel_id = str(cfg.get("max_channel_id") or "").strip()
            if not db.query(MaxChannelState).filter(MaxChannelState.source_id == src.id).one_or_none():
                db.add(MaxChannelState(source_id=src.id, channel_id=max_channel_id))
                db.commit()
        if src.source_type == SourceType.VK_GROUP:
            cfg = src.settings_json or {}
            vk_group_id = str(cfg.get("vk_group_id") or "").strip()
            if not db.query(VkGroupState).filter(VkGroupState.source_id == src.id).one_or_none():
                db.add(VkGroupState(source_id=src.id, group_id=vk_group_id))
                db.commit()

        # Ingest based on type
        if src.source_type == SourceType.RSS_ATOM:
            result = ingest_rss(db, source=src)
        elif src.source_type in (SourceType.HTML_LIST_DETAIL, SourceType.HTML_DETAIL_ONLY, SourceType.SITEMAP):
            result = ingest_html(db, source=src)
        elif src.source_type == SourceType.TELEGRAM_CHANNEL:
            result = ingest_telegram(db, source=src)
        elif src.source_type == SourceType.MAX_CHANNEL:
            result = ingest_max_channel(db, source=src)
        elif src.source_type == SourceType.VK_GROUP:
            result = ingest_vk_group(db, source=src)
        else:
            raise ValueError(f"Unsupported source_type: {src.source_type}")

        src.last_success_at = _now()
        src.last_error = None
        src.consecutive_failures = 0
        src.backoff_until = None
        db.commit()
        return {"status": "ok", "source_id": source_id, "result": result}
    except Exception as e:
        log.exception("fetch_source failed", extra={"source_id": source_id})
        try:
            src = db.get(Source, sid)
            if src:
                src.last_error = str(e)
                src.consecutive_failures = (src.consecutive_failures or 0) + 1

                backoff_s: int | None = None
                if isinstance(e, FloodWaitError):
                    backoff_s = int(getattr(e, "seconds", 60))
                elif isinstance(e, httpx.HTTPStatusError) and getattr(e, "response", None) is not None:
                    if e.response.status_code == 429:
                        ra = e.response.headers.get("retry-after")
                        try:
                            backoff_s = int(ra) if ra else 60
                        except Exception:
                            backoff_s = 60
                elif isinstance(e, PermissionError):
                    # Usually robots.txt or similar policy; pause longer to avoid repeated violations.
                    backoff_s = 24 * 60 * 60

                if backoff_s is None:
                    backoff_s = _backoff_seconds(failures=int(src.consecutive_failures or 1))

                src.backoff_until = _now().replace(microsecond=0) + timedelta(seconds=int(backoff_s))
                db.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            r = get_redis()
            r.delete(f"lock:source:{sid}")
        except Exception:
            pass
        db.close()


def rebuild_news_clusters_job(
    days: int = 90,
    threshold: int = 3,
    max_items: int = 2000,
) -> dict:
    """Фоновая пересборка кластеров похожих новостей (simhash)."""
    from app.services.news_clustering import rebuild_news_clusters

    db: Session = SessionLocal()
    try:
        return rebuild_news_clusters(db, days=days, threshold=threshold, max_items=max_items)
    finally:
        db.close()

