from __future__ import annotations

import datetime as dt
from typing import Any

import feedparser
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.domain import NewsItem, RssState, Source
from app.parsers.limits import acquire_rate_slot, domain_key
from app.parsers.normalize import canonicalize_url, html_to_text, normalize_text, period_month_from_dt, sha256_hex, simhash64
from app.parsers.keyword_filter import should_keep_item
from app.parsers.robots import can_fetch
from app.tagging.rules import tag_item
from app.workers.queue import get_redis


def _to_dt(struct_time) -> dt.datetime | None:
    if not struct_time:
        return None
    try:
        return dt.datetime.fromtimestamp(dt.datetime(*struct_time[:6]).timestamp(), tz=dt.timezone.utc)
    except Exception:
        return None


def ingest_rss(db: Session, *, source: Source) -> dict[str, Any]:
    if not source.feed_url:
        raise ValueError("feed_url is required")

    redis = get_redis()
    if source.respect_robots_txt:
        d = can_fetch(source.feed_url, user_agent="NewsIntParser", redis=redis)
        if not d.allowed:
            raise PermissionError(f"Blocked by robots.txt: {source.feed_url}")
    acquire_rate_slot(
        redis,
        scope=f"source:{source.id}",
        max_per_minute=source.max_requests_per_minute,
        delay_ms=source.delay_ms,
    )
    acquire_rate_slot(
        redis,
        scope=f"domain:{domain_key(source.feed_url)}",
        max_per_minute=max(30, source.max_requests_per_minute),
        delay_ms=0,
    )

    state = db.query(RssState).filter(RssState.source_id == source.id).one_or_none()
    if not state:
        state = RssState(source_id=source.id)
        db.add(state)
        db.commit()

    headers: dict[str, str] = {"User-Agent": "NewsIntParser/0.1"}
    if state.etag:
        headers["If-None-Match"] = state.etag
    if state.last_modified:
        headers["If-Modified-Since"] = state.last_modified

    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(source.feed_url)
            state.last_fetch_at = dt.datetime.now(dt.timezone.utc)
            if resp.status_code == 304:
                state.last_success_at = dt.datetime.now(dt.timezone.utc)
                state.last_error = None
                db.commit()
                return {"status": "not_modified", "fetched": 0, "inserted": 0}
            resp.raise_for_status()

            state.etag = resp.headers.get("etag") or state.etag
            state.last_modified = resp.headers.get("last-modified") or state.last_modified

            feed = feedparser.parse(resp.content)
    except Exception as e:
        state.last_error = str(e)
        db.commit()
        raise

    inserted = 0
    fetched = 0
    for e in feed.entries or []:
        fetched += 1
        url = e.get("link") or e.get("id")
        if not url:
            continue
        canonical = canonicalize_url(str(url))

        title = e.get("title")
        summary = e.get("summary") or e.get("description")

        content_html = None
        if e.get("content"):
            # feedparser uses list of dicts with "value"
            try:
                content_html = e["content"][0].get("value")
            except Exception:
                content_html = None
        if not content_html and summary and "<" in str(summary):
            content_html = str(summary)

        content_text = None
        if content_html:
            content_text = html_to_text(content_html)
        elif summary:
            content_text = normalize_text(str(summary))

        published_at = _to_dt(e.get("published_parsed")) or _to_dt(e.get("updated_parsed"))

        norm = normalize_text(content_text or "")
        norm_hash = sha256_hex(norm) if norm else None
        sh = simhash64(norm) if norm else None

        search_text = " ".join([str(url or ""), str(title or ""), str(content_text or ""), str(summary or "")])
        if not should_keep_item(search_text, source.settings_json):
            continue

        tags = tag_item(
            db,
            text=search_text,
            source_region_ids=source.region_tags,
            source_competitor_id=source.competitor_id,
            source_developer_id=source.developer_id,
        )

        stmt = pg_insert(NewsItem).values(
            source_id=source.id,
            competitor_id=source.competitor_id,
            developer_id=source.developer_id,
            url=str(url),
            canonical_url=canonical,
            title=str(title) if title else None,
            author=None,
            published_at=published_at,
            period_month=period_month_from_dt(published_at, dt.datetime.now(dt.timezone.utc)),
            snippet=(normalize_text(content_text or "")[:300] if content_text else None),
            content_text=content_text,
            content_html=content_html,
            normalized_text_hash=norm_hash,
            simhash64=sh,
            region_ids=tags["region_ids"],
            competitor_mentions=tags["competitor_mentions"],
            developer_mentions=tags["developer_mentions"],
            topic_tags=tags["topic_tags"],
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["canonical_url"])
        res = db.execute(stmt)
        if res.rowcount:
            inserted += 1

    state.last_success_at = dt.datetime.now(dt.timezone.utc)
    state.last_error = None
    db.commit()

    return {"status": "ok", "fetched": fetched, "inserted": inserted}

