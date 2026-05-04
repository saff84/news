"""Convert AI summary text with Markdown links to HTML / ReportLab markup (safe subset)."""

from __future__ import annotations

import re
from html import escape
from xml.sax.saxutils import escape as xml_escape

# [label](http://...)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def markdown_links_to_html(text: str | None) -> str:
    """Escape text and turn [t](url) into <a>; newlines → <br>."""
    if not text:
        return ""
    parts: list[str] = []
    pos = 0
    for m in _MD_LINK.finditer(text):
        parts.append(escape(text[pos : m.start()]).replace("\n", "<br>\n"))
        parts.append(
            f'<a href="{escape(m.group(2))}" target="_blank" rel="noreferrer">{escape(m.group(1))}</a>'
        )
        pos = m.end()
    parts.append(escape(text[pos:]).replace("\n", "<br>\n"))
    return "".join(parts)


def markdown_links_to_reportlab_markup(text: str | None) -> str:
    """Subset of HTML for reportlab.platypus.Paragraph (links + line breaks)."""
    if not text:
        return ""
    parts: list[str] = []
    pos = 0
    for m in _MD_LINK.finditer(text):
        parts.append(xml_escape(text[pos : m.start()]).replace("\n", "<br/>"))
        label = xml_escape(m.group(1))
        url = xml_escape(m.group(2))
        parts.append(f'<a href="{url}" color="blue">{label}</a>')
        pos = m.end()
    parts.append(xml_escape(text[pos:]).replace("\n", "<br/>"))
    return "".join(parts)
