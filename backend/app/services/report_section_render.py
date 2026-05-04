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


def parse_report_section_json(raw: str) -> dict[str, Any]:
    s = strip_json_fences(raw)
    data = json.loads(s)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")
    payload = ReportSectionPayload.model_validate(data)
    return payload.model_dump()


def section_dict_to_markdown(d: dict[str, Any]) -> str:
    """Плоское текстовое представление (fallback для API и старых клиентов)."""
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
        t = (b.get("text") or "").strip()
        cites = b.get("citations") or []
        link_bits: list[str] = []
        for c in cites:
            if not isinstance(c, dict):
                continue
            url = (c.get("url") or "").strip()
            lab = (c.get("label") or "источник").strip()
            if url:
                link_bits.append(f"[{lab}]({url})")
        if t:
            parts.append("- " + t + (" " + " ".join(link_bits) if link_bits else ""))
    if d.get("closing"):
        parts.append(str(d["closing"]))
    return "\n\n".join(parts) if parts else ""


def section_dict_to_html_fragment(d: dict[str, Any]) -> str:
    blocks: list[str] = []
    if d.get("headline"):
        blocks.append(f"<h4 class='sec-headline'>{escape(str(d['headline']))}</h4>")
    if d.get("lead"):
        blocks.append(f"<p class='sec-lead'>{markdown_links_to_html(str(d['lead']))}</p>")
    for p in d.get("paragraphs") or []:
        if p:
            blocks.append(f"<p>{markdown_links_to_html(str(p))}</p>")
    bullets = d.get("bullets") or []
    if bullets:
        lis: list[str] = []
        for b in bullets:
            if not isinstance(b, dict):
                continue
            t = escape(str(b.get("text") or ""))
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
        d = payload
        if d.get("headline"):
            story.append(Paragraph(f"<b>{escape(str(d['headline']))}</b>", normal_style))
        if d.get("lead"):
            story.append(Paragraph(markdown_links_to_reportlab_markup(str(d["lead"])), normal_style))
        for p in d.get("paragraphs") or []:
            if p:
                story.append(Paragraph(markdown_links_to_reportlab_markup(str(p)), normal_style))
        from xml.sax.saxutils import escape as xml_esc

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
