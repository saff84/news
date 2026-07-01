from __future__ import annotations

import datetime as dt
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.domain import NewsItem, ParsingTemplate, Source
from app.parsers.html_template_engine import extract_from_html
from app.parsers.limits import acquire_rate_slot, domain_key
from app.parsers.normalize import canonicalize_url, normalize_text, period_month_from_dt, sha256_hex, simhash64
from app.services.news_filter_config import should_keep_news_item
from app.parsers.robots import can_fetch
from app.parsers.sitemap import SitemapUrl, fetch_sitemap_urls
from app.tagging.rules import tag_item
from app.workers.queue import get_redis


def _fetch_text(url: str) -> str:
    headers = {"User-Agent": "NewsIntParser/0.1"}
    with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def _discover_list_urls(*, base_url: str, template_json: dict, fetch) -> list[str]:
    """
    Minimal list discovery:
      template.list.item_links_css: CSS selector for anchors to articles
      template.list.next_page_css: optional CSS selector for next page anchor
    """
    list_cfg = (template_json or {}).get("list", {}) or {}
    item_css = list_cfg.get("item_links_css") or "a"
    next_css = list_cfg.get("next_page_css")
    max_pages = int(list_cfg.get("max_pages") or 1)

    out: list[str] = []
    url = base_url
    for _ in range(max_pages):
        html = fetch(url)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select(item_css):
            href = a.get("href")
            if not href:
                continue
            out.append(urljoin(url, href))
        if not next_css:
            break
        nxt = soup.select_one(next_css)
        href = nxt.get("href") if nxt else None
        if not href:
            break
        url = urljoin(url, href)
    # de-dup preserve order
    seen = set()
    uniq = []
    for u in out:
        cu = canonicalize_url(u)
        if cu in seen:
            continue
        seen.add(cu)
        uniq.append(u)
    return uniq


def _parse_cursor_dt(v: Any) -> dt.datetime | None:
    if not v:
        return None
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    if isinstance(v, str):
        try:
            x = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None
    return None


def ingest_html(db: Session, *, source: Source) -> dict[str, Any]:
    if not source.base_url:
        raise ValueError("base_url is required")

    redis = get_redis()

    template_json: dict = {}
    if source.parsing_template_id:
        t = db.get(ParsingTemplate, source.parsing_template_id)
        template_json = (t.template_json if t else {}) or {}

    def fetch(url: str) -> str:
        if source.respect_robots_txt:
            d = can_fetch(url, user_agent="NewsIntParser", redis=redis)
            if not d.allowed:
                raise PermissionError(f"Blocked by robots.txt: {url}")
        acquire_rate_slot(
            redis,
            scope=f"source:{source.id}",
            max_per_minute=source.max_requests_per_minute,
            delay_ms=source.delay_ms,
        )
        acquire_rate_slot(
            redis,
            scope=f"domain:{domain_key(url)}",
            max_per_minute=max(30, source.max_requests_per_minute),
            delay_ms=0,
        )
        return _fetch_text(url)

    discovered: list[str] = []
    sitemap_entries: list[SitemapUrl] | None = None
    max_lastmod: dt.datetime | None = None

    if source.source_type.value == "HTML_LIST_DETAIL":
        if not source.parsing_template_id:
            raise ValueError("parsing_template_id is required for HTML_LIST_DETAIL")
        discovered = _discover_list_urls(base_url=source.base_url, template_json=template_json, fetch=fetch)
    elif source.source_type.value == "HTML_DETAIL_ONLY":
        if not source.parsing_template_id:
            raise ValueError("parsing_template_id is required for HTML_DETAIL_ONLY")
        discovered = [source.base_url]
    elif source.source_type.value == "SITEMAP":
        cfg = source.settings_json or {}
        if source.respect_robots_txt:
            d = can_fetch(source.base_url, user_agent="NewsIntParser", redis=redis)
            if not d.allowed:
                raise PermissionError(f"Blocked by robots.txt: {source.base_url}")
        acquire_rate_slot(
            redis,
            scope=f"source:{source.id}",
            max_per_minute=source.max_requests_per_minute,
            delay_ms=source.delay_ms,
        )
        acquire_rate_slot(
            redis,
            scope=f"domain:{domain_key(source.base_url)}",
            max_per_minute=max(30, source.max_requests_per_minute),
            delay_ms=0,
        )
        sitemap_entries = fetch_sitemap_urls(
            source.base_url,
            max_sitemaps=int(cfg.get("sitemap_max_sitemaps") or 20),
            max_urls_total=int(cfg.get("sitemap_max_urls_total") or 5000),
            include_regex=(cfg.get("sitemap_include_regex") or None),
            exclude_regex=(cfg.get("sitemap_exclude_regex") or None),
        )

        cursor = _parse_cursor_dt(cfg.get("sitemap_lastmod_cursor"))
        overlap_h = int(cfg.get("sitemap_cursor_overlap_hours") or 48)
        cutoff = (cursor - dt.timedelta(hours=overlap_h)) if cursor else None

        # Prefer newest first when lastmod exists
        sitemap_entries.sort(key=lambda x: x.lastmod or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc), reverse=True)
        filtered: list[SitemapUrl] = []
        for e in sitemap_entries:
            if cutoff and e.lastmod and e.lastmod <= cutoff:
                continue
            filtered.append(e)

        max_lastmod = None
        for e in filtered:
            if e.lastmod and (max_lastmod is None or e.lastmod > max_lastmod):
                max_lastmod = e.lastmod

        discovered = [e.loc for e in filtered]
    else:
        raise ValueError(f"unsupported html type: {source.source_type}")

    inserted = 0
    fetched = 0
    skipped_robots = 0
    skipped_errors = 0

    max_urls_per_run = int((source.settings_json or {}).get("max_urls_per_run") or 50)
    for url in discovered[:max_urls_per_run]:
        canonical = canonicalize_url(url)
        try:
            html = fetch(url)
            fetched += 1
        except PermissionError:
            skipped_robots += 1
            continue
        except Exception:
            skipped_errors += 1
            continue

        extracted = extract_from_html(url, html, template_json)
        title = extracted.title
        content_text = extracted.body_text
        content_html = extracted.body_html
        published_at = extracted.published_at
        author = extracted.author

        search_text = " ".join([str(url or ""), str(title or ""), str(content_text or "")])
        if not should_keep_news_item(db, search_text, source.settings_json):
            continue

        norm = normalize_text(content_text or "")
        norm_hash = sha256_hex(norm) if norm else None
        sh = simhash64(norm) if norm else None

        tags = tag_item(
            db,
            text=content_text or "",
            title=str(title or ""),
            match_text=search_text,
            source_region_ids=source.region_tags,
            source_competitor_id=source.competitor_id,
            source_developer_id=source.developer_id,
        )

        stmt = pg_insert(NewsItem).values(
            source_id=source.id,
            competitor_id=source.competitor_id,
            developer_id=source.developer_id,
            url=url,
            canonical_url=canonical,
            title=title,
            author=author,
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
        ).on_conflict_do_nothing(index_elements=["canonical_url"])
        res = db.execute(stmt)
        if res.rowcount:
            inserted += 1

    # Update sitemap cursor (best-effort) to reduce re-fetching on subsequent runs.
    if source.source_type.value == "SITEMAP" and max_lastmod:
        cfg = dict(source.settings_json or {})
        cfg["sitemap_lastmod_cursor"] = max_lastmod.isoformat()
        source.settings_json = cfg

    db.commit()
    return {
        "status": "ok",
        "discovered": len(discovered),
        "fetched": fetched,
        "inserted": inserted,
        "skipped_robots": skipped_robots,
        "skipped_errors": skipped_errors,
        "max_urls_per_run": max_urls_per_run,
    }

