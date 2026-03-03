from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from app.core.settings import settings
from app.models.domain import NewsItem, Source, TgChannelState
from app.parsers.keyword_filter import should_keep_item
from app.parsers.normalize import canonicalize_url, normalize_text, sha256_hex, simhash64
from app.tagging.rules import tag_item


def _ensure_tg_config() -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash or not settings.telegram_phone:
        raise RuntimeError(
            "Telegram credentials are not configured. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE."
        )


async def _ingest_async(db: Session, *, source: Source) -> dict[str, Any]:
    if not source.tg_channel_username:
        raise ValueError("tg_channel_username required")

    _ensure_tg_config()

    st = db.query(TgChannelState).filter(TgChannelState.source_id == source.id).one_or_none()
    if not st:
        st = TgChannelState(source_id=source.id, channel_username=source.tg_channel_username)
        db.add(st)
        db.commit()

    username = source.tg_channel_username.lstrip("@")
    st.channel_username = username
    st.last_fetch_at = dt.datetime.now(dt.timezone.utc)
    st.fetched_count_last_run = 0
    db.commit()

    session_name = f"newsint_{username}"
    client = TelegramClient(
        session=f"{settings.telegram_session_dir}/{session_name}",
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
    )

    backfill = int((source.settings_json or {}).get("backfill_limit") or 200)
    tail = int((source.settings_json or {}).get("recheck_tail_window") or 50)

    inserted = 0
    fetched = 0
    try:
        await client.connect()
        if not await client.is_user_authorized():
            # We don't do interactive code entry in workers.
            raise RuntimeError(
                "Telegram session is not authorized. Run one-time auth to create session file in TELEGRAM_SESSION_DIR."
            )

        entity = await client.get_entity(username)
        st.channel_id = getattr(entity, "id", None)

        # 1) Initial backfill if never fetched
        if not st.last_message_id:
            msgs = await client.get_messages(entity, limit=backfill)
        else:
            # 2) Incremental fetch newer than last_message_id
            msgs = await client.get_messages(entity, min_id=st.last_message_id, limit=backfill)
            # 3) Recheck tail window for edits
            if tail > 0:
                tail_msgs = await client.get_messages(entity, limit=tail)
                # merge unique by id
                by_id = {m.id: m for m in msgs}
                for m in tail_msgs:
                    by_id[m.id] = m
                msgs = list(by_id.values())

        # Process oldest->newest
        msgs.sort(key=lambda m: m.id or 0)

        max_id = st.last_message_id or 0
        for m in msgs:
            if not m or not m.id:
                continue
            fetched += 1
            max_id = max(max_id, m.id)
            text = m.message or ""
            if not text.strip():
                continue

            url = f"https://t.me/{username}/{m.id}"
            canonical = canonicalize_url(url)
            title = normalize_text(text)[:120] or None
            content_text = normalize_text(text)
            published_at = m.date
            if published_at and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=dt.timezone.utc)

            search_text = " ".join([str(url or ""), title or "", content_text])
            if not should_keep_item(search_text, source.settings_json):
                continue

            norm_hash = sha256_hex(content_text) if content_text else None
            sh = simhash64(content_text) if content_text else None

            tags = tag_item(
                db,
                text=search_text,
                source_region_ids=source.region_tags,
                source_competitor_id=source.competitor_id,
            )

            stmt = (
                pg_insert(NewsItem)
                .values(
                    source_id=source.id,
                    competitor_id=source.competitor_id,
                    url=url,
                    canonical_url=canonical,
                    title=title,
                    author=username,
                    published_at=published_at,
                    snippet=content_text[:300] if content_text else None,
                    content_text=content_text,
                    content_html=None,
                    normalized_text_hash=norm_hash,
                    simhash64=sh,
                    region_ids=tags["region_ids"],
                    competitor_mentions=tags["competitor_mentions"],
                    topic_tags=tags["topic_tags"],
                )
                .on_conflict_do_nothing(index_elements=["canonical_url"])
            )
            res = db.execute(stmt)
            if res.rowcount:
                inserted += 1
                st.fetched_count_last_run += 1

        st.last_message_id = max_id if max_id else st.last_message_id
        st.last_success_at = dt.datetime.now(dt.timezone.utc)
        st.last_error = None
        db.commit()
        return {"status": "ok", "fetched": fetched, "inserted": inserted, "last_message_id": st.last_message_id}

    except FloodWaitError as fw:
        # Save error and re-raise for RQ retry/backoff policy to handle
        st.last_error = f"FloodWait {fw.seconds}s"
        db.commit()
        await asyncio.sleep(min(30, fw.seconds))
        raise
    finally:
        await client.disconnect()


def ingest_telegram(db: Session, *, source: Source) -> dict[str, Any]:
    return asyncio.run(_ingest_async(db, source=source))

