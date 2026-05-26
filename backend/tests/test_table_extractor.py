"""Tests for indicator table extraction."""

from app.parsers.table_extractor import (
    _extract_date_value_pairs_from_text,
    _extract_date_value_table,
    extract_from_xlsx,
)


def test_extract_date_value_table_multiple_rows():
    text = """
    Период действия ставки | Значение
    16 февраля 2026 г. | 16,00
    22 декабря 2025 г. - 15 февраля 2026 г. | 15,50
    24 июля 2022 г. - 17 декабря 2023 г. | 7,50
    """
    rows = _extract_date_value_table(text)
    assert len(rows) >= 3
    periods = {r["period"] for r in rows}
    assert any("16 февраля 2026" in p for p in periods)
    assert any("15,50" in str(r["value"]) or r["value"] == 15.5 for r in rows)


def test_extract_date_value_accepts_dot_decimal():
    text = "10 января 2025 г.\t16.00"
    rows = _extract_date_value_table(text)
    assert len(rows) == 1
    assert rows[0]["value"] == 16.0


def test_extract_date_value_pairs_from_single_line_ocr():
    text = (
        "16 февраля 2026 г. 16,00 22 декабря 2025 г. - 15 февраля 2026 г. 15,50 "
        "24 июля 2022 г. - 17 декабря 2023 г. 7,50"
    )
    rows = _extract_date_value_pairs_from_text(text)
    assert len(rows) >= 3


def test_extract_from_xlsx_key_rate():
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Период действия ставки", "Значение", "Ссылка"])
    ws.append(["16 февраля 2026 г.", "16,00", ""])
    ws.append(["22 декабря 2025 г. - 15 февраля 2026 г.", "15,50", ""])
    ws.append(["24 июля 2022 г. - 17 декабря 2023 г.", "7,50", ""])
    buf = BytesIO()
    wb.save(buf)
    rows = extract_from_xlsx(buf.getvalue())
    assert len(rows) == 3
    assert rows[0]["indicator_name"] == "Ключевая ставка"
    assert rows[0]["value"] == 16.0
