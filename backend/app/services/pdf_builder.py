"""Build PDF report from structured data (charts, news by region/channel)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart

from app.services.indicator_telegram_report import image_path_to_filesystem
from app.services.report_markup import markdown_links_to_reportlab_markup
from app.services.report_section_render import append_section_json_to_pdf_story

# Шрифт с поддержкой кириллицы
_FONT_REGISTERED = False
_FONT_NAME = "DejaVu"


def _register_cyrillic_font() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _FONT_NAME
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ]
    for reg, bold in candidates:
        p_reg, p_bold = Path(reg), Path(bold)
        if p_reg.exists():
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, str(p_reg)))
                if p_bold.exists():
                    pdfmetrics.registerFont(TTFont(f"{_FONT_NAME}-Bold", str(p_bold)))
                _FONT_REGISTERED = True
                return _FONT_NAME
            except Exception:
                continue
    return "Helvetica"


def _make_line_chart(values: list[float], labels: list[str], width: float = 14 * cm, height: float = 5 * cm) -> Drawing | None:
    """Линейный график: даты на X (горизонталь), значения на Y (вертикаль). Современный стиль."""
    if not values or not labels or len(values) != len(labels):
        return None
    if len(values) == 1:
        values = [values[0], values[0]]
        labels = [labels[0], labels[0]]
    n = len(labels)
    max_labels = 12
    if n > max_labels:
        step = max(1, n // max_labels)
        idx = list(range(0, n, step))[:max_labels]
        if idx[-1] != n - 1:
            idx[-1] = n - 1
        labels = [labels[i] for i in idx]
        values = [values[i] for i in idx]
    d = Drawing(width, height)
    c = HorizontalLineChart()
    c.data = [tuple(float(v) for v in values)]
    c.x = 60
    c.y = 40
    c.height = height - 70
    c.width = width - 90
    c.joinedLines = 1
    c.strokeColor = None
    c.fillColor = colors.HexColor("#f8fafc")
    c.lines.strokeWidth = 2.5
    c.lines[0].strokeColor = colors.HexColor("#0ea5e9")
    c.lines[0].strokeWidth = 2.5
    c.categoryAxis.categoryNames = [str(x) for x in labels]
    c.categoryAxis.labels.angle = 45
    c.categoryAxis.labels.fontName = _FONT_NAME if _FONT_REGISTERED else "Helvetica"
    c.categoryAxis.labels.fontSize = 8
    c.categoryAxis.labels.boxAnchor = "n"
    c.valueAxis.labels.fontName = _FONT_NAME if _FONT_REGISTERED else "Helvetica"
    c.valueAxis.labels.fontSize = 9
    c.valueAxis.visibleGrid = 1
    c.valueAxis.gridStrokeWidth = 0.5
    c.valueAxis.gridStrokeColor = colors.HexColor("#e2e8f0")
    c.valueAxis.strokeColor = colors.HexColor("#94a3b8")
    c.valueAxis.strokeWidth = 0.5
    vmin, vmax = min(values), max(values)
    if vmin == vmax:
        c.valueAxis.valueMin = vmin - 1
        c.valueAxis.valueMax = vmax + 1
    else:
        c.valueAxis.valueMin = vmin * 0.98
        c.valueAxis.valueMax = vmax * 1.02
    d.add(c)
    return d


def build_report_pdf(
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
    **kwargs: Any,
) -> bytes:
    """PDF: графики индикаторов и текстовые саммари по застройщикам, конкурентам, регионам (Markdown-ссылки → кликабельные)."""
    font_name = _register_cyrillic_font()
    cfg = report_config or {}
    period_from = period.get("date_from", "")
    period_to = period.get("date_to", "")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    base = getSampleStyleSheet()
    normal_style = ParagraphStyle("CyrillicNormal", parent=base["Normal"], fontName=font_name, fontSize=9)
    h1_style = ParagraphStyle("CyrillicH1", parent=base["Heading1"], fontName=font_name, fontSize=16, spaceAfter=6)
    h2_style = ParagraphStyle("CyrillicH2", parent=base["Heading2"], fontName=font_name, fontSize=11, spaceAfter=4)
    h3_style = ParagraphStyle("CyrillicH3", parent=base["Heading3"], fontName=font_name, fontSize=10, spaceAfter=3)
    story = []

    # Header
    story.append(Paragraph(cfg.get("title", "Аналитический отчёт"), h1_style))
    if cfg.get("subtitle"):
        story.append(Paragraph(cfg["subtitle"], normal_style))
    if cfg.get("company_name") or cfg.get("company_address"):
        parts = [p for p in [cfg.get("company_name"), cfg.get("company_address")] if p]
        story.append(Paragraph("<br/>".join(parts), normal_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<b>Период:</b> {period_from} — {period_to}", normal_style))
    story.append(Spacer(1, 1 * cm))

    # Индикаторы — Telegram (ввод жилья / МКД) и графики
    has_tg = bool(indicator_telegram_sections)
    if daily_indicators or parsed_indicators or has_tg:
        story.append(Paragraph("<b>Индикаторы</b>", h2_style))
        story.append(Spacer(1, 0.3 * cm))

    if has_tg:
        from html import escape as html_escape

        for sec in indicator_telegram_sections or []:
            title = str(sec.get("title") or "").strip()
            if title:
                story.append(Paragraph(f"<b>{html_escape(title)}</b>", h3_style))
            ai_json = sec.get("ai_json")
            if isinstance(ai_json, dict) and ai_json:
                append_section_json_to_pdf_story(
                    story,
                    section_title="",
                    payload=ai_json,
                    text_fallback=None,
                    h3_style=h3_style,
                    normal_style=normal_style,
                    spacer_cm=0.2,
                )
            elif sec.get("ai_text"):
                story.append(Paragraph(markdown_links_to_reportlab_markup(str(sec["ai_text"])), normal_style))
                story.append(Spacer(1, 0.2 * cm))
            for p in sec.get("posts") or []:
                fs = image_path_to_filesystem(p.get("image_path"))
                if fs:
                    try:
                        img = RLImage(str(fs), width=16 * cm, height=9 * cm, kind="proportional")
                        story.append(img)
                        story.append(Spacer(1, 0.2 * cm))
                    except Exception:
                        pass
                if p.get("text"):
                    txt = str(p["text"]).replace("\n", "<br/>")
                    story.append(Paragraph(html_escape(txt)[:4000], normal_style))
                if p.get("post_url"):
                    story.append(Paragraph(f'<a href="{html_escape(str(p["post_url"]))}">Telegram</a>', normal_style))
                story.append(Spacer(1, 0.35 * cm))
        story.append(Spacer(1, 0.3 * cm))

    if daily_indicators:
        story.append(Paragraph("<b>Курс CNY/RUB</b>", h3_style))
        dates = [str(r.period_date) for r in daily_indicators]
        values = [float(r.value) for r in daily_indicators]
        chart = _make_line_chart(values, dates)
        if chart:
            story.append(chart)
            story.append(Spacer(1, 0.5 * cm))

    # Parsed indicators — по каждому показателю график
    if parsed_indicators:
        from collections import defaultdict

        def _period_key(p: str) -> tuple:
            import re
            s = (p or "").strip()
            m = re.match(r"^(\d{4})$", s)
            if m:
                return (int(m.group(1)), 1, 1)
            m = re.search(r"(\d{4})-(\d{1,2})", s)
            if m:
                return (int(m.group(1)), int(m.group(2)), 1)
            # Русские даты: "16 февраля 2026 г." — извлекаем год
            m = re.search(r"(\d{4})", s)
            if m:
                return (int(m.group(1)), 1, 1)
            return (9999, 99, 99)

        by_name: dict[str, list] = defaultdict(list)
        for r in parsed_indicators:
            by_name[r.indicator_name].append(r)
        for ind_name, rows in sorted(by_name.items()):
            if not rows:
                continue
            rows = sorted(rows, key=lambda x: _period_key(x.period))
            story.append(Paragraph(f"<b>{ind_name}</b>", h3_style))
            periods = [str(r.period) for r in rows]
            vals = [float(r.value) for r in rows]
            chart = _make_line_chart(vals, periods)
            if chart:
                story.append(chart)
                story.append(Spacer(1, 0.5 * cm))

    # Выводы ИИ по индикаторам — под графиками
    if (processed_indicators_json or (processed_indicators and processed_indicators.strip())) and (
        daily_indicators or parsed_indicators
    ):
        pi = processed_indicators_json if isinstance(processed_indicators_json, dict) else None
        append_section_json_to_pdf_story(
            story,
            section_title="Выводы ИИ по индикаторам",
            payload=pi,
            text_fallback=processed_indicators,
            h3_style=h3_style,
            normal_style=normal_style,
            spacer_cm=0.5,
        )

    # Текстовые саммари — новая страница (без сырых списков новостей)
    story.append(PageBreak())
    dev_summ = processed_developers_by_name or {}
    dev_j = processed_developers_by_name_json or {}
    comp_summ = processed_competitors_by_name or {}
    comp_j = processed_competitors_by_name_json or {}
    reg_summ = processed_regions_by_name or {}
    reg_j = processed_regions_by_name_json or {}

    if dev_summ or dev_j:
        story.append(Paragraph("<b>Застройщики</b>", h2_style))
        story.append(Spacer(1, 0.2 * cm))
        for title in sorted(set(dev_summ.keys()) | set(dev_j.keys())):
            body = (dev_summ.get(title) or "").strip()
            payload = dev_j.get(title)
            pl = payload if isinstance(payload, dict) else None
            if not body and not pl:
                continue
            append_section_json_to_pdf_story(
                story,
                section_title=title,
                payload=pl,
                text_fallback=body or None,
                h3_style=h3_style,
                normal_style=normal_style,
                spacer_cm=0.4,
            )

    if comp_summ or comp_j:
        story.append(Paragraph("<b>Конкуренты</b>", h2_style))
        story.append(Spacer(1, 0.2 * cm))
        for title in sorted(set(comp_summ.keys()) | set(comp_j.keys())):
            body = (comp_summ.get(title) or "").strip()
            payload = comp_j.get(title)
            pl = payload if isinstance(payload, dict) else None
            if not body and not pl:
                continue
            append_section_json_to_pdf_story(
                story,
                section_title=title,
                payload=pl,
                text_fallback=body or None,
                h3_style=h3_style,
                normal_style=normal_style,
                spacer_cm=0.4,
            )

    if reg_summ or reg_j:
        story.append(Paragraph("<b>Регионы</b>", h2_style))
        story.append(Spacer(1, 0.2 * cm))
        for title in sorted(set(reg_summ.keys()) | set(reg_j.keys())):
            body = (reg_summ.get(title) or "").strip()
            payload = reg_j.get(title)
            pl = payload if isinstance(payload, dict) else None
            if not body and not pl:
                continue
            append_section_json_to_pdf_story(
                story,
                section_title=title,
                payload=pl,
                text_fallback=body or None,
                h3_style=h3_style,
                normal_style=normal_style,
                spacer_cm=0.4,
            )

    pn = processed_news_json if isinstance(processed_news_json, dict) else None
    if pn or (processed_news and processed_news.strip()):
        append_section_json_to_pdf_story(
            story,
            section_title="Общие новости",
            payload=pn,
            text_fallback=processed_news,
            h3_style=h2_style,
            normal_style=normal_style,
            spacer_cm=0.5,
        )

    pc = processed_clusters_json if isinstance(processed_clusters_json, dict) else None
    if pc or (processed_clusters and processed_clusters.strip()):
        append_section_json_to_pdf_story(
            story,
            section_title="Кластеры похожих новостей",
            payload=pc,
            text_fallback=processed_clusters,
            h3_style=h2_style,
            normal_style=normal_style,
            spacer_cm=0.5,
        )

    # Footer
    if cfg.get("footer_text"):
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(f"<i>{cfg['footer_text']}</i>", normal_style))

    doc.build(story)
    return buf.getvalue()
