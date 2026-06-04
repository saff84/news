"""Сбор постов из Telegram-канала для раздела «Индикаторы» (картинка + текст по ключам)."""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from app.core.settings import settings
from app.models.domain import IndicatorTelegramPost
from app.parsers.keyword_filter import explain_filter, parse_keyword_list, should_keep_item
from app.services.indicator_telegram_config import get_indicator_telegram_config, save_indicator_telegram_config
from app.services.telegram_config import get_telegram_config


def _media_dir() -> Path:
    d = Path(settings.storage_dir) / "indicator_tg"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_tg_config(cfg: dict) -> None:
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    has_session_string = bool(cfg.get("session_string"))
    has_phone_auth = has_api and bool(settings.telegram_phone)
    if not (has_session_string or has_phone_auth) or not has_api:
        raise RuntimeError(
            "Telegram credentials not configured. Настройте в UI: Telegram-парсер, или в .env."
        )


def _parse_until_date(raw: object) -> dt.datetime | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()[:10]
    try:
        d = dt.date.fromisoformat(s)
        return dt.datetime.combine(d, dt.time.max, tzinfo=dt.timezone.utc)
    except ValueError:
        return None


async def _fetch_channel_messages(
    client: TelegramClient,
    entity: Any,
    *,
    backfill: int,
    last_message_id: int,
    reset_history: bool,
    until_date: dt.datetime | None,
) -> list[Any]:
    """reset_history / нет курсора — глубокий backfill; иначе только новые + хвост канала."""
    if reset_history or not last_message_id:
        kwargs: dict[str, Any] = {"limit": backfill}
        if until_date:
            kwargs["offset_date"] = until_date
        msgs = await client.get_messages(entity, **kwargs)
        return [m for m in (msgs or []) if m and m.id]

    # Только сообщения новее курсора — уже сохранённые в БД не перекачиваем.
    msgs = await client.get_messages(entity, min_id=last_message_id, limit=backfill)
    return [m for m in (msgs or []) if m and m.id]


def _filter_settings(cfg: dict) -> dict:
    return {
        "include_keywords": parse_keyword_list(cfg.get("include_keywords")),
        "exclude_keywords": parse_keyword_list(cfg.get("exclude_keywords")),
        "match_whole_words": bool(cfg.get("match_whole_words")),
    }


def _public_image_path(filename: str) -> str:
    return f"/indicator-media/{filename}"


async def _download_first_image(client: TelegramClient, message: Any, *, username: str, message_id: int) -> str | None:
    if not getattr(message, "photo", None):
        return None
    filename = f"{username}_{message_id}.jpg"
    dest = _media_dir() / filename
    if dest.exists() and dest.stat().st_size > 0:
        return _public_image_path(filename)
    try:
        saved = await client.download_media(message, file=str(dest))
        if saved and dest.exists() and dest.stat().st_size > 0:
            return _public_image_path(filename)
    except Exception:
        if dest.exists():
            dest.unlink(missing_ok=True)
    return None


async def _ingest_async(db: Session, *, force: bool = False, reset_history: bool = False) -> dict[str, Any]:
    cfg = get_indicator_telegram_config(db)
    if not cfg.get("enabled") and not force:
        return {"status": "skipped", "reason": "disabled"}
    username = str(cfg.get("channel_username") or "").strip().lstrip("@")
    if not username:
        raise ValueError("channel_username is required in indicator telegram config")

    tg_cfg = get_telegram_config(db)
    _ensure_tg_config(tg_cfg)

    filter_cfg = _filter_settings(cfg)
    backfill = int(cfg.get("backfill_limit") or 100)
    last_message_id = 0 if reset_history else int(cfg.get("last_message_id") or 0)
    until_date = _parse_until_date(cfg.get("backfill_until_date"))

    session_string = tg_cfg.get("session_string") or ""
    session: str | StringSession = StringSession(session_string) if session_string else f"{settings.telegram_session_dir}/newsint_main"
    client = TelegramClient(session=session, api_id=tg_cfg["api_id"], api_hash=tg_cfg["api_hash"])

    inserted = 0
    updated = 0
    fetched = 0
    matched = 0
    max_id = last_message_id

    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")

        entity = await client.get_entity(username)
        msgs = await _fetch_channel_messages(
            client,
            entity,
            backfill=backfill,
            last_message_id=last_message_id,
            reset_history=reset_history,
            until_date=until_date,
        )

        msgs.sort(key=lambda m: m.id or 0)

        for m in msgs:
            if not m or not m.id:
                continue
            fetched += 1
            max_id = max(max_id, m.id)
            text = (m.message or "").strip()
            if not text and not getattr(m, "photo", None):
                continue

            search_text = text or f"post {m.id}"
            if not should_keep_item(search_text, filter_cfg):
                continue
            matched += 1
            explain = explain_filter(search_text, filter_cfg)

            image_path = await _download_first_image(client, m, username=username, message_id=m.id)
            published_at = m.date
            if published_at and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=dt.timezone.utc)

            post_url = f"https://t.me/{username}/{m.id}"
            values = {
                "channel_username": username,
                "message_id": m.id,
                "post_url": post_url,
                "text": text or None,
                "image_path": image_path,
                "published_at": published_at,
                "matched_keywords": explain.get("matched_keywords") or [],
            }
            existing = (
                db.query(IndicatorTelegramPost)
                .filter(
                    IndicatorTelegramPost.channel_username == username,
                    IndicatorTelegramPost.message_id == m.id,
                )
                .one_or_none()
            )
            if existing:
                if reset_history:
                    existing.post_url = post_url
                    existing.text = values["text"]
                    existing.image_path = image_path or existing.image_path
                    existing.published_at = published_at
                    existing.matched_keywords = values["matched_keywords"]
                    updated += 1
                continue
            db.add(IndicatorTelegramPost(**values))
            inserted += 1

        save_indicator_telegram_config(
            db,
            last_message_id=max_id if max_id else last_message_id,
            last_fetch_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            last_error=None,
        )
        db.commit()
        return {
            "status": "ok",
            "channel": username,
            "fetched": fetched,
            "matched": matched,
            "inserted": inserted,
            "updated": updated,
            "last_message_id": max_id,
            "reset_history": reset_history,
            "backfill_until_date": cfg.get("backfill_until_date"),
        }
    except FloodWaitError as fw:
        save_indicator_telegram_config(db, last_error=f"FloodWait {fw.seconds}s")
        db.commit()
        await asyncio.sleep(min(30, fw.seconds))
        raise
    finally:
        await client.disconnect()


def ingest_indicator_telegram(db: Session, *, force: bool = False, reset_history: bool = False) -> dict[str, Any]:
    return asyncio.run(_ingest_async(db, force=force, reset_history=reset_history))
