"""Report data collection and AI processing for PDF generation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.domain import (
    Competitor,
    Developer,
    IndicatorDaily,
    IndicatorSeries,
    NewsItem,
    NewsItemCluster,
    ParsedIndicator,
    Region,
)
from app.schemas.report_sections import REPORT_SECTION_JSON_INSTRUCTION
from app.services.ai_client import AIValidationError, call_provider
from app.services.ai_config import get_ai_config
from app.services.ai_runtime import (
    AIProcessingStats,
    pause_before_ai_call,
    runtime_from_config,
)
from app.services.report_config import get_report_config
from app.services.report_section_render import parse_report_section_json, section_dict_to_markdown


_AI_LINK_INSTRUCTION = (
    "\n\nИнструкция по ответу: при ссылке на конкретную публикацию используй Markdown "
    "[краткий текст](URL) ровно с тем URL, который указан во входных данных. Не выдумывай ссылки."
)


def _serialize_news_for_ai(items: list, *, competitor_names: dict[str, str] | None = None) -> str:
    """Вход для ИИ: дата, заголовок+URL в Markdown, фрагмент. competitor_names — подписи [конкурент] в строке."""
    lines: list[str] = []
    for n in items:
        pub = n.published_at.strftime("%Y-%m-%d") if n.published_at else "—"
        title = (n.title or "Без заголовка").replace("\n", " ").strip()
        url = (n.url or "").strip()
        prefix = ""
        if competitor_names:
            cid = n.competitor_id
            if cid and str(cid) in competitor_names:
                prefix = f"[{competitor_names[str(cid)]}] "
            elif n.competitor_mentions:
                names = [competitor_names.get(str(m), str(m)) for m in n.competitor_mentions]
                prefix = f"[{', '.join(names)}] " if names else ""
        link = f"[{title}]({url})" if url else title
        lines.append(f"- {prefix}{pub} | {link}")
        if n.snippet:
            sn = n.snippet[:450] + ("…" if len(n.snippet) > 450 else "")
            lines.append(f"  {sn}")
    return "\n".join(lines) if lines else "(нет данных за период)"


def _serialize_indicators(daily: list, parsed: list) -> str:
    """Сериализация индикаторов для ИИ: цифровые данные для аналитики (не для отображения в PDF)."""
    parts = []
    if daily:
        parts.append("Курс CNY/RUB — числовые данные (дата, значение):")
        for r in daily:
            parts.append(f"  {r.period_date},{float(r.value)}")
    if parsed:
        parts.append("Сводные показатели — числовые данные (показатель, период, значение):")
        for r in parsed:
            parts.append(f"  {r.indicator_name},{r.period},{float(r.value)}{r.unit or ''}")
    return "\n".join(parts) if parts else "(нет данных за период)"


def _fetch_clusters_for_report(db: Session, news_ids: frozenset) -> list[NewsItemCluster]:
    """Кластеры, у которых главная новость попала в выборку отчёта."""
    if not news_ids:
        return []
    return (
        db.query(NewsItemCluster)
        .filter(NewsItemCluster.primary_item_id.in_(news_ids))
        .order_by(NewsItemCluster.created_at.desc())
        .limit(120)
        .all()
    )


def _serialize_clusters(db: Session, clusters: list[NewsItemCluster]) -> str:
    """Текст для ИИ: группы похожих новостей."""
    if not clusters:
        return "(нет кластеров за период)"
    all_ids: set = set()
    for cl in clusters:
        all_ids.add(cl.primary_item_id)
        all_ids.update(cl.related_item_ids or [])
    items = {i.id: i for i in db.query(NewsItem).filter(NewsItem.id.in_(all_ids)).all()}
    lines: list[str] = []
    for idx, cl in enumerate(clusters, 1):
        note = f" ({cl.note})" if cl.note else ""
        lines.append(f"### Кластер {idx}{note}, порог simhash: {cl.similarity_threshold}")
        prim = items.get(cl.primary_item_id)
        pub = prim.published_at.strftime("%Y-%m-%d %H:%M") if prim and prim.published_at else "—"
        title = (prim.title or "Без заголовка") if prim else str(cl.primary_item_id)
        purl = (prim.url or "") if prim else ""
        lines.append(f"  Главная: [{pub}] [{title}]({purl})" if purl else f"  Главная: [{pub}] {title}")
        for rid in cl.related_item_ids or []:
            rel = items.get(rid)
            rp = rel.published_at.strftime("%Y-%m-%d %H:%M") if rel and rel.published_at else "—"
            rt = (rel.title or "Без заголовка") if rel else str(rid)
            ru = (rel.url or "") if rel else ""
            lines.append(f"  Похожая: [{rp}] [{rt}]({ru})" if ru else f"  Похожая: [{rp}] {rt}")
        lines.append("")
    return "\n".join(lines).strip()


def _simple_news_summary_linked(items: list, *, title: str) -> str:
    """Fallback без ИИ: краткий список с Markdown-ссылками."""
    if not items:
        return f"{title}: данных за период нет."
    lines = [f"{title}: {len(items)} публикаций.", ""]
    for n in sorted(items, key=lambda x: (x.published_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[:20]:
        t = (n.title or "Без заголовка").replace("\n", " ")
        u = (n.url or "").strip()
        lines.append(f"- [{t}]({u})" if u else f"- {t}")
    return "\n".join(lines)


def _group_competitor_news(news: list, competitors_map: dict[str, str]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for n in news:
        cids = set()
        if n.competitor_id:
            cids.add(n.competitor_id)
        cids.update(n.competitor_mentions or [])
        for cid in cids:
            cname = competitors_map.get(str(cid), str(cid))
            out[cname].append(n)
    return dict(out)


def _group_developer_news(news: list, developers_map: dict[str, str]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for n in news:
        dids = set()
        if n.developer_id:
            dids.add(n.developer_id)
        dids.update(n.developer_mentions or [])
        for did in dids:
            dname = developers_map.get(str(did), str(did))
            out[dname].append(n)
    return dict(out)


def _group_region_news(news: list, region_map: dict[str, str]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for n in news:
        if n.region_ids:
            for rid in n.region_ids:
                out[region_map.get(str(rid), str(rid))].append(n)
        else:
            out["Без региона"].append(n)
    return dict(out)


def fetch_report_data(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    period_month: date | None = None,
    include_news: bool = True,
    include_indicators: bool = True,
    include_regions: bool = True,
) -> dict[str, Any]:
    """Fetch raw data for report period. period_month: строгая фильтрация по месяцу."""
    dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)

    news_items = []
    if include_news:
        q = db.query(NewsItem)
        if period_month is not None:
            q = q.filter(NewsItem.period_month == period_month)
        else:
            q = q.filter(
                and_(
                    NewsItem.published_at >= dt_from,
                    NewsItem.published_at <= dt_to,
                )
            )
        news_items = (
            q.order_by(NewsItem.published_at.desc().nullslast())
            .limit(500)
            .all()
        )

    daily_indicators = []
    parsed_indicators = []
    if include_indicators:
        daily_indicators = (
            db.query(IndicatorDaily)
            .filter(
                IndicatorDaily.series == IndicatorSeries.CNY_RUB,
                IndicatorDaily.period_date >= date_from,
                IndicatorDaily.period_date <= date_to,
            )
            .order_by(IndicatorDaily.period_date.asc())
            .all()
        )
        parsed_indicators = (
            db.query(ParsedIndicator)
            .filter(
                ParsedIndicator.created_at >= dt_from,
                ParsedIndicator.created_at <= dt_to,
            )
            .order_by(ParsedIndicator.indicator_name.asc(), ParsedIndicator.created_at.desc())
            .limit(500)
            .all()
        )

    regions_list = []
    if include_regions:
        regions_list = db.query(Region).filter(Region.is_active.is_(True)).order_by(Region.name).all()

    return {
        "news": news_items,
        "daily_indicators": daily_indicators,
        "parsed_indicators": parsed_indicators,
        "regions": regions_list,
    }


def get_report_data_for_pdf(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    period_month: date | None = None,
    include_news: bool = True,
    include_indicators: bool = True,
    include_regions: bool = True,
) -> dict[str, Any]:
    """
    Fetch raw data for PDF with resolved names (source, region).
    Returns structured data for pdf_builder.
    """
    raw = fetch_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month=period_month,
        include_news=include_news,
        include_indicators=include_indicators,
        include_regions=include_regions,
    )
    news = raw["news"]
    regions_list = raw["regions"]
    region_map = {str(r.id): r.name for r in regions_list}

    # Load sources and competitors for news
    from app.models.domain import Source

    source_ids = {n.source_id for n in news if n.source_id}
    sources_map: dict[str, str] = {}
    if source_ids:
        for s in db.query(Source).filter(Source.id.in_(source_ids)).all():
            sources_map[str(s.id)] = (
                s.name or s.base_url or s.feed_url or (f"@{s.tg_channel_username}" if s.tg_channel_username else str(s.id))
            )

    competitor_ids = set()
    for n in news:
        if n.competitor_id:
            competitor_ids.add(n.competitor_id)
        competitor_ids.update(n.competitor_mentions or [])
    competitors_map: dict[str, str] = {}
    if competitor_ids:
        for c in db.query(Competitor).filter(Competitor.id.in_(competitor_ids)).all():
            competitors_map[str(c.id)] = c.name or str(c.id)

    developer_ids: set = set()
    for n in news:
        if n.developer_id:
            developer_ids.add(n.developer_id)
        developer_ids.update(n.developer_mentions or [])
    developers_map: dict[str, str] = {}
    if developer_ids:
        for d in db.query(Developer).filter(Developer.id.in_(developer_ids)).all():
            developers_map[str(d.id)] = d.name or str(d.id)

    # Новости конкурентов — по компании (новость может быть в нескольких компаниях)
    news_by_competitor: dict[str, list] = {}
    news_by_developer: dict[str, list] = {}
    news_general: list = []
    for n in news:
        has_c = bool(n.competitor_id or (n.competitor_mentions and len(n.competitor_mentions) > 0))
        has_d = bool(n.developer_id or (n.developer_mentions and len(n.developer_mentions) > 0))
        if has_c:
            cids = set()
            if n.competitor_id:
                cids.add(n.competitor_id)
            cids.update(n.competitor_mentions or [])
            for cid in cids:
                cname = competitors_map.get(str(cid), str(cid))
                news_by_competitor.setdefault(cname, []).append(n)
        if has_d:
            dids = set()
            if n.developer_id:
                dids.add(n.developer_id)
            dids.update(n.developer_mentions or [])
            for did in dids:
                dname = developers_map.get(str(did), str(did))
                news_by_developer.setdefault(dname, []).append(n)
        if not has_c and not has_d:
            news_general.append(n)

    # Group news by region
    news_by_region: dict[str, list] = {}
    for r in regions_list:
        news_by_region[r.name] = []
    news_by_region["Без региона"] = []
    for n in news:
        if n.region_ids:
            for rid in n.region_ids:
                rname = region_map.get(str(rid), str(rid))
                if rname not in news_by_region:
                    news_by_region[rname] = []
                news_by_region[rname].append(n)
        else:
            news_by_region["Без региона"].append(n)

    # Group news by channel (source)
    news_by_channel: dict[str, list] = {}
    for n in news:
        ch = sources_map.get(str(n.source_id), "Без источника") if n.source_id else "Без источника"
        if ch not in news_by_channel:
            news_by_channel[ch] = []
        news_by_channel[ch].append(n)

    return {
        "news": news,
        "news_by_competitor": news_by_competitor,
        "news_by_developer": news_by_developer,
        "news_general": news_general,
        "news_by_region": news_by_region,
        "news_by_channel": news_by_channel,
        "daily_indicators": raw["daily_indicators"],
        "parsed_indicators": raw["parsed_indicators"],
        "regions": regions_list,
        "report_config": {},
        "period": {"date_from": str(date_from), "date_to": str(date_to)},
    }


def process_section_with_ai(
    *,
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    data: str,
    max_retries: int = 0,
    retry_base_seconds: float = 5.0,
    log_label: str = "report-section",
) -> str:
    """Process section with AI. Returns processed text or raises AIValidationError."""
    return call_provider(
        provider=provider,
        api_key=api_key,
        model=model,
        prompt=prompt,
        data=data,
        max_retries=max_retries,
        retry_base_seconds=retry_base_seconds,
        log_label=log_label,
    )


def _process_ai_report_section(
    *,
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    data: str,
    link_hint: bool = True,
    max_retries: int = 0,
    retry_base_seconds: float = 5.0,
    log_label: str = "report-section",
) -> tuple[str, dict[str, Any] | None]:
    """
    ИИ с инструкцией вернуть JSON-секцию; при успешном разборе — markdown + dict для HTML/PDF.
    При ошибке парсинга — сырой ответ модели и json=None.
    """
    tail = REPORT_SECTION_JSON_INSTRUCTION
    if link_hint:
        tail = _AI_LINK_INSTRUCTION + tail
    raw = process_section_with_ai(
        provider=provider,
        api_key=api_key,
        model=model,
        prompt=prompt,
        data=data + tail,
        max_retries=max_retries,
        retry_base_seconds=retry_base_seconds,
        log_label=log_label,
    )
    try:
        d = parse_report_section_json(raw)
        md = section_dict_to_markdown(d)
        if md.strip():
            return md, d
        if d.get("headline") or d.get("lead") or d.get("paragraphs") or d.get("bullets") or d.get("closing"):
            return md, d
        return raw, None
    except Exception:
        return raw, None


def _parse_report_month(s: str | None) -> tuple[date, date, date | None] | None:
    """Parse 'YYYY-MM' -> (date_from, date_to, period_month). Returns None if invalid."""
    if not s or len(s) != 7 or s[4] != "-":
        return None
    try:
        y, m = int(s[:4]), int(s[5:7])
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            from calendar import monthrange
            first = date(y, m, 1)
            last = date(y, m, monthrange(y, m)[1])
            return (first, last, first)
    except (ValueError, KeyError):
        pass
    return None


def generate_report(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_range_days: int | None = None,
    report_month: str | None = None,
) -> dict[str, Any]:
    """
    Generate report: fetch data, process with AI per section, return processed data for PDF.
    report_month ("YYYY-MM") — приоритет: строго данные за месяц, без смешения с другими месяцами.
    """
    report_cfg = get_report_config(db)
    period_month_val: date | None = None

    if report_month is None:
        report_month = report_cfg.get("report_month")

    if report_month:
        parsed = _parse_report_month(report_month)
        if parsed:
            date_from, date_to, period_month_val = parsed

    if date_from is None or date_to is None:
        if date_range_days is None:
            date_range_days = report_cfg.get("date_range_days", 30)
        if date_to is None:
            date_to = date.today()
        if date_from is None:
            date_from = date_to - timedelta(days=date_range_days)

    ai_cfg = get_ai_config(db)
    runtime = runtime_from_config(ai_cfg)
    ai_stats = AIProcessingStats()

    raw = fetch_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month=period_month_val,
        include_news=report_cfg.get("include_news", True),
        include_indicators=report_cfg.get("include_indicators", True),
        include_regions=report_cfg.get("include_regions", True),
    )

    result: dict[str, Any] = {
        "report_config": {
            "title": report_cfg.get("title", "Аналитический отчёт"),
            "subtitle": report_cfg.get("subtitle", ""),
            "company_name": report_cfg.get("company_name", ""),
            "company_address": report_cfg.get("company_address", ""),
            "footer_text": report_cfg.get("footer_text", ""),
        },
        "period": {"date_from": str(date_from), "date_to": str(date_to)},
        "processed_news": None,
        "processed_competitors": None,
        "processed_indicators": None,
        "processed_regions": None,
        "processed_clusters": None,
        "processed_news_json": None,
        "processed_indicators_json": None,
        "processed_clusters_json": None,
        "processed_competitors_by_name": {},
        "processed_developers_by_name": {},
        "processed_regions_by_name": {},
        "processed_competitors_by_name_json": {},
        "processed_developers_by_name_json": {},
        "processed_regions_by_name_json": {},
        "processed_raw": raw,
        "ai_stats": {},
    }

    def _run_ai(
        *,
        label: str,
        prompt: str,
        data: str,
        link_hint: bool = True,
    ) -> tuple[str, dict[str, Any] | None]:
        if not runtime.api_key or not prompt.strip():
            return "", None
        pause_before_ai_call(runtime.request_delay_seconds, label=label)
        ai_stats.calls += 1
        try:
            text, payload = _process_ai_report_section(
                provider=runtime.provider,
                api_key=runtime.api_key,
                model=runtime.model,
                prompt=prompt,
                data=data,
                link_hint=link_hint,
                max_retries=runtime.max_retries,
                retry_base_seconds=runtime.retry_base_seconds,
                log_label=label,
            )
            ai_stats.succeeded += 1
            return text, payload
        except AIValidationError as e:
            ai_stats.failed += 1
            ai_stats.labels_failed.append(label)
            return f"[Ошибка ИИ: {e}]", None

    all_news = raw["news"]
    competitor_news = [n for n in all_news if n.competitor_id or (n.competitor_mentions and len(n.competitor_mentions) > 0)]
    developer_news = [n for n in all_news if n.developer_id or (n.developer_mentions and len(n.developer_mentions) > 0)]
    general_news = [
        n
        for n in all_news
        if not (
            n.competitor_id
            or (n.competitor_mentions and len(n.competitor_mentions) > 0)
            or n.developer_id
            or (n.developer_mentions and len(n.developer_mentions) > 0)
        )
    ]

    competitor_names_map: dict[str, str] = {}
    if competitor_news:
        c_ids = set()
        for n in competitor_news:
            if n.competitor_id:
                c_ids.add(n.competitor_id)
            c_ids.update(n.competitor_mentions or [])
        for c in db.query(Competitor).filter(Competitor.id.in_(c_ids)).all():
            competitor_names_map[str(c.id)] = c.name or str(c.id)

    developer_names_map: dict[str, str] = {}
    if developer_news:
        d_ids = set()
        for n in developer_news:
            if n.developer_id:
                d_ids.add(n.developer_id)
            d_ids.update(n.developer_mentions or [])
        for d in db.query(Developer).filter(Developer.id.in_(d_ids)).all():
            developer_names_map[str(d.id)] = d.name or str(d.id)

    region_map: dict[str, str] = {}
    for r in raw.get("regions", []):
        region_map[str(r.id)] = r.name
    competitor_groups = _group_competitor_news(competitor_news, competitor_names_map)
    developer_groups = _group_developer_news(developer_news, developer_names_map)
    region_groups = _group_region_news(all_news, region_map)

    if report_cfg.get("include_news", True) and competitor_news:
        prompt_comp = (ai_cfg.get("prompt_competitors") or "").strip()
        for cname, items in sorted(competitor_groups.items()):
            entity_data = _serialize_news_for_ai(items, competitor_names=competitor_names_map)
            if prompt_comp and runtime.api_key:
                text, payload = _run_ai(
                    label=f"competitor:{cname}",
                    prompt=prompt_comp,
                    data=entity_data,
                )
                result["processed_competitors_by_name"][cname] = text
                if payload is not None:
                    result["processed_competitors_by_name_json"][cname] = payload
            else:
                result["processed_competitors_by_name"][cname] = _simple_news_summary_linked(items, title=f"Конкурент {cname}")

    if report_cfg.get("include_news", True) and developer_news:
        prompt_dev = (ai_cfg.get("prompt_developers") or "").strip() or (ai_cfg.get("prompt_competitors") or "").strip()
        for dname, items in sorted(developer_groups.items()):
            entity_data = _serialize_news_for_ai(items)
            if prompt_dev and runtime.api_key:
                text, payload = _run_ai(
                    label=f"developer:{dname}",
                    prompt=prompt_dev,
                    data=entity_data,
                )
                result["processed_developers_by_name"][dname] = text
                if payload is not None:
                    result["processed_developers_by_name_json"][dname] = payload
            else:
                result["processed_developers_by_name"][dname] = _simple_news_summary_linked(items, title=f"Застройщик {dname}")

    if report_cfg.get("include_news", True) and general_news:
        prompt_news = (ai_cfg.get("prompt_news") or "").strip()
        data_str = _serialize_news_for_ai(general_news)
        if prompt_news and runtime.api_key:
            text, payload = _run_ai(label="news:general", prompt=prompt_news, data=data_str)
            result["processed_news"] = text
            if payload is not None:
                result["processed_news_json"] = payload
        else:
            result["processed_news"] = _simple_news_summary_linked(general_news, title="Общие новости")

    if report_cfg.get("include_indicators", True):
        prompt_ind = (ai_cfg.get("prompt_indicators") or "").strip()
        data_str = _serialize_indicators(raw["daily_indicators"], raw["parsed_indicators"])
        if prompt_ind and runtime.api_key:
            text, payload = _run_ai(
                label="indicators",
                prompt=prompt_ind,
                data=data_str,
                link_hint=False,
            )
            result["processed_indicators"] = text
            if payload is not None:
                result["processed_indicators_json"] = payload
        else:
            result["processed_indicators"] = data_str

    if report_cfg.get("include_regions", True):
        prompt_reg = (ai_cfg.get("prompt_regions") or "").strip()
        for rname, items in sorted(region_groups.items()):
            if not items:
                continue
            entity_data = _serialize_news_for_ai(items)
            if prompt_reg and runtime.api_key:
                text, payload = _run_ai(
                    label=f"region:{rname}",
                    prompt=prompt_reg,
                    data=entity_data,
                )
                result["processed_regions_by_name"][rname] = text
                if payload is not None:
                    result["processed_regions_by_name_json"][rname] = payload
            else:
                result["processed_regions_by_name"][rname] = _simple_news_summary_linked(items, title=f"Регион {rname}")

    # Кластеры похожих новостей (главная новость входит в выборку отчёта)
    if report_cfg.get("include_news", True) and all_news:
        news_id_set = frozenset(n.id for n in all_news)
        clusters_list = _fetch_clusters_for_report(db, news_id_set)
        if clusters_list:
            prompt_cl = (ai_cfg.get("prompt_clusters") or "").strip()
            data_str = _serialize_clusters(db, clusters_list)
            if prompt_cl and runtime.api_key:
                text, payload = _run_ai(label="clusters", prompt=prompt_cl, data=data_str)
                result["processed_clusters"] = text
                if payload is not None:
                    result["processed_clusters_json"] = payload
            else:
                result["processed_clusters"] = data_str

    result["ai_stats"] = {
        **ai_stats.to_dict(),
        "request_delay_seconds": runtime.request_delay_seconds,
        "max_retries": runtime.max_retries,
    }

    # Remove raw from payload for response (optional)
    if "processed_raw" in result:
        del result["processed_raw"]

    return result
