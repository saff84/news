"""Extract structured table data from PDF and images (screenshots)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import pdfplumber
from PIL import Image
import pytesseract


@dataclass
class ParsedCell:
    """Single cell: value and optional change_pct in parentheses."""
    value: float | None
    change_pct: float | None
    raw: str


@dataclass
class ParsedRow:
    """Row with indicator name and values per period."""
    indicator_name: str
    unit: str | None
    values: dict[str, ParsedCell]  # period -> cell
    level: int = 0  # 0=main, 1=sub-indicator (— МКД, — ИЖС)


def _parse_number_with_pct(s: str) -> ParsedCell:
    """Parse '96,4' or '41,6 (+55,1%)' or '—'."""
    s = (s or "").strip()
    if not s or s == "—" or s == "-":
        return ParsedCell(value=None, change_pct=None, raw=s)

    value = None
    change_pct = None

    # Match number with optional (+\d% or -\d%)
    match = re.search(r"([\d\s,]+)\s*(?:\(([+-]?[\d,]+)\s*%\))?", s)
    if match:
        num_str = match.group(1).replace(",", ".").replace(" ", "")
        try:
            value = float(num_str)
        except ValueError:
            pass
        if match.group(2):
            try:
                change_pct = float(match.group(2).replace(",", "."))
            except ValueError:
                pass

    return ParsedCell(value=value, change_pct=change_pct, raw=s)


def _extract_table_from_text(text: str, period_headers: list[str] | None = None) -> list[ParsedRow]:
    """
    Heuristic extraction from OCR/plain text.
    period_headers: e.g. ['2021','2022','2023','2024','2025','Янв. 2026']
    """
    rows: list[ParsedRow] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if not period_headers:
        # Try to detect headers from first lines
        period_headers = []
        for line in lines[:5]:
            # Look for year-like tokens
            tokens = re.findall(r"\b(20\d{2}|Янв\.\s*20\d{2}|Фев\.\s*20\d{2})\b", line, re.I)
            if tokens:
                period_headers = tokens
                break

    for line in lines:
        # Skip header-like lines
        if re.match(r"^№?\s*$", line) or re.match(r"^Наименование", line, re.I):
            continue
        # Split by multiple spaces or tabs
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        if not name or re.match(r"^\d+$", name):
            continue
        values = {}
        for i, p in enumerate(parts[1:]):
            period = period_headers[i] if period_headers and i < len(period_headers) else str(i)
            values[period] = _parse_number_with_pct(p)
        rows.append(ParsedRow(indicator_name=name, unit=None, values=values, level=0))

    return rows


def _to_flat_rows(rows: list[dict]) -> list[dict[str, Any]]:
    """Convert nested {indicator_name, values: {period: cell}} to flat [{indicator_name, period, value, change_pct}]."""
    flat: list[dict[str, Any]] = []
    for r in rows:
        name = r.get("indicator_name") or ""
        unit = r.get("unit")
        for period, cell in (r.get("values") or {}).items():
            if isinstance(cell, dict):
                v = cell.get("value")
                if v is not None:
                    flat.append({
                        "indicator_name": name,
                        "period": str(period),
                        "value": float(v),
                        "change_pct": cell.get("change_pct"),
                        "unit": unit,
                    })
    return flat


def extract_from_pdf(file_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract tables from PDF. Returns flat list of dicts for editing/saving.
    """
    rows: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables or []:
                if not table or len(table) < 2:
                    continue
                headers = table[0]
                period_cols = [str(h).strip() for h in (headers or [])[1:] if h and str(h).strip()]
                for row in table[1:]:
                    if not row:
                        continue
                    name = (row[0] or "").strip()
                    if not name or name == "№" or "Наименование" in name:
                        continue
                    values = {}
                    for i, cell in enumerate(row[1:]):
                        period = period_cols[i] if i < len(period_cols) else str(i)
                        if cell is not None and str(cell).strip():
                            pc = _parse_number_with_pct(str(cell))
                            if pc.value is not None:
                                values[period] = {"value": pc.value, "change_pct": pc.change_pct, "raw": pc.raw}
                    if values:
                        rows.append({
                            "indicator_name": name,
                            "unit": None,
                            "values": values,
                            "level": 1 if name.startswith("—") else 0,
                        })
    return _to_flat_rows(rows)


def extract_from_image(file_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract text from image via OCR, then parse table heuristically.
    """
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img, lang="rus+eng")
    rows = _extract_table_from_text(text)
    nested = [
        {
            "indicator_name": r.indicator_name,
            "unit": r.unit,
            "values": {k: {"value": v.value, "change_pct": v.change_pct, "raw": v.raw} for k, v in r.values.items() if v.value is not None},
            "level": r.level,
        }
        for r in rows
    ]
    return _to_flat_rows(nested)
