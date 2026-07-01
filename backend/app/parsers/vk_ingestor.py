from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.domain import NewsItem, Source, VkGroupState
from app.services.news_filter_config import should_keep_news_item
from app.parsers.normalize import canonicalize_url, normalize_text, period_month_from_dt, sha256_hex, simhash64
from app.tagging.rules import tag_item


def _pick_vk_token(source: Source) -> str:
    cfg = source.settings_json or {}
    token = str(cfg.get("vk_access_token") or settings.vk_access_token or "").strip()
    if not token:
        raise RuntimeError("VK token is not configured (settings_json.vk_access_token or VK_ACCESS_TOKEN)")
    return token


def _to_owner_and_domain(group_id_raw: str) -> tuple[str | None, str | None]:
    gid = group_id_raw.strip()
    if gid.startswith("https://vk.com/"):
        gid = gid.replace("https://vk.com/", "").strip("/")
    if gid.startswith("vk.com/"):
        gid = gid.replace("vk.com/", "").strip("/")
    if gid.startswith("public"):
        try:
            num = int(gid.replace("public", ""))
            return str(-abs(num)), None
        except Exception:
            return None, gid
    if gid.startswith("club"):
        try:
            num = int(gid.replace("club", ""))
            return str(-abs(num)), None
        except Exception:
            return None, gid
    if gid.lstrip("-").isdigit():
        num = int(gid)
        return str(-abs(num)), None
    return None, gid


def ingest_vk_group(db: Session, *, source: Source) -> dict[str, Any]:
    """
    Ingest posts from public VK groups via wall.get.

    Expected source.settings_json:
    - vk_group_id (required): numeric id, domain, public123, club123 or URL.
    - vk_access_token (optional): overrides env VK_ACCESS_TOKEN.
    - vk_limit (optional): default 100, max 100.
    """
    cfg = source.settings_json or {}
    group_id_raw = str(cfg.get("vk_group_id") or "").strip()
    if not group_id_raw:
        raise ValueError("settings_json.vk_group_id is required for VK_GROUP")

    token = _pick_vk_token(source)
    limit = max(1, min(int(cfg.get("vk_limit") or 100), 100))
    owner_id, domain = _to_owner_and_domain(group_id_raw)

    state = db.query(VkGroupState).filter(VkGroupState.source_id == source.id).one_or_none()
    if not state:
        state = VkGroupState(source_id=source.id, group_id=group_id_raw)
        db.add(state)
        db.commit()
    else:
        state.group_id = group_id_raw
        db.commit()

    params: dict[str, Any] = {
        "access_token": token,
        "v": settings.vk_api_version,
        "count": limit,
        "filter": "owner",
    }
    if owner_id:
        params["owner_id"] = owner_id
    else:
        params["domain"] = domain

    state.last_fetch_at = dt.datetime.now(dt.timezone.utc)
    state.fetched_count_last_run = 0
    db.commit()

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(f"{settings.vk_api_base.rstrip('/')}/wall.get", params=params)
        resp.raise_for_status()
        body = resp.json()

    if "error" in body:
        msg = body.get("error", {}).get("error_msg") or str(body.get("error"))
        state.last_error = f"VK API error: {msg}"
        db.commit()
        raise RuntimeError(state.last_error)

    data = body.get("response") or {}
    items = data.get("items") or []
    if not isinstance(items, list):
        items = []

    inserted = 0
    fetched = 0
    max_post_id = state.last_post_id or 0

    # VK returns newest first; process oldest->newest for stable state.
    sorted_items = sorted((it for it in items if isinstance(it, dict)), key=lambda x: int(x.get("id") or 0))
    for post in sorted_items:
        post_id = int(post.get("id") or 0)
        if post_id <= 0:
            continue
        if state.last_post_id and post_id <= state.last_post_id:
            continue

        fetched += 1
        max_post_id = max(max_post_id, post_id)

        text = str(post.get("text") or "").strip()
        if not text and isinstance(post.get("copy_history"), list) and post["copy_history"]:
            text = str((post["copy_history"][0] or {}).get("text") or "").strip()
        if not text:
            continue

        owner = int(post.get("owner_id") or 0)
        url = f"https://vk.com/wall{owner}_{post_id}"
        canonical = canonicalize_url(url)
        norm_text = normalize_text(text)
        title = norm_text[:120] if norm_text else None
        ts = int(post.get("date") or 0)
        published_at = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc) if ts else None

        search_text = " ".join([url, title or "", norm_text])
        if not should_keep_news_item(db, search_text, source.settings_json):
            continue

        norm_hash = sha256_hex(norm_text) if norm_text else None
        sh = simhash64(norm_text) if norm_text else None
        tags = tag_item(
            db,
            text=norm_text,
            title=title,
            match_text=search_text,
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
                url=url,
                canonical_url=canonical,
                title=title,
                author="vk",
                published_at=published_at,
                period_month=period_month_from_dt(published_at, dt.datetime.now(dt.timezone.utc)),
                snippet=norm_text[:300] if norm_text else None,
                content_text=norm_text or None,
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

    state.last_post_id = max_post_id or state.last_post_id
    state.last_success_at = dt.datetime.now(dt.timezone.utc)
    state.last_error = None
    db.commit()
    return {"status": "ok", "fetched": fetched, "inserted": inserted, "last_post_id": state.last_post_id}
