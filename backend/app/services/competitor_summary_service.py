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
from app.services.report_section_render import (
    merge_report_section_payloads,
    render_section_inner_html,
    sanitize_section_dict,
    section_dict_to_markdown,
    try_parse_report_section,
)

AI_BUDGET = AI_NEWS_DATA_BUDGET_CHARS
POST_TITLE_CHARS = 200
DEFAULT_SNIPPET_CHARS = 900

# Всегда дописывается к промпту из настроек — нельзя переопределить через UI.
_PROMPT_PRODUCT_GUARD = """
КРИТИЧНО — сохранность продуктового контента:
- ЗАПРЕЩЕНО опускать, обобщать до потери смысла или «фильтровать как второстепенное» новинки ассортимента, новые лоты, очереди/корпуса, планировки, метражи, цены, старт продаж и акции.
- Если такие факты есть во входных «Данные», каждый из них должен быть явно отражён в bullets/subsections с датой или ссылкой на пост.
- Не сокращай саммари за счёт продуктовых анонсов ради «общей картины» — продукт и ассортимент приоритетны наравне с PR и финансами."""

_PROMPT_BATCH_EXTRACT = """
Режим: промежуточная выжимка части архива (не финальный отчёт для руководства).
- Сгруппируй факты по темам (продукт, маркетинг, компания, риски), а не по датам.
- НЕ делай хронологический перечень «DD.MM — событие».
- Сохрани все продуктовые анонсы и артикулы из данных.
JSON: subsections с title, paragraphs (кратко) и bullets с citations."""

_PROMPT_SYNTHESIS = """Ты — стратегический аналитик конкурентной среды в девелопменте и строительной отрасли.
На входе — черновая выжимка по постам Telegram-канала одного конкурента за длительный период.
Переработай её в развёрнутую аналитическую справку для руководства.

ЗАПРЕЩЕНО:
- хронологический журнал событий («17.08 — X, 24.08 — Y»);
- структура «по периодам» или «часть 1 / часть 2» — объедини в единый тематический отчёт;
- однострочные bullets без аналитики — каждый раздел начинается с абзаца-интерпретации;
- выбрасывать новинки ассортимента и продуктовые анонсы из черновика.

ОБЯЗАТЕЛЬНО:
1) lead — 4–6 предложений: стратегическая картина периода, чем конкурент отличается, куда движется.
2) subsections — только темы, где есть факты (рекомендуемые title):
   • «Продукт и ассортимент» — все новинки, артикулы, расширения линейки; сгруппируй по направлениям, не теряя конкретику;
   • «Маркетинг и продажи» — акции, цены, каналы, мероприятия, коммуникации;
   • «Развитие компании» — география, склады, партнёрства, кадры, стратегические шаги;
   • «Репутация и риски» — если есть;
   • «Динамика и тренды» — что изменилось во времени, устойчивые паттерны.
   В каждом разделе: paragraphs (2–4 предложения анализа) + bullets (ключевые факты с [ссылками](URL) из черновика).
3) closing — главный вывод за период + 2–3 пункта «что мониторить дальше».
4) Сигнал для нас: нейтрально / давление / возможность — одним абзацем в closing или отдельным bullet.

Ограничения: только факты из черновика; не выдумывай; русский, деловой стиль.
JSON: headline, lead, subsections[{title, paragraphs, bullets}], closing."""


def _post_date_range(batch: list[CompetitorTelegramPost]) -> tuple[str, str]:
    dates = [p.published_at for p in batch if p.published_at]
    if not dates:
        return "—", "—"
    return min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")


def _batch_header_lines(
    *,
    batch_index: int,
    batch_total: int,
    batch: list[CompetitorTelegramPost],
    total_posts: int,
) -> list[str]:
    d0, d1 = _post_date_range(batch)
    return [
        f"Часть {batch_index} из {batch_total}. Постов в части: {len(batch)}. Период части: {d0} — {d1}.",
        f"Всего постов в архиве: {total_posts}.",
        "Обязательно отрази запуски проектов, новинки ассортимента, планировки, цены и акции — если они есть в этой части.",
        "Не составляй хронологический список по датам — группируй по темам.",
    ]


def _serialize_posts_batch(
    posts: list[CompetitorTelegramPost],
    *,
    subject: str,
    header_lines: list[str] | None = None,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
) -> tuple[str, int]:
    lines: list[str] = list(header_lines or [])
    truncated = 0
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
        raw = (p.text or "Пост").strip()
        title = raw[:POST_TITLE_CHARS].replace("\n", " ").strip()
        if len(raw) > POST_TITLE_CHARS:
            title = title.rstrip() + "…"
        url = (p.post_url or "").strip()
        link = f"[{title}]({url})" if url else title
        lines.append(f"- {pub} | {link}")
        if raw and len(raw) > POST_TITLE_CHARS:
            if snippet_chars > 0:
                if len(raw) > snippet_chars:
                    truncated += 1
                body = raw[:snippet_chars] + ("…" if len(raw) > snippet_chars else "")
            else:
                body = raw
            lines.append(f"  {body.replace(chr(10), ' ')}")
    return "\n".join(lines) if lines else "(нет постов)", truncated


def _split_posts_for_ai(
    posts: list[CompetitorTelegramPost],
    max_chars: int,
    *,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
) -> list[list[CompetitorTelegramPost]]:
    if not posts:
        return []
    sorted_posts = sorted(
        posts,
        key=lambda p: p.published_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=False,
    )
    header_reserve = 420
    batches: list[list[CompetitorTelegramPost]] = []
    current: list[CompetitorTelegramPost] = []
    for post in sorted_posts:
        trial = current + [post]
        text, _ = _serialize_posts_batch(trial, subject="", snippet_chars=snippet_chars)
        if len(text) + header_reserve > max_chars and current:
            batches.append(current)
            current = [post]
            continue
        if len(text) + header_reserve > max_chars:
            compact, _ = _serialize_posts_batch([post], subject="", snippet_chars=0)
            if len(compact) + header_reserve > max_chars and current:
                batches.append(current)
                current = [post]
            else:
                current = [post]
            continue
        current = trial
    if current:
        batches.append(current)
    return batches if batches else [sorted_posts]


def _draft_for_synthesis(batch_results: list[tuple[str, dict[str, Any]]]) -> str:
    """Плоский черновик без хронологических подразделов — вход для финального синтеза."""
    payloads = [sanitize_section_dict(p) for _, p in batch_results if isinstance(p, dict) and p]
    if not payloads:
        return ""
    if len(payloads) == 1:
        return section_dict_to_markdown(payloads[0])

    merged = merge_report_section_payloads(payloads)
    extra_bullets: list[dict[str, Any]] = []
    extra_paragraphs: list[str] = []
    for payload in payloads:
        for sub in payload.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            extra_paragraphs.extend(str(p).strip() for p in (sub.get("paragraphs") or []) if str(p).strip())
            for b in sub.get("bullets") or []:
                if isinstance(b, dict) and str(b.get("text") or "").strip():
                    extra_bullets.append(b)
        extra_paragraphs.extend(str(p).strip() for p in (payload.get("paragraphs") or []) if str(p).strip())
        for b in payload.get("bullets") or []:
            if isinstance(b, dict) and str(b.get("text") or "").strip():
                extra_bullets.append(b)

    seen: set[str] = set()
    for b in merged.get("bullets") or []:
        if isinstance(b, dict):
            key = str(b.get("text") or "").lower()[:160]
            seen.add(key)
    for b in extra_bullets:
        key = str(b.get("text") or "").lower()[:160]
        if key and key not in seen:
            seen.add(key)
            merged.setdefault("bullets", []).append(b)

    for p in extra_paragraphs:
        if p not in (merged.get("paragraphs") or []):
            merged.setdefault("paragraphs", []).append(p)

    return section_dict_to_markdown(merged)


def _merge_batch_drafts(batch_results: list[tuple[str, dict[str, Any]]]) -> str:
    """Alias для совместимости."""
    return _draft_for_synthesis(batch_results)


def _merge_competitor_tg_batch_payloads(
    batch_results: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Объединить JSON-саммари по хронологическим частям архива."""
    clean_pairs = [
        (label, sanitize_section_dict(payload))
        for label, payload in batch_results
        if isinstance(payload, dict) and payload
    ]
    if not clean_pairs:
        return {}
    if len(clean_pairs) == 1:
        return clean_pairs[0][1]

    payloads_only = [p for _, p in clean_pairs]
    merged_flat = merge_report_section_payloads(payloads_only)

    subsections: list[dict[str, Any]] = []
    for label, payload in clean_pairs:
        bullets = list(payload.get("bullets") or [])
        paragraphs = list(payload.get("paragraphs") or [])
        for sub in payload.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sub_bullets = list(sub.get("bullets") or [])
            sub_paragraphs = list(sub.get("paragraphs") or [])
            if sub_bullets or sub_paragraphs:
                sub_title = str(sub.get("title") or label).strip() or label
                subsections.append(
                    {"title": sub_title, "paragraphs": sub_paragraphs, "bullets": sub_bullets}
                )
        if bullets or paragraphs:
            subsections.append({"title": label, "paragraphs": paragraphs, "bullets": bullets})

    first = clean_pairs[0][1]
    last = clean_pairs[-1][1]
    out: dict[str, Any] = {
        "headline": merged_flat.get("headline") or first.get("headline"),
        "lead": merged_flat.get("lead") or first.get("lead"),
        "closing": merged_flat.get("closing") or last.get("closing"),
    }
    if subsections:
        out["subsections"] = subsections
        out["paragraphs"] = []
        out["bullets"] = []
    else:
        out["paragraphs"] = merged_flat.get("paragraphs") or []
        out["bullets"] = merged_flat.get("bullets") or []
    return out


def _summary_html(
    *,
    competitor_name: str,
    channel: str,
    period_from: dt.date | None,
    period_to: dt.date | None,
    posts_count: int,
    inner_html: str,
    meta_note: str | None = None,
) -> str:
    pf = period_from.strftime("%d.%m.%Y") if period_from else "—"
    pt = period_to.strftime("%d.%m.%Y") if period_to else "—"
    generated = dt.datetime.now(dt.timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    meta_extra = f"<br/>{escape(meta_note)}" if meta_note else ""
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
Постов в анализе: {posts_count}{meta_extra}<br/>
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
    prompt_base = (ai_cfg.get("prompt_competitor_tg") or ai_cfg.get("prompt_competitors") or "").strip()
    if not prompt_base:
        raise ValueError("Промпт prompt_competitor_tg не настроен в «Подключение ИИ»")
    prompt = f"{prompt_base.rstrip()}\n{_PROMPT_PRODUCT_GUARD}"
    if not runtime.api_key:
        raise ValueError("API-ключ ИИ не настроен")

    cname = competitor.name or str(competitor.id)
    batches = _split_posts_for_ai(posts, AI_BUDGET, snippet_chars=DEFAULT_SNIPPET_CHARS)
    batch_results: list[tuple[str, dict[str, Any]]] = []
    fallback_texts: list[str] = []
    total_truncated = 0
    chars_sent = 0
    multi_batch = len(batches) > 1

    for bi, batch in enumerate(batches, 1):
        header = (
            _batch_header_lines(
                batch_index=bi,
                batch_total=len(batches),
                batch=batch,
                total_posts=len(posts),
            )
            if multi_batch
            else None
        )
        data, truncated = _serialize_posts_batch(batch, subject=cname, header_lines=header)
        total_truncated += truncated
        if len(data) > AI_BUDGET:
            data = data[: AI_BUDGET - 40] + "\n\n[... обрезано по лимиту контекста ...]"
        chars_sent += len(data)

        batch_prompt = prompt
        if multi_batch:
            batch_prompt = f"{prompt.rstrip()}\n{_PROMPT_BATCH_EXTRACT}"

        pause_before_ai_call(runtime.request_delay_seconds, label=f"competitor-tg:{cname}:{bi}")
        text, payload = _process_ai_report_section(
            provider=runtime.provider,
            api_key=runtime.api_key,
            model=runtime.model,
            prompt=batch_prompt,
            data=data,
            log_label=f"competitor-tg:{cname}:{bi}",
            max_retries=runtime.max_retries,
            retry_base_seconds=runtime.retry_base_seconds,
        )
        if payload is None and text and not str(text).startswith("[Ошибка ИИ"):
            payload = try_parse_report_section(text)
        if payload:
            d0, d1 = _post_date_range(batch)
            label = f"{d0} — {d1}" if multi_batch else (payload.get("headline") or cname)
            batch_results.append((str(label), payload))
        if text:
            fallback_texts.append(text)

    period_from = None
    period_to = None
    dates = [p.published_at.date() for p in posts if p.published_at]
    if dates:
        period_from = min(dates)
        period_to = max(dates)

    pf = period_from.strftime("%d.%m.%Y") if period_from else "—"
    pt = period_to.strftime("%d.%m.%Y") if period_to else "—"
    synthesis_pass = False
    synthesis_failed = False

    if batch_results:
        draft_text = _draft_for_synthesis(batch_results)
        synthesis_data = (
            f"Конкурент: «{cname}»\n"
            f"Период: {pf} — {pt}\n"
            f"Постов в архиве: {len(posts)}\n\n"
            f"--- Черновая выжимка ---\n\n{draft_text}"
        )
        chars_sent += len(synthesis_data)
        synthesis_prompt = f"{_PROMPT_SYNTHESIS.rstrip()}\n{_PROMPT_PRODUCT_GUARD}"
        pause_before_ai_call(runtime.request_delay_seconds, label=f"competitor-tg:{cname}:synthesis")
        synth_text, synth_payload = _process_ai_report_section(
            provider=runtime.provider,
            api_key=runtime.api_key,
            model=runtime.model,
            prompt=synthesis_prompt,
            data=synthesis_data,
            log_label=f"competitor-tg:{cname}:synthesis",
            max_retries=runtime.max_retries,
            retry_base_seconds=runtime.retry_base_seconds,
        )
        if synth_payload is None and synth_text and not str(synth_text).startswith("[Ошибка ИИ"):
            synth_payload = try_parse_report_section(synth_text)
        if synth_payload:
            combined_json = synth_payload
            combined_text = section_dict_to_markdown(synth_payload)
            synthesis_pass = True
        elif synth_text and not str(synth_text).startswith("[Ошибка ИИ") and str(synth_text).strip():
            combined_text = str(synth_text).strip()
            combined_json = try_parse_report_section(combined_text) or {}
            synthesis_pass = bool(combined_json)
            synthesis_failed = not synthesis_pass
        else:
            synthesis_failed = True
            combined_json = _merge_competitor_tg_batch_payloads(batch_results)
            combined_text = section_dict_to_markdown(combined_json) if combined_json else "\n\n".join(fallback_texts)
    else:
        combined_json = {}
        combined_text = "\n\n".join(t for t in fallback_texts if t)

    inner = render_section_inner_html(text=combined_text, payload=combined_json or None)
    if not inner:
        inner = f"<div class='summary rich'><p>{escape(combined_text or 'Пустой ответ ИИ')}</p></div>"

    meta_parts: list[str] = []
    if len(batches) > 1:
        meta_parts.append(f"Частей для ИИ: {len(batches)}")
    if synthesis_pass:
        meta_parts.append("Финальный аналитический синтез")
    elif synthesis_failed:
        meta_parts.append("Синтез не удался — показан черновик по частям")
    if total_truncated:
        meta_parts.append(f"Постов с усечённым текстом: {total_truncated} (до {DEFAULT_SNIPPET_CHARS} симв.)")
    meta_note = ". ".join(meta_parts) if meta_parts else None

    html = _summary_html(
        competitor_name=cname,
        channel=profile.tg_channel_username,
        period_from=period_from,
        period_to=period_to,
        posts_count=len(posts),
        inner_html=inner,
        meta_note=meta_note,
    )
    filename = f"{profile.id}.html"
    path = _storage_dir() / filename
    path.write_text(html, encoding="utf-8")
    html_url = f"/competitor-summaries/{filename}"

    summary_payload = dict(combined_json or {})
    summary_payload["_meta"] = {
        "posts_count": len(posts),
        "batches_count": len(batches),
        "posts_text_truncated": total_truncated,
        "snippet_chars": DEFAULT_SNIPPET_CHARS,
        "chars_sent_to_ai": chars_sent,
        "synthesis_pass": synthesis_pass,
        "synthesis_failed": synthesis_failed,
    }

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
    summary.summary_json = summary_payload
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
