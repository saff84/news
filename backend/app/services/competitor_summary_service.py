"""AI-саммари и HTML-страница по постам TG-канала конкурента."""

from __future__ import annotations

import datetime as dt
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.domain import Competitor, CompetitorTelegramPost, CompetitorTelegramProfile, CompetitorTelegramSummary
from app.services.ai_config import get_ai_config
from app.services.ai_runtime import pause_before_ai_call, runtime_from_config
from app.services.report_generator import AI_NEWS_DATA_BUDGET_CHARS, _process_ai_report_section
from app.services.report_section_render import render_section_inner_html

AI_BUDGET = AI_NEWS_DATA_BUDGET_CHARS


def _serialize_posts_batch(posts: list[CompetitorTelegramPost], *, subject: str, header_lines: list[str] | None = None) -> str:
    lines: list[str] = list(header_lines or [])
    if subject:
        if lines:
            lines.append("")
        lines.extend(
            [
                f"Конкурент: «{subject}». Саммари только по постам этого конкурента из его Telegram-канала.",
                "Не включай новости про других участников рынка.",
                "",
            ]
        )
    for p in posts:
        pub = p.published_at.strftime("%Y-%m-%d") if p.published_at else "—"
        title = ((p.text or "Пост")[:120]).replace("\n", " ").strip()
        url = (p.post_url or "").strip()
        link = f"[{title}]({url})" if url else title
        lines.append(f"- {pub} | {link}")
        if p.text and len(p.text) > 120:
            sn = p.text[:400] + ("…" if len(p.text) > 400 else "")
            lines.append(f"  {sn.replace(chr(10), ' ')}")
    return "\n".join(lines) if lines else "(нет постов)"


def _split_posts_for_ai(posts: list[CompetitorTelegramPost], max_chars: int) -> list[list[CompetitorTelegramPost]]:
    if not posts:
        return []
    sorted_posts = sorted(
        posts,
        key=lambda p: p.published_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    batches: list[list[CompetitorTelegramPost]] = []
    current: list[CompetitorTelegramPost] = []
    header_reserve = 280
    for post in sorted_posts:
        trial = current + [post]
        text = _serialize_posts_batch(trial, subject="")
        if len(text) + header_reserve > max_chars and current:
            batches.append(current)
            current = [post]
        else:
            current = trial
    if current:
        batches.append(current)
    return batches if batches else [sorted_posts]


def _summary_html(
    *,
    competitor_name: str,
    channel: str,
    period_from: dt.date | None,
    period_to: dt.date | None,
    posts_count: int,
    inner_html: str,
) -> str:
    pf = period_from.strftime("%d.%m.%Y") if period_from else "—"
    pt = period_to.strftime("%d.%m.%Y") if period_to else "—"
    generated = dt.datetime.now(dt.timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(competitor_name)} — TG-саммари</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #f1f5f9; color: #0f172a; }}
.wrap {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.25rem; }}
header {{ margin-bottom: 1.5rem; }}
h1 {{ font-size: 1.75rem; margin: 0 0 0.5rem; }}
.meta {{ color: #64748b; font-size: 0.95rem; line-height: 1.5; }}
.card {{ background: #fff; border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
.summary.rich p {{ line-height: 1.6; }}
.summary.rich ul {{ padding-left: 1.25rem; }}
.summary.rich a {{ color: #2563eb; }}
.sec-closing {{ color: #475569; margin-top: 1rem; }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>{escape(competitor_name)}</h1>
<p class="meta">Telegram: @{escape(channel)}<br/>
Период: {pf} — {pt}<br/>
Постов в анализе: {posts_count}<br/>
Сгенерировано: {generated}</p>
</header>
<section class="card">{inner_html}</section>
</div>
</body>
</html>"""


def _storage_dir() -> Path:
    d = Path(settings.storage_dir) / "competitor_summaries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_competitor_summary(db: Session, profile: CompetitorTelegramProfile) -> CompetitorTelegramSummary:
    competitor = db.get(Competitor, profile.competitor_id)
    if not competitor:
        raise ValueError("Competitor not found")

    posts = (
        db.query(CompetitorTelegramPost)
        .filter(CompetitorTelegramPost.profile_id == profile.id)
        .order_by(CompetitorTelegramPost.published_at.asc().nullslast())
        .all()
    )
    if not posts:
        raise ValueError("Нет спарсенных постов для саммари")

    ai_cfg = get_ai_config(db)
    runtime = runtime_from_config(ai_cfg)
    prompt = (ai_cfg.get("prompt_competitor_tg") or ai_cfg.get("prompt_competitors") or "").strip()
    if not prompt:
        raise ValueError("Промпт prompt_competitor_tg не настроен в «Подключение ИИ»")
    if not runtime.api_key:
        raise ValueError("API-ключ ИИ не настроен")

    cname = competitor.name or str(competitor.id)
    batches = _split_posts_for_ai(posts, AI_BUDGET)
    combined_text = ""
    combined_json: dict[str, Any] | None = None

    for bi, batch in enumerate(batches, 1):
        header = []
        if len(batches) > 1:
            header = [f"Часть {bi} из {len(batches)}. Постов в части: {len(batch)}."]
        data = _serialize_posts_batch(batch, subject=cname, header_lines=header)
        pause_before_ai_call(runtime.request_delay_seconds, label=f"competitor-tg:{cname}:{bi}")
        text, payload = _process_ai_report_section(
            provider=runtime.provider,
            api_key=runtime.api_key,
            model=runtime.model,
            prompt=prompt,
            data=data,
            log_label=f"competitor-tg:{cname}:{bi}",
            max_retries=runtime.max_retries,
            retry_base_seconds=runtime.retry_base_seconds,
        )
        if len(batches) == 1:
            combined_text = text
            combined_json = payload
        elif payload:
            if combined_json is None:
                combined_json = payload
            else:
                for key in ("bullets", "paragraphs", "subsections"):
                    if payload.get(key):
                        combined_json.setdefault(key, [])
                        combined_json[key].extend(payload[key])

    period_from = None
    period_to = None
    dates = [p.published_at.date() for p in posts if p.published_at]
    if dates:
        period_from = min(dates)
        period_to = max(dates)

    inner = render_section_inner_html(text=combined_text, payload=combined_json)
    if not inner:
        inner = f"<div class='summary rich'><p>{escape(combined_text or 'Пустой ответ ИИ')}</p></div>"

    html = _summary_html(
        competitor_name=cname,
        channel=profile.tg_channel_username,
        period_from=period_from,
        period_to=period_to,
        posts_count=len(posts),
        inner_html=inner,
    )
    filename = f"{profile.id}.html"
    path = _storage_dir() / filename
    path.write_text(html, encoding="utf-8")
    html_url = f"/competitor-summaries/{filename}"

    summary = (
        db.query(CompetitorTelegramSummary)
        .filter(CompetitorTelegramSummary.profile_id == profile.id, CompetitorTelegramSummary.status != "approved")
        .order_by(CompetitorTelegramSummary.created_at.desc())
        .first()
    )
    if not summary:
        summary = CompetitorTelegramSummary(profile_id=profile.id)
        db.add(summary)

    summary.status = "ready"
    summary.summary_text = combined_text
    summary.summary_json = combined_json or {}
    summary.posts_count = len(posts)
    summary.period_from = period_from
    summary.period_to = period_to
    summary.html_path = html_url
    db.commit()
    db.refresh(summary)
    return summary


def purge_competitor_posts(db: Session, profile: CompetitorTelegramProfile) -> dict[str, Any]:
    """Удалить спарсенные посты после одобрения саммари."""
    deleted = (
        db.query(CompetitorTelegramPost)
        .filter(CompetitorTelegramPost.profile_id == profile.id)
        .delete(synchronize_session=False)
    )
    profile.last_message_id = 0
    profile.backfill_complete = False
    profile.backfill_cursor_date = None
    db.commit()
    return {"deleted_posts": deleted}
