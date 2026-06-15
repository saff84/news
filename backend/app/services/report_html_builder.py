"""Build modern HTML report with interactive charts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from typing import Any

from app.services.period_sort import period_sort_key
from app.services.report_markup import markdown_links_to_html
from app.services.indicator_telegram_report import indicator_telegram_sections_to_html
from app.services.report_section_render import render_section_inner_html, section_dict_to_html_fragment


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _cards_for_summaries(entries: dict[str, str] | None) -> str:
    if not entries:
        return ""
    parts: list[str] = []
    for name, text in sorted(entries.items()):
        if not (text or "").strip():
            continue
        parts.append(
            f"<section class='card'><h3>{escape(name)}</h3>"
            f"<div class='summary rich'>{markdown_links_to_html(text)}</div></section>"
        )
    if not parts:
        return ""
    return f"<div class='two'>{''.join(parts)}</div>"


def _cards_for_summaries_mixed(
    entries: dict[str, str] | None,
    json_entries: dict[str, Any] | None,
) -> str:
    keys = sorted(set((entries or {}).keys()) | set((json_entries or {}).keys()))
    parts: list[str] = []
    for name in keys:
        text = (entries or {}).get(name) or ""
        raw_j = (json_entries or {}).get(name)
        pl = raw_j if isinstance(raw_j, dict) else None
        inner = render_section_inner_html(text=text, payload=pl)
        if not inner:
            continue
        parts.append(f"<section class='card'><h3>{escape(name)}</h3>{inner}</section>")
    if not parts:
        return ""
    return f"<div class='two'>{''.join(parts)}</div>"


def _section_rich(title: str, text: str | None, payload: dict[str, Any] | None) -> str:
    inner = render_section_inner_html(text=text, payload=payload if isinstance(payload, dict) else None)
    if not inner:
        return ""
    return f'<section class="card"><h3>{escape(title)}</h3>{inner}</section>'


def build_report_html(
    *,
    report_config: dict,
    period: dict,
    news: list,
    news_by_region: dict[str, list],
    news_by_channel: dict[str, list],
    news_by_competitor: dict[str, list] | None = None,
    news_by_developer: dict[str, list] | None = None,
    news_general: list | None = None,
    daily_indicators: list,
    parsed_indicators: list,
    regions: list,
    processed_indicators: str | None = None,
    processed_news: str | None = None,
    processed_competitors: str | None = None,
    processed_regions: str | None = None,
    processed_clusters: str | None = None,
    processed_news_json: dict[str, Any] | None = None,
    processed_indicators_json: dict[str, Any] | None = None,
    processed_clusters_json: dict[str, Any] | None = None,
    processed_competitors_by_name: dict[str, str] | None = None,
    processed_developers_by_name: dict[str, str] | None = None,
    processed_regions_by_name: dict[str, str] | None = None,
    processed_competitors_by_name_json: dict[str, Any] | None = None,
    processed_developers_by_name_json: dict[str, Any] | None = None,
    processed_regions_by_name_json: dict[str, Any] | None = None,
    indicator_telegram_sections: list[dict[str, Any]] | None = None,
    **_: Any,
) -> str:
    cfg = report_config or {}
    date_from = escape(period.get("date_from", ""))
    date_to = escape(period.get("date_to", ""))
    title = escape(cfg.get("title", "Аналитический отчёт"))
    subtitle = escape(cfg.get("subtitle", ""))
    company = escape(cfg.get("company_name", ""))
    address = escape(cfg.get("company_address", ""))
    footer = escape(cfg.get("footer_text", ""))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cny_x = [str(r.period_date) for r in daily_indicators]
    cny_y = [float(r.value) for r in daily_indicators]

    parsed_by_name: dict[str, dict[str, list]] = {}
    for r in parsed_indicators or []:
        name = str(r.indicator_name)
        if name not in parsed_by_name:
            parsed_by_name[name] = {"x": [], "y": []}
        parsed_by_name[name]["x"].append(str(r.period))
        parsed_by_name[name]["y"].append(float(r.value))

    # Графики: слева старые даты, справа самые свежие
    for series in parsed_by_name.values():
        pairs = sorted(zip(series["x"], series["y"]), key=lambda p: period_sort_key(p[0]))
        if pairs:
            series["x"] = [p[0] for p in pairs]
            series["y"] = [p[1] for p in pairs]

    dev_cards = _cards_for_summaries_mixed(processed_developers_by_name, processed_developers_by_name_json)
    comp_cards = _cards_for_summaries_mixed(processed_competitors_by_name, processed_competitors_by_name_json)
    region_cards = _cards_for_summaries_mixed(processed_regions_by_name, processed_regions_by_name_json)

    nbd = news_by_developer or {}
    nbc = news_by_competitor or {}
    nbr = news_by_region or {}
    has_dev_news = any(len(v) > 0 for v in nbd.values())
    has_comp_news = any(len(v) > 0 for v in nbc.values())
    has_reg_news = any(len(v) > 0 for v in nbr.values())

    if dev_cards:
        dev_section = f'<section class="card"><h2>Застройщики</h2>{dev_cards}</section>'
    elif has_dev_news:
        dev_section = (
            '<section class="card"><h2>Застройщики</h2>'
            '<p class="muted">Саммари не сформировано (задайте промпт застройщиков и API-ключ ИИ).</p></section>'
        )
    else:
        dev_section = ""

    if comp_cards:
        comp_section = f'<section class="card"><h2>Конкуренты</h2>{comp_cards}</section>'
    elif has_comp_news:
        comp_section = (
            '<section class="card"><h2>Конкуренты</h2>'
            '<p class="muted">Саммари не сформировано (промпт конкурентов и API-ключ ИИ).</p></section>'
        )
    else:
        comp_section = ""

    if region_cards:
        region_section = f'<section class="card"><h2>Регионы</h2>{region_cards}</section>'
    elif has_reg_news:
        region_section = (
            '<section class="card"><h2>Регионы</h2>'
            '<p class="muted">Саммари не сформировано (промпт регионов и API-ключ ИИ).</p></section>'
        )
    else:
        region_section = ""

    ind_html = ""
    if isinstance(processed_indicators_json, dict):
        ind_frag = section_dict_to_html_fragment(processed_indicators_json).strip()
        if ind_frag:
            ind_html = f'<div class="summary rich structured">{ind_frag}</div>'
    if not ind_html and processed_indicators:
        ind_html = f'<div class="summary rich">{markdown_links_to_html(processed_indicators)}</div>'

    tg_indicators_html = indicator_telegram_sections_to_html(indicator_telegram_sections)

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    .hdr {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 20px; margin-bottom: 16px; }}
    .muted {{ color: #64748b; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 14px; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px; }}
    .card h2 {{ margin: 0 0 12px 0; font-size: 20px; }}
    .card h3 {{ margin: 0 0 10px 0; font-size: 18px; }}
    .summary {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; font-size: 14px; color: #0f172a; line-height: 1.5; }}
    .summary.rich {{ white-space: normal; }}
    .summary.rich a {{ color: #2563eb; text-decoration: underline; }}
    .summary.structured .sec-headline {{ margin: 0 0 8px 0; font-size: 16px; }}
    .summary.structured .sec-subtheme {{ margin: 18px 0 8px 0; font-size: 15px; font-weight: 600; color: #334155; }}
    .summary.structured .sec-subtheme-body {{ margin-bottom: 4px; }}
    .summary.structured .sec-bullets {{ margin: 8px 0; padding-left: 1.2em; }}
    .summary.structured .sec-lead, .summary.structured .sec-closing {{ margin: 8px 0; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    @media (max-width: 900px) {{ .two {{ grid-template-columns: 1fr; }} }}
    .tg-indicators {{ margin-top: 16px; display: flex; flex-direction: column; gap: 24px; }}
    .tg-indicator-block h3 {{ margin: 0 0 12px 0; font-size: 18px; }}
    .tg-post-stack {{ display: flex; flex-direction: column; gap: 16px; margin-top: 8px; }}
    .tg-post-card {{ border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: #fff; padding: 0 0 12px 0; }}
    .tg-post-images {{ display: flex; flex-direction: column; gap: 8px; }}
    .tg-post-img {{ width: 100%; max-height: 420px; object-fit: contain; display: block; background: #f8fafc; }}
    .tg-post-text {{ margin: 12px 16px 8px; font-size: 15px; line-height: 1.55; color: #1e293b; }}
    .tg-post-text p {{ margin: 0 0 10px 0; }}
    .tg-post-text p:last-child {{ margin-bottom: 0; }}
    .tg-post-meta {{ margin: 8px 16px 0; }}
    .tg-post-link {{ margin: 4px 16px 0; display: inline-block; font-size: 13px; color: #2563eb; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hdr">
      <h1 style="margin:0 0 4px 0">{title}</h1>
      {'<div class="muted">' + subtitle + '</div>' if subtitle else ''}
      <div class="muted" style="margin-top:6px">{company} {("· " + address) if address else ""}</div>
      <div class="muted">Период: {date_from} — {date_to} · Сгенерировано: {generated_at}</div>
    </section>

    <section class="card">
      <h3>Индикаторы</h3>
      {tg_indicators_html}
      {ind_html}
      <div id="cny_chart" style="height:360px"></div>
      <div class="grid" id="parsed_charts"></div>
    </section>

    {dev_section}

    {comp_section}

    {region_section}

    {_section_rich("Кластеры похожих новостей", processed_clusters, processed_clusters_json)}
    {_section_rich("Общие новости", processed_news, processed_news_json)}
    {'<section class="muted" style="padding:8px 2px 24px 2px">' + footer + '</section>' if footer else ''}
  </div>
  <script>
    const cnyX = {_json(cny_x)};
    const cnyY = {_json(cny_y)};
    Plotly.newPlot('cny_chart', [{{x: cnyX, y: cnyY, type:'scatter', mode:'lines+markers', line:{{width:3,color:'#0ea5e9'}}, marker:{{size:6}}}}],
      {{title:'Курс CNY/RUB', margin:{{l:50,r:20,t:40,b:60}}, paper_bgcolor:'#fff', plot_bgcolor:'#fff', xaxis:{{tickangle:-35, gridcolor:'#e2e8f0'}}, yaxis:{{gridcolor:'#e2e8f0'}}}},
      {{displayModeBar:false, responsive:true}});

    const parsed = {_json(parsed_by_name)};
    const holder = document.getElementById('parsed_charts');
    Object.keys(parsed).forEach((name, idx) => {{
      const id = 'pch_' + idx;
      const div = document.createElement('div');
      div.className = 'card';
      div.innerHTML = `<h3 style="font-size:16px">${{name}}</h3><div id="${{id}}" style="height:320px"></div>`;
      holder.appendChild(div);
      Plotly.newPlot(id, [{{x: parsed[name].x, y: parsed[name].y, type:'scatter', mode:'lines+markers', line:{{width:3,color:'#2563eb'}}, marker:{{size:6}}}}],
        {{margin:{{l:50,r:20,t:20,b:80}}, paper_bgcolor:'#fff', plot_bgcolor:'#fff', xaxis:{{tickangle:-35, gridcolor:'#e2e8f0'}}, yaxis:{{gridcolor:'#e2e8f0'}}}},
        {{displayModeBar:false, responsive:true}});
    }});
  </script>
</body>
</html>"""
