"""Парсинг JSON от ИИ и рендер в markdown/HTML/ReportLab."""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer

from app.schemas.report_sections import ReportSectionPayload
from app.services.report_markup import markdown_links_to_html, markdown_links_to_reportlab_markup

_FENCE = re.compile(r"^```(?:json)?\s*", re.I)
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF]+",
    flags=re.UNICODE,
)


def strip_report_emojis(text: str | None) -> str:
    if not text:
        return ""
    return _EMOJI_RE.sub("", text).strip()


def strip_json_fences(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _normalize_section_data(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    bullets = out.get("bullets")
    if isinstance(bullets, list):
        norm: list[dict[str, Any]] = []
        for b in bullets:
            if isinstance(b, str):
                t = strip_report_emojis(b)
                if t:
                    norm.append({"text": t, "citations": []})
            elif isinstance(b, dict):
                t = strip_report_emojis(str(b.get("text") or ""))
                if not t:
                    continue
                cites = b.get("citations") if isinstance(b.get("citations"), list) else []
                norm.append({"text": t, "citations": cites})
        out["bullets"] = norm
    for key in ("headline", "lead", "closing"):
        if out.get(key) is not None:
            out[key] = strip_report_emojis(str(out[key])) or None
    if isinstance(out.get("paragraphs"), list):
        out["paragraphs"] = [strip_report_emojis(str(p)) for p in out["paragraphs"] if strip_report_emojis(str(p))]
    return out


def _validate_section_dict(data: dict[str, Any]) -> dict[str, Any]:
    payload = ReportSectionPayload.model_validate(_normalize_section_data(data))
    return payload.model_dump()


def try_parse_report_section(raw: str | None) -> dict[str, Any] | None:
    """Разбор JSON секции: ограждения ```json, обрезки, bullets-строки."""
    if not raw or not str(raw).strip():
        return None
    candidates: list[str] = []
    s = str(raw).strip()
    candidates.append(s)
    fenced = strip_json_fences(s)
    if fenced not in candidates:
        candidates.append(fenced)
    if "{" in fenced and "}" in fenced:
        inner = fenced[fenced.find("{") : fenced.rfind("}") + 1]
        if inner not in candidates:
            candidates.append(inner)
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return _validate_section_dict(data)
        except Exception:
            continue
    return None


def parse_report_section_json(raw: str) -> dict[str, Any]:
    parsed = try_parse_report_section(raw)
    if parsed is None:
        raise ValueError("Invalid report section JSON")
    return parsed


def merge_report_section_payloads(sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Объединить несколько JSON-секций (батчи общих новостей) в один блок отчёта."""
    clean = [sanitize_section_dict(s) for s in sections if isinstance(s, dict) and s]
    if not clean:
        return {}
    if len(clean) == 1:
        return clean[0]

    merged: dict[str, Any] = {
        "headline": clean[0].get("headline") or "Общие новости",
        "lead": clean[0].get("lead"),
        "paragraphs": [],
        "bullets": [],
        "closing": clean[-1].get("closing"),
    }
    seen_bullets: set[str] = set()
    for sec in clean:
        for p in sec.get("paragraphs") or []:
            pt = str(p).strip()
            if pt and pt not in merged["paragraphs"]:
                merged["paragraphs"].append(pt)
        for b in sec.get("bullets") or []:
            if not isinstance(b, dict):
                continue
            t = str(b.get("text") or "").strip()
            if not t:
                continue
            key = t.lower()[:160]
            if key in seen_bullets:
                continue
            seen_bullets.add(key)
            merged["bullets"].append(b)
    return merged


def build_general_news_section(theme_results: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Собрать финальный JSON «Общие новости» из саммари по темам."""
    subsections: list[dict[str, Any]] = []
    headline: str | None = None
    lead: str | None = None
    closing: str | None = None
    for i, (title, payload) in enumerate(theme_results):
        if not payload:
            continue
        p = sanitize_section_dict(payload)
        bullets = list(p.get("bullets") or [])
        paragraphs = list(p.get("paragraphs") or [])
        if not bullets and not paragraphs:
            continue
        subsections.append({"title": title, "paragraphs": paragraphs, "bullets": bullets})
        if i == 0:
            headline = p.get("headline")
            lead = p.get("lead")
        if p.get("closing"):
            closing = p.get("closing")
    if not subsections:
        return {}
    return {
        "headline": headline or "Общие новости",
        "lead": lead,
        "paragraphs": [],
        "bullets": [],
        "subsections": subsections,
        "closing": closing,
    }


def _subsection_body_html(sub: dict[str, Any]) -> str:
    blocks: list[str] = []
    for p in sub.get("paragraphs") or []:
        if p:
            blocks.append(f"<p>{markdown_links_to_html(str(p))}</p>")
    bullets = sub.get("bullets") or []
    if bullets:
        lis: list[str] = []
        for b in bullets:
            if not isinstance(b, dict):
                continue
            t = escape(strip_report_emojis(str(b.get("text") or "")))
            if not t:
                continue
            cites = b.get("citations") or []
            cite_html: list[str] = []
            for c in cites:
                if not isinstance(c, dict):
                    continue
                url = escape(str(c.get("url") or ""))
                lab = escape(str(c.get("label") or "источник"))
                if url:
                    cite_html.append(f'<a href="{url}" target="_blank" rel="noreferrer">{lab}</a>')
            inner = t + (" " + " ".join(cite_html) if cite_html else "")
            lis.append(f"<li>{inner}</li>")
        if lis:
            blocks.append("<ul class='sec-bullets'>" + "".join(lis) + "</ul>")
    return "".join(blocks)


def sanitize_section_dict(d: dict[str, Any]) -> dict[str, Any]:
    return _normalize_section_data(d)


def section_dict_to_markdown(d: dict[str, Any]) -> str:
    """Плоское текстовое представление (fallback для API и старых клиентов)."""
    d = sanitize_section_dict(d)
    parts: list[str] = []
    if d.get("headline"):
        parts.append(str(d["headline"]))
    if d.get("lead"):
        parts.append(str(d["lead"]))
    for p in d.get("paragraphs") or []:
        if p:
            parts.append(str(p))
    for b in d.get("bullets") or []:
        if not isinstance(b, dict):
            continue
        t = str(b.get("text") or "").strip()
        if not t:
            continue
        cites = b.get("citations") or []
        link_bits: list[str] = []
        for c in cites:
            if not isinstance(c, dict):
                continue
            url = (c.get("url") or "").strip()
            lab = (c.get("label") or "источник").strip()
            if url:
                link_bits.append(f"[{lab}]({url})")
        parts.append("- " + t + (" " + " ".join(link_bits) if link_bits else ""))
    for sub in d.get("subsections") or []:
        if not isinstance(sub, dict):
            continue
        st = str(sub.get("title") or "").strip()
        if st:
            parts.append(f"### {st}")
        for p in sub.get("paragraphs") or []:
            if p:
                parts.append(str(p))
        for b in sub.get("bullets") or []:
            if not isinstance(b, dict):
                continue
            t = str(b.get("text") or "").strip()
            if not t:
                continue
            parts.append(f"- {t}")
    if d.get("closing"):
        parts.append(str(d["closing"]))
    return "\n\n".join(parts) if parts else ""


def section_dict_to_html_fragment(d: dict[str, Any]) -> str:
    d = sanitize_section_dict(d)
    blocks: list[str] = []
    if d.get("headline"):
        blocks.append(f"<h4 class='sec-headline'>{escape(str(d['headline']))}</h4>")
    if d.get("lead"):
        blocks.append(f"<p class='sec-lead'>{markdown_links_to_html(str(d['lead']))}</p>")
    subsections = d.get("subsections") or []
    if subsections:
        for sub in subsections:
            if not isinstance(sub, dict):
                continue
            st = str(sub.get("title") or "").strip()
            body = _subsection_body_html(sub)
            if not st and not body:
                continue
            if st:
                blocks.append(f"<h4 class='sec-subtheme'>{escape(st)}</h4>")
            if body:
                blocks.append(f"<div class='sec-subtheme-body'>{body}</div>")
    else:
        for p in d.get("paragraphs") or []:
            if p:
                blocks.append(f"<p>{markdown_links_to_html(str(p))}</p>")
        bullets = d.get("bullets") or []
        if bullets:
            lis: list[str] = []
            for b in bullets:
                if not isinstance(b, dict):
                    continue
                t = escape(strip_report_emojis(str(b.get("text") or "")))
                if not t:
                    continue
                cites = b.get("citations") or []
                cite_html: list[str] = []
                for c in cites:
                    if not isinstance(c, dict):
                        continue
                    url = escape(str(c.get("url") or ""))
                    lab = escape(str(c.get("label") or "источник"))
                    if url:
                        cite_html.append(f'<a href="{url}" target="_blank" rel="noreferrer">{lab}</a>')
                inner = t + (" " + " ".join(cite_html) if cite_html else "")
                lis.append(f"<li>{inner}</li>")
            if lis:
                blocks.append("<ul class='sec-bullets'>" + "".join(lis) + "</ul>")
    if d.get("closing"):
        blocks.append(f"<p class='sec-closing'><em>{markdown_links_to_html(str(d['closing']))}</em></p>")
    return "".join(blocks)


def render_section_inner_html(*, text: str | None, payload: dict[str, Any] | None) -> str:
    """HTML блока секции: JSON → структура, иначе markdown; без сырого ```json в отчёте."""
    pl = payload if isinstance(payload, dict) else None
    if not pl and text:
        pl = try_parse_report_section(text)
    if pl:
        frag = section_dict_to_html_fragment(pl).strip()
        if frag:
            return f"<div class='summary rich structured'>{frag}</div>"
    clean = strip_report_emojis(strip_json_fences(text or ""))
    if clean.strip().startswith("{"):
        pl2 = try_parse_report_section(clean)
        if pl2:
            frag = section_dict_to_html_fragment(pl2).strip()
            if frag:
                return f"<div class='summary rich structured'>{frag}</div>"
        return ""
    if clean.strip():
        return f"<div class='summary rich'>{markdown_links_to_html(clean)}</div>"
    return ""


def append_section_json_to_pdf_story(
    story: list,
    *,
    section_title: str,
    payload: dict[str, Any] | None,
    text_fallback: str | None,
    h3_style: ParagraphStyle,
    normal_style: ParagraphStyle,
    spacer_cm: float = 0.35,
) -> None:
    from reportlab.lib.units import cm

    story.append(Paragraph(f"<b>{escape(section_title)}</b>", h3_style))
    if payload:
        from xml.sax.saxutils import escape as xml_esc

        d = sanitize_section_dict(payload)
        if d.get("headline"):
            story.append(Paragraph(f"<b>{escape(str(d['headline']))}</b>", normal_style))
        if d.get("lead"):
            story.append(Paragraph(markdown_links_to_reportlab_markup(str(d["lead"])), normal_style))
        subs = d.get("subsections") or []
        if subs:
            for sub in subs:
                if not isinstance(sub, dict):
                    continue
                st = str(sub.get("title") or "").strip()
                if st:
                    story.append(Paragraph(f"<b>{escape(st)}</b>", normal_style))
                for p in sub.get("paragraphs") or []:
                    if p:
                        story.append(Paragraph(markdown_links_to_reportlab_markup(str(p)), normal_style))
                for b in sub.get("bullets") or []:
                    if not isinstance(b, dict):
                        continue
                    t = str(b.get("text") or "").strip()
                    if not t:
                        continue
                    cite_parts: list[str] = []
                    for c in b.get("citations") or []:
                        if not isinstance(c, dict):
                            continue
                        url = str(c.get("url") or "").strip()
                        lab = str(c.get("label") or "источник").strip()
                        if url:
                            cite_parts.append(f'<a href="{xml_esc(url)}" color="blue">{xml_esc(lab)}</a>')
                    bullet_xml = "• " + xml_esc(t).replace("\n", "<br/>")
                    if cite_parts:
                        bullet_xml += " " + " ".join(cite_parts)
                    story.append(Paragraph(bullet_xml, normal_style))
                story.append(Spacer(1, 0.15 * cm))
        else:
            for p in d.get("paragraphs") or []:
                if p:
                    story.append(Paragraph(markdown_links_to_reportlab_markup(str(p)), normal_style))

            for b in d.get("bullets") or []:
                if not isinstance(b, dict):
                    continue
                t = str(b.get("text") or "").strip()
                if not t:
                    continue
                cite_parts: list[str] = []
                for c in b.get("citations") or []:
                    if not isinstance(c, dict):
                        continue
                    url = str(c.get("url") or "").strip()
                    lab = str(c.get("label") or "источник").strip()
                    if url:
                        cite_parts.append(f'<a href="{xml_esc(url)}" color="blue">{xml_esc(lab)}</a>')
                bullet_xml = "• " + xml_esc(t).replace("\n", "<br/>")
                if cite_parts:
                    bullet_xml += " " + " ".join(cite_parts)
                story.append(Paragraph(bullet_xml, normal_style))
        if d.get("closing"):
            story.append(Paragraph(f"<i>{markdown_links_to_reportlab_markup(str(d['closing']))}</i>", normal_style))
    elif text_fallback and text_fallback.strip():
        story.append(Paragraph(markdown_links_to_reportlab_markup(text_fallback), normal_style))
    story.append(Spacer(1, spacer_cm * cm))
