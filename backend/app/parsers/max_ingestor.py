from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.domain import MaxChannelState, NewsItem, Source
from app.services.max_config import get_max_config
from app.services.news_filter_config import should_keep_news_item
from app.parsers.normalize import canonicalize_url, normalize_text, period_month_from_dt, sha256_hex, simhash64
from app.tagging.rules import tag_item


def _pick_text(msg: dict[str, Any]) -> str:
    text = msg.get("text")
    if isinstance(text, str) and text.strip():
        return text
    body = msg.get("body")
    if isinstance(body, dict):
        v = body.get("text")
        if isinstance(v, str) and v.strip():
            return v
    payload = msg.get("payload")
    if isinstance(payload, dict):
        v = payload.get("text")
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _pick_message_id(msg: dict[str, Any]) -> str | None:
    for key in ("message_id", "messageId", "id"):
        v = msg.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _pick_published_at(msg: dict[str, Any]) -> dt.datetime | None:
    ts = msg.get("created_at") or msg.get("createdAt") or msg.get("date") or msg.get("timestamp")
    if isinstance(ts, (int, float)):
        # Heuristic: API timestamps are commonly in milliseconds.
        if ts > 10_000_000_000:
            ts = ts / 1000
        try:
            return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        except Exception:
            return None
    if isinstance(ts, str):
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            parsed = dt.datetime.fromisoformat(ts)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except Exception:
            return None
    return None


def _max_message_id(a: str | None, b: str) -> str:
    if not a:
        return b
    try:
        return str(max(int(a), int(b)))
    except Exception:
        return max(a, b)


def _extract_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("messages", "items", "data", "results"):
            arr = payload.get(key)
            if isinstance(arr, list):
                return [x for x in arr if isinstance(x, dict)]
    return []


def ingest_max_channel(db: Session, *, source: Source) -> dict[str, Any]:
    """
    Ingest messages from MAX channel/chat using Bot API.

    Expected source settings_json keys:
    - max_channel_id (required): chat/channel identifier.
    - max_bot_token (optional): override global token from env.
    - messages_path (optional): API path to read messages (default: /messages).
    - limit (optional): page size, default 100.
    - since_param (optional): incremental param name (default: from_message_id).
    - channel_param (optional): channel id param name (default: chat_id).
    """
    cfg = source.settings_json or {}
    channel_id = str(cfg.get("max_channel_id") or "").strip()
    if not channel_id:
        raise ValueError("settings_json.max_channel_id is required for MAX_CHANNEL")

    global_cfg = get_max_config(db)
    token = str(cfg.get("max_bot_token") or global_cfg.get("bot_token") or settings.max_bot_token or "").strip()
    if not token:
        raise RuntimeError("MAX bot token is not configured (settings_json.max_bot_token or MAX_BOT_TOKEN)")

    base = str(settings.max_api_base or "https://platform-api.max.ru").rstrip("/")
    path = str(cfg.get("messages_path") or "/messages")
    if not path.startswith("/"):
        path = "/" + path
    url = f"{base}{path}"

    state = db.query(MaxChannelState).filter(MaxChannelState.source_id == source.id).one_or_none()
    if not state:
        state = MaxChannelState(source_id=source.id, channel_id=channel_id)
        db.add(state)
        db.commit()
    else:
        state.channel_id = channel_id
        db.commit()

    params: dict[str, Any] = {}
    channel_param = str(cfg.get("channel_param") or "chat_id")
    since_param = str(cfg.get("since_param") or "from_message_id")
    limit = int(cfg.get("limit") or 100)
    params[channel_param] = channel_id
    params["limit"] = max(1, min(limit, 200))
    if state.last_message_id:
        params[since_param] = state.last_message_id

    inserted = 0
    fetched = 0
    state.last_fetch_at = dt.datetime.now(dt.timezone.utc)
    state.fetched_count_last_run = 0
    db.commit()

    headers = {"Authorization": token}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            messages = _extract_messages(resp.json())
    except Exception as e:
        state.last_error = str(e)
        db.commit()
        raise

    max_id = state.last_message_id
    for msg in messages:
        msg_id = _pick_message_id(msg)
        if not msg_id:
            continue
        fetched += 1
        max_id = _max_message_id(max_id, msg_id)

        text = _pick_text(msg)
        if not text.strip():
            continue

        clean = normalize_text(text)
        title = clean[:120] if clean else None
        published_at = _pick_published_at(msg)

        web_url = msg.get("url") or msg.get("link")
        if isinstance(web_url, str) and web_url.strip():
            item_url = web_url.strip()
        else:
            item_url = f"max://{channel_id}/{msg_id}"
        canonical = canonicalize_url(item_url)

        search_text = " ".join([item_url, title or "", clean])
        if not should_keep_news_item(db, search_text, source.settings_json):
            continue

        norm_hash = sha256_hex(clean) if clean else None
        sh = simhash64(clean) if clean else None
        tags = tag_item(
            db,
            text=search_text,
            source_region_ids=source.region_tags,
            source_competitor_id=source.competitor_id,
            source_developer_id=source.developer_id,
        )

        stmt = (
            pg_insert(NewsItem)
            .values(
                source_id=source.id,
                competitor_id=source.competitor_id,
                developer_id=source.developer_id,
                url=item_url,
                canonical_url=canonical,
                title=title,
                author=f"max:{channel_id}",
                published_at=published_at,
                period_month=period_month_from_dt(published_at, dt.datetime.now(dt.timezone.utc)),
                snippet=clean[:300] if clean else None,
                content_text=clean or None,
                content_html=None,
                normalized_text_hash=norm_hash,
                simhash64=sh,
                region_ids=tags["region_ids"],
                competitor_mentions=tags["competitor_mentions"],
                developer_mentions=tags["developer_mentions"],
                topic_tags=tags["topic_tags"],
            )
            .on_conflict_do_nothing(index_elements=["canonical_url"])
        )
        res = db.execute(stmt)
        if res.rowcount:
            inserted += 1
            state.fetched_count_last_run += 1

    state.last_message_id = max_id
    state.last_success_at = dt.datetime.now(dt.timezone.utc)
    state.last_error = None
    db.commit()
    return {"status": "ok", "fetched": fetched, "inserted": inserted, "last_message_id": state.last_message_id}
