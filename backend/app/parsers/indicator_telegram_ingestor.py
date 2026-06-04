"""Сбор постов из Telegram-канала для раздела «Индикаторы» (картинка + текст по ключам)."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections import defaultdict
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
from app.services.indicator_telegram_report import clean_telegram_post_text
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


def _group_message_units(msgs: list[Any]) -> list[list[Any]]:
    """Альбом TG = несколько сообщений с одним grouped_id."""
    by_gid: dict[int, list[Any]] = defaultdict(list)
    singles: list[list[Any]] = []
    for m in msgs:
        gid = getattr(m, "grouped_id", None)
        if gid:
            by_gid[int(gid)].append(m)
        else:
            singles.append([m])
    units = singles + [sorted(g, key=lambda x: x.id or 0) for g in by_gid.values()]
    return units


def _extract_unit_text(unit: list[Any]) -> str:
    for m in sorted(unit, key=lambda x: x.id or 0, reverse=True):
        text = (m.message or "").strip()
        if text:
            return text
    return ""


def _unit_primary_message(unit: list[Any]) -> Any:
    return min(unit, key=lambda x: x.id or 0)


async def _download_message_photo(
    client: TelegramClient,
    message: Any,
    *,
    username: str,
    message_id: int,
) -> str | None:
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


async def _download_all_images_for_unit(
    client: TelegramClient,
    unit: list[Any],
    *,
    username: str,
) -> list[str]:
    paths: list[str] = []
    for m in sorted(unit, key=lambda x: x.id or 0):
        if not m.id:
            continue
        path = await _download_message_photo(client, m, username=username, message_id=int(m.id))
        if path:
            paths.append(path)
    return paths


async def _album_unit_for_message(
    client: TelegramClient,
    entity: Any,
    message: Any,
    *,
    cache: dict[int, list[Any]],
) -> list[Any]:
    gid = getattr(message, "grouped_id", None)
    if not gid:
        return [message]
    gid = int(gid)
    if gid in cache:
        return cache[gid]
    window = await client.get_messages(entity, min_id=int(message.id) - 20, max_id=int(message.id) + 20)
    unit = sorted(
        [m for m in (window or []) if m and getattr(m, "grouped_id", None) == gid],
        key=lambda x: x.id or 0,
    )
    if not unit:
        unit = [message]
    cache[gid] = unit
    return unit


def _post_values_from_unit(
    unit: list[Any],
    *,
    username: str,
    image_paths: list[str],
    matched_keywords: list[str],
) -> dict[str, Any]:
    primary = _unit_primary_message(unit)
    text_raw = _extract_unit_text(unit)
    text = clean_telegram_post_text(text_raw) or None
    published_at = primary.date
    if published_at and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=dt.timezone.utc)
    return {
        "channel_username": username,
        "message_id": int(primary.id),
        "post_url": f"https://t.me/{username}/{primary.id}",
        "text": text,
        "image_path": image_paths[0] if image_paths else None,
        "image_paths": image_paths,
        "published_at": published_at,
        "matched_keywords": matched_keywords,
    }


async def _refresh_existing_posts_media(
    client: TelegramClient,
    entity: Any,
    db: Session,
    *,
    username: str,
    filter_cfg: dict,
) -> int:
    rows = (
        db.query(IndicatorTelegramPost)
        .filter(IndicatorTelegramPost.channel_username == username)
        .order_by(IndicatorTelegramPost.message_id.asc())
        .all()
    )
    if not rows:
        return 0
    msgs = await client.get_messages(entity, ids=[int(r.message_id) for r in rows])
    by_id = {int(m.id): m for m in (msgs or []) if m and m.id}
    album_cache: dict[int, list[Any]] = {}
    updated = 0
    for row in rows:
        m = by_id.get(int(row.message_id))
        if not m:
            continue
        unit = await _album_unit_for_message(client, entity, m, cache=album_cache)
        image_paths = await _download_all_images_for_unit(client, unit, username=username)
        text_raw = _extract_unit_text(unit)
        search_text = text_raw or f"post {row.message_id}"
        explain = explain_filter(search_text, filter_cfg)
        row.image_paths = image_paths
        row.image_path = image_paths[0] if image_paths else row.image_path
        row.text = clean_telegram_post_text(text_raw) or row.text
        row.matched_keywords = explain.get("matched_keywords") or row.matched_keywords
        updated += 1
    return updated


async def _ingest_async(
    db: Session,
    *,
    force: bool = False,
    reset_history: bool = False,
    refresh_existing: bool = False,
) -> dict[str, Any]:
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

            for m in unit:
                fetched += 1
                max_id = max(max_id, int(m.id))

            text_raw = _extract_unit_text(unit)
            has_photo = any(getattr(m, "photo", None) for m in unit)
            if not text_raw and not has_photo:
                continue

            search_text = text_raw or f"post {primary.id}"
            if not should_keep_item(search_text, filter_cfg):
                continue
            matched += 1
            explain = explain_filter(search_text, filter_cfg)
            image_paths = await _download_all_images_for_unit(client, unit, username=username)
            values = _post_values_from_unit(
                unit,
                username=username,
                image_paths=image_paths,
                matched_keywords=explain.get("matched_keywords") or [],
            )

            existing = (
                db.query(IndicatorTelegramPost)
                .filter(
                    IndicatorTelegramPost.channel_username == username,
                    IndicatorTelegramPost.message_id == values["message_id"],
                )
                .one_or_none()
            )
            if existing:
                continue
            db.add(IndicatorTelegramPost(**values))
            inserted += 1

        if refresh_existing or reset_history:
            updated = await _refresh_existing_posts_media(
                client, entity, db, username=username, filter_cfg=filter_cfg
            )

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
            "refresh_existing": refresh_existing,
            "backfill_until_date": cfg.get("backfill_until_date"),
        }
    except FloodWaitError as fw:
        save_indicator_telegram_config(db, last_error=f"FloodWait {fw.seconds}s")
        db.commit()
        await asyncio.sleep(min(30, fw.seconds))
        raise
    finally:
        await client.disconnect()


def ingest_indicator_telegram(
    db: Session,
    *,
    force: bool = False,
    reset_history: bool = False,
    refresh_existing: bool = False,
) -> dict[str, Any]:
    return asyncio.run(
        _ingest_async(
            db,
            force=force,
            reset_history=reset_history,
            refresh_existing=refresh_existing,
        )
    )
