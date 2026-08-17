"""Сбор постов из TG-каналов конкурентов (глубокий backfill до 24 мес.)."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from app.core.settings import settings
from app.models.domain import CompetitorTelegramPost, CompetitorTelegramProfile
from app.parsers.keyword_filter import should_keep_item
from app.services.indicator_telegram_report import clean_telegram_post_text
from app.services.telegram_config import get_telegram_config
from app.services.telegram_errors import humanize_telegram_error

BATCH_LIMIT = 500


def _ensure_tg_config(cfg: dict) -> None:
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    has_session_string = bool(cfg.get("session_string"))
    has_phone_auth = has_api and bool(settings.telegram_phone)
    if not (has_session_string or has_phone_auth) or not has_api:
        raise RuntimeError(
            "Telegram credentials not configured. Настройте в UI: Telegram-парсер, или в .env."
        )


def _default_until_date() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=730)).date()


def _filter_settings(profile: CompetitorTelegramProfile) -> dict:
    return {
        "include_keywords": list(profile.include_keywords or []),
        "exclude_keywords": list(profile.exclude_keywords or []),
        "match_whole_words": bool(profile.match_whole_words),
    }


def _group_message_units(msgs: list[Any]) -> list[list[Any]]:
    by_gid: dict[int, list[Any]] = defaultdict(list)
    singles: list[list[Any]] = []
    for m in msgs:
        gid = getattr(m, "grouped_id", None)
        if gid:
            by_gid[int(gid)].append(m)
        else:
            singles.append([m])
    return singles + [sorted(g, key=lambda x: x.id or 0) for g in by_gid.values()]


def _extract_unit_text(unit: list[Any]) -> str:
    for m in sorted(unit, key=lambda x: x.id or 0, reverse=True):
        text = (m.message or "").strip()
        if text:
            return text
    return ""


def _unit_primary_message(unit: list[Any]) -> Any:
    return min(unit, key=lambda x: x.id or 0)


def _message_dt(message: Any) -> dt.datetime | None:
    published_at = getattr(message, "date", None)
    if published_at and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=dt.timezone.utc)
    return published_at


async def _fetch_batch(
    client: TelegramClient,
    entity: Any,
    *,
    profile: CompetitorTelegramProfile,
    reset_history: bool,
) -> list[Any]:
    username = profile.tg_channel_username.strip().lstrip("@")
    if reset_history or not profile.backfill_complete:
        kwargs: dict[str, Any] = {"limit": BATCH_LIMIT}
        if profile.backfill_cursor_date:
            kwargs["offset_date"] = profile.backfill_cursor_date
        elif profile.last_message_id:
            kwargs["min_id"] = int(profile.last_message_id)
            return [m for m in (await client.get_messages(entity, **kwargs)) or [] if m and m.id]
        msgs = await client.get_messages(entity, **kwargs)
        return [m for m in (msgs or []) if m and m.id]

    msgs = await client.get_messages(entity, min_id=int(profile.last_message_id or 0), limit=BATCH_LIMIT)
    return [m for m in (msgs or []) if m and m.id]


def _post_values(
    unit: list[Any],
    *,
    username: str,
    profile_id: Any,
) -> dict[str, Any]:
    primary = _unit_primary_message(unit)
    text_raw = _extract_unit_text(unit)
    text = clean_telegram_post_text(text_raw) or None
    published_at = _message_dt(primary)
    return {
        "profile_id": profile_id,
        "message_id": int(primary.id),
        "post_url": f"https://t.me/{username}/{primary.id}",
        "text": text,
        "published_at": published_at,
    }


async def _ingest_async(
    db: Session,
    profile: CompetitorTelegramProfile,
    *,
    reset_history: bool = False,
) -> dict[str, Any]:
    username = str(profile.tg_channel_username or "").strip().lstrip("@")
    if not username:
        raise ValueError("tg_channel_username is required")

    until_date = profile.backfill_until_date or _default_until_date()
    tg_cfg = get_telegram_config(db)
    _ensure_tg_config(tg_cfg)
    filter_cfg = _filter_settings(profile)

    if reset_history:
        profile.last_message_id = 0
        profile.backfill_complete = False
        profile.backfill_cursor_date = None

    session_string = tg_cfg.get("session_string") or ""
    session: str | StringSession = StringSession(session_string) if session_string else f"{settings.telegram_session_dir}/newsint_main"
    client = TelegramClient(session=session, api_id=tg_cfg["api_id"], api_hash=tg_cfg["api_hash"])

    inserted = 0
    fetched = 0
    matched = 0
    max_id = int(profile.last_message_id or 0)
    oldest_dt: dt.datetime | None = None
    reached_until = False

    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")

        entity = await client.get_entity(username)
        msgs = await _fetch_batch(client, entity, profile=profile, reset_history=reset_history)
        msgs.sort(key=lambda m: m.id or 0)

        processed_units: set[tuple[int, int]] = set()
        for unit in _group_message_units(msgs):
            primary = _unit_primary_message(unit)
            if not primary.id:
                continue
            gid = int(getattr(primary, "grouped_id", None) or 0)
            unit_key = (gid, int(primary.id))
            if unit_key in processed_units:
                continue
            processed_units.add(unit_key)

            pub = _message_dt(primary)
            if pub:
                if oldest_dt is None or pub < oldest_dt:
                    oldest_dt = pub
                if pub.date() < until_date:
                    reached_until = True
                    continue

            for m in unit:
                fetched += 1
                max_id = max(max_id, int(m.id))

            text_raw = _extract_unit_text(unit)
            if not text_raw:
                continue

            search_text = text_raw
            if not should_keep_item(search_text, filter_cfg):
                continue
            matched += 1

            values = _post_values(unit, username=username, profile_id=profile.id)
            existing = (
                db.query(CompetitorTelegramPost)
                .filter(
                    CompetitorTelegramPost.profile_id == profile.id,
                    CompetitorTelegramPost.message_id == values["message_id"],
                )
                .one_or_none()
            )
            if existing:
                continue
            db.add(CompetitorTelegramPost(**values))
            inserted += 1

        if profile.backfill_complete:
            profile.last_message_id = max(max_id, int(profile.last_message_id or 0))
        elif reset_history or not profile.backfill_cursor_date:
            if oldest_dt and not reached_until and len(msgs) >= BATCH_LIMIT:
                profile.backfill_cursor_date = oldest_dt
            else:
                profile.backfill_complete = True
                profile.backfill_cursor_date = None
                profile.last_message_id = max(max_id, int(profile.last_message_id or 0))
        else:
            if reached_until or len(msgs) < BATCH_LIMIT:
                profile.backfill_complete = True
                profile.backfill_cursor_date = None
                profile.last_message_id = max(max_id, int(profile.last_message_id or 0))
            elif oldest_dt:
                profile.backfill_cursor_date = oldest_dt

        profile.last_fetch_at = dt.datetime.now(dt.timezone.utc)
        profile.last_error = None
        if not profile.backfill_until_date:
            profile.backfill_until_date = until_date
        db.commit()

        total_posts = db.query(CompetitorTelegramPost).filter(CompetitorTelegramPost.profile_id == profile.id).count()
        return {
            "status": "ok",
            "channel": username,
            "fetched": fetched,
            "matched": matched,
            "inserted": inserted,
            "total_posts": total_posts,
            "last_message_id": profile.last_message_id,
            "backfill_complete": profile.backfill_complete,
            "backfill_until_date": until_date.isoformat(),
            "reset_history": reset_history,
        }
    except FloodWaitError as fw:
        profile.last_error = f"FloodWait {fw.seconds}s"
        db.commit()
        await asyncio.sleep(min(30, fw.seconds))
        raise
    except Exception as e:
        profile.last_error = humanize_telegram_error(e) or str(e)
        db.commit()
        raise
    finally:
        await client.disconnect()


def ingest_competitor_telegram(
    db: Session,
    profile: CompetitorTelegramProfile,
    *,
    reset_history: bool = False,
) -> dict[str, Any]:
    return asyncio.run(_ingest_async(db, profile, reset_history=reset_history))
