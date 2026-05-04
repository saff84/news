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
    """
    Parse cell value with optional change.
    Supports: '96,4' | '41,6 (+55,1%)' | '7,49 (-0,19 п.п.)' | multiline '96,4\\n(+55,1%)'
    """
    s = (s or "").replace("\n", " ").replace("\r", " ").strip()
    if not s or s == "—" or s == "-":
        return ParsedCell(value=None, change_pct=None, raw=s)

    value = None
    change_pct = None

    # Primary value: decimal (96,4 or 7.49) or integer. Prefer decimal to avoid matching years.
    num_match = re.search(r"(\d{1,3}[,.]\d{1,6})|(\d{1,3}(?:[,.]\d+)?)", s)
    if num_match:
        num_str = (num_match.group(1) or num_match.group(2) or "").replace(",", ".").replace(" ", "")
        try:
            val = float(num_str)
            # Reject 4-digit integers 1900-2100 (likely years in period headers)
            if 1900 <= val <= 2100 and val == int(val) and "." not in (num_match.group(0) or ""):
                pass
            else:
                value = val
        except (ValueError, TypeError):
            pass

    # Change: (+55,1%) or (-0,19 п.п.) or (+1,02 п.п.)
    change_match = re.search(r"\(([+-]?[\d,\.]+)\s*(?:%|п\.п\.?)\)", s, re.I)
    if change_match:
        try:
            change_pct = float(change_match.group(1).replace(",", "."))
        except ValueError:
            pass

    return ParsedCell(value=value, change_pct=change_pct, raw=s)


# Russian month names for date detection
_RU_MONTHS = r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
# Pattern: "16 февраля 2026 г." or "22 декабря 2025 г. - 15 февраля 2026 г."
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2}\s+" + _RU_MONTHS + r"\s+\d{4}\s*г\.(?:\s*-\s*\d{1,2}\s+" + _RU_MONTHS + r"\s+\d{4}\s*г\.)?)",
    re.I,
)
# Number with comma decimal: 15,50 or 16,00 (prefer to avoid matching years like 2026)
_NUMBER_RE = re.compile(r"\b(\d{1,3},\d{2})\b")


def _extract_date_value_table(text: str, default_indicator: str = "Ключевая ставка") -> list[dict[str, Any]]:
    """
    Extract rows from format: "период | значение | ссылка" (e.g. CBR key rate table).
    Each line: date/range, number, optional reference.
    """
    flat: list[dict[str, Any]] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for line in lines:
        # Find number in line (e.g. 15,50)
        num_match = _NUMBER_RE.search(line)
        if not num_match:
            continue
        try:
            value = float(num_match.group(1).replace(",", "."))
        except ValueError:
            continue
        # Period: text before the number, or first column if split by 2+ spaces
        parts = re.split(r"\s{2,}|\t", line)
        period = ""
        if len(parts) >= 2:
            # First part is usually period (date)
            period = (parts[0] or "").strip()
            # Check if period looks like a date
            if _DATE_RANGE_RE.match(period):
                pass
            else:
                # Maybe number is in first part - try to extract period before number
                before_num = line[: num_match.start()].strip()
                if _DATE_RANGE_RE.search(before_num):
                    period = _DATE_RANGE_RE.search(before_num).group(1).strip()
                else:
                    period = before_num or parts[0]
        else:
            before_num = line[: num_match.start()].strip()
            if _DATE_RANGE_RE.search(before_num):
                period = _DATE_RANGE_RE.search(before_num).group(1).strip()
            else:
                period = before_num or "—"

        if not period:
            continue
        flat.append({
            "indicator_name": default_indicator,
            "period": period,
            "value": value,
            "change_pct": None,
            "unit": "%",
        })
    return flat


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


def _looks_like_date_period(s: str) -> bool:
    """Check if string looks like a date/period (e.g. '16 февраля 2026 г.' or '24 июля 2022 г. - 17 декабря 2023 г.')."""
    if not s or len(s) < 10:
        return False
    return bool(_DATE_RANGE_RE.search(s))


def _extract_date_value_from_table_cells(table: list[list[str | None]]) -> list[dict[str, Any]]:
    """Extract from CBR-style table: period | value | reference. Period must look like a date."""
    flat: list[dict[str, Any]] = []
    for row in table or []:
        if not row:
            continue
        # First cell: period (date or range)
        period = (row[0] or "").strip()
        if not period or "Наименование" in period or period == "№":
            continue
        if not _looks_like_date_period(period):
            continue
        value = None
        # Find number in remaining cells
        for cell in row[1:]:
            if cell is None:
                continue
            s = str(cell).strip()
            num_match = _NUMBER_RE.search(s)
            if num_match:
                try:
                    value = float(num_match.group(1).replace(",", "."))
                except ValueError:
                    pass
                if value is not None:
                    break
        if value is not None and period:
            flat.append({
                "indicator_name": "Ключевая ставка",
                "period": period,
                "value": value,
                "change_pct": None,
                "unit": "%",
            })
    return flat


def _is_period_header(cell: str) -> bool:
    """Check if cell looks like a period (year or month.year)."""
    s = (cell or "").strip()
    if re.match(r"^20\d{2}$", s):  # 2021, 2022...
        return True
    if re.match(r"^(?:Янв|Фев|Мар|Апр|Май|Июн|Июл|Авг|Сен|Окт|Ноя|Дек)\.?\s*20\d{2}$", s, re.I):
        return True
    return False


def _extract_matrix_table(table: list[list[str | None]]) -> list[dict[str, Any]]:
    """
    Extract from matrix: rows = indicators, cols = periods (2021, 2022, ..., Янв. 2026).
    First 1-2 columns: № and/or Наименование. Rest: period headers.
    Handles hierarchical rows (— sub-indicator) and cells with value (change).
    """
    nested: list[dict[str, Any]] = []
    if not table or len(table) < 2:
        return []

    # Find header row and period columns
    header_row = table[0]
    name_col = 0
    if header_row and len(header_row) > 1:
        first = (header_row[0] or "").strip()
        second = (header_row[1] or "").strip() if len(header_row) > 1 else ""
        if first == "№" and second and ("Наименование" in second or "показателя" in second.lower()):
            name_col = 1
    period_cols: list[str] = []
    for i, h in enumerate(header_row or []):
        if i <= name_col:
            continue
        s = str(h or "").strip()
        if s:
            period_cols.append(s)

    if not period_cols:
        return []

    parent_name = ""
    for row in table[1:]:
        if not row:
            continue
        name = (row[name_col] if name_col < len(row) else row[0] if row else "") or ""
        name = str(name).strip()
        if not name or name == "№" or re.match(r"^Наименование", name, re.I):
            continue
        # Category headers (no numbers) - update parent for sub-rows
        values = {}
        for i, cell in enumerate(row[name_col + 1 : name_col + 1 + len(period_cols)]):
            period = period_cols[i] if i < len(period_cols) else str(i)
            if cell is not None and str(cell).strip():
                pc = _parse_number_with_pct(str(cell))
                if pc.value is not None:
                    values[period] = {"value": pc.value, "change_pct": pc.change_pct, "raw": pc.raw}
        if values:
            if name.startswith("—"):
                full_name = f"{parent_name} — {name.lstrip('—').strip()}" if parent_name else name.lstrip("—").strip()
            else:
                parent_name = name
                full_name = name
            nested.append({
                "indicator_name": full_name,
                "unit": None,
                "values": values,
                "level": 1 if name.startswith("—") else 0,
            })

    return _to_flat_rows(nested)


def extract_from_pdf(file_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract tables from PDF. Returns flat list of dicts for editing/saving.
    Supports: CBR-style (period|value), matrix (indicators x periods), date-value text.
    """
    flat_rows: list[dict[str, Any]] = []
    nested_rows: list[dict[str, Any]] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables or []:
                if not table or len(table) < 2:
                    continue
                # Try CBR-style first (period | value | ref)
                date_val = _extract_date_value_from_table_cells(table)
                if date_val:
                    flat_rows.extend(date_val)
                    continue
                # Matrix table: indicators x periods (e.g. housing sector report)
                matrix_rows = _extract_matrix_table(table)
                if matrix_rows:
                    flat_rows.extend(matrix_rows)
                    continue
                # Fallback: headers + data
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
                        nested_rows.append({
                            "indicator_name": name,
                            "unit": None,
                            "values": values,
                            "level": 1 if name.startswith("—") else 0,
                        })

    if flat_rows:
        return flat_rows
    if nested_rows:
        return _to_flat_rows(nested_rows)
    # Fallback: extract text and try date-value pattern
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return _extract_date_value_table(text)


def extract_from_image(file_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract text from image via OCR, then parse table heuristically.
    """
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img, lang="rus+eng")
    # Try date-value format first (CBR key rate etc.)
    date_val = _extract_date_value_table(text)
    if date_val:
        return date_val
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
