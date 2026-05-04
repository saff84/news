"""API for parsing and importing indicator tables from PDF/images."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import ParsedIndicator
from app.parsers.table_extractor import extract_from_image, extract_from_pdf

router = APIRouter(prefix="/indicators", tags=["indicators"])

# Russian month names for parsing period strings (e.g. "24 июля 2022 г." or "30 октября 2023 г. - 17 декабря 2023 г.")
_RU_MONTHS = {
    "января": 1, "янв": 1, "февраля": 2, "фев": 2, "марта": 3, "мар": 3,
    "апреля": 4, "апр": 4, "мая": 5, "май": 5, "июня": 6, "июн": 6,
    "июля": 7, "июл": 7, "августа": 8, "авг": 8, "сентября": 9, "сен": 9,
    "октября": 10, "окт": 10, "ноября": 11, "ноя": 11, "декабря": 12, "дек": 12,
}


def _period_sort_key(period: str) -> tuple[int, int, int]:
    """Extract (year, month, day) from period string for chronological sorting."""
    s = period.split(" - ")[0].strip() if " - " in period else period.strip()
    s_lower = s.lower()
    # Year-only: 2021, 2022
    m_year = re.match(r"^(\d{4})$", s)
    if m_year:
        return (int(m_year.group(1)), 1, 1)
    # Abbreviated month + year: Янв. 2026, Фев 2025
    m_abbr = re.search(r"(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\.?\s*(\d{4})", s_lower)
    if m_abbr:
        mo = _RU_MONTHS.get(m_abbr.group(1).lower(), 1)
        return (int(m_abbr.group(2)), mo, 1)
    for month_name, month_num in _RU_MONTHS.items():
        if month_name in s_lower:
            m = re.search(r"(\d{1,2})\s+.*?(\d{4})", s)
            if m:
                day, year = int(m.group(1)), int(m.group(2))
                return (year, month_num, min(day, 31))
    # ISO: 2024-01 or 2024-01-15
    m = re.search(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        d = int(m.group(3)) if m.group(3) else 1
        return (y, mo, min(d, 31))
    return (9999, 99, 99)


class ParsedIndicatorOut(BaseModel):
    id: str
    indicator_name: str
    period: str
    value: float
    change_pct: float | None
    unit: str | None
    source_name: str | None
    created_at: str


class ParsedIndicatorCreateIn(BaseModel):
    indicator_name: str = Field(min_length=1, max_length=500)
    period: str = Field(min_length=1, max_length=50)
    value: float
    change_pct: float | None = None
    unit: str | None = None
    source_name: str | None = None


class ParsedIndicatorUpdateIn(BaseModel):
    indicator_name: str | None = Field(default=None, min_length=1, max_length=500)
    period: str | None = Field(default=None, min_length=1, max_length=50)
    value: float | None = None
    change_pct: float | None = None
    unit: str | None = None
    source_name: str | None = None


@router.get("/parsed/names")
def list_parsed_indicator_names(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> list[str]:
    """List unique indicator names from parsed_indicators."""
    rows = (
        db.query(ParsedIndicator.indicator_name)
        .distinct()
        .order_by(ParsedIndicator.indicator_name)
        .all()
    )
    return [r[0] for r in rows]


@router.get("/parsed")
def list_parsed_indicators(
    indicator_name: str | None = Query(default=None, description="Filter by indicator name"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> dict:
    """List parsed indicators with optional filter. Sorted chronologically within each indicator."""
    q = db.query(ParsedIndicator)
    if indicator_name:
        q = q.filter(ParsedIndicator.indicator_name == indicator_name)
    total = q.count()
    rows = q.limit(2000).all()  # cap for in-memory sort
    # Sort by indicator_name, then by parsed period date (chronological)
    sorted_rows = sorted(rows, key=lambda r: (r.indicator_name, _period_sort_key(r.period)))
    paginated = sorted_rows[offset : offset + limit]
    items = [
        ParsedIndicatorOut(
            id=str(r.id),
            indicator_name=r.indicator_name,
            period=r.period,
            value=float(r.value),
            change_pct=r.change_pct,
            unit=r.unit,
            source_name=r.source_name,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in paginated
    ]
    return {"items": items, "total": total}


@router.get("/parsed/history")
def get_parsed_indicator_history(
    indicator_name: str = Query(..., description="Indicator name"),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> dict:
    """Get history for a parsed indicator (for chart). Sorted chronologically by parsed period date."""
    rows = (
        db.query(ParsedIndicator)
        .filter(ParsedIndicator.indicator_name == indicator_name)
        .limit(limit * 2)  # fetch extra, we'll sort and limit
        .all()
    )
    # Sort by parsed date (period strings like "24 июля 2022 г." are not sortable alphabetically)
    sorted_rows = sorted(rows, key=lambda r: _period_sort_key(r.period))[:limit]
    return {
        "indicator_name": indicator_name,
        "items": [{"period": r.period, "value": float(r.value), "unit": r.unit} for r in sorted_rows],
    }


@router.post("/parsed/single")
def create_parsed_indicator(
    payload: ParsedIndicatorCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ParsedIndicatorOut:
    """Add a single indicator row manually."""
    row = ParsedIndicator(
        indicator_name=payload.indicator_name,
        period=payload.period,
        value=payload.value,
        change_pct=payload.change_pct,
        unit=payload.unit,
        source_name=payload.source_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ParsedIndicatorOut(
        id=str(row.id),
        indicator_name=row.indicator_name,
        period=row.period,
        value=float(row.value),
        change_pct=row.change_pct,
        unit=row.unit,
        source_name=row.source_name,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.patch("/parsed/{indicator_id}")
def update_parsed_indicator(
    indicator_id: str,
    payload: ParsedIndicatorUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ParsedIndicatorOut:
    """Update a parsed indicator row."""
    import uuid as uuid_mod

    row = db.get(ParsedIndicator, uuid_mod.UUID(indicator_id))
    if not row:
        raise HTTPException(status_code=404, detail="Indicator not found")
    kwargs = payload.model_dump(exclude_unset=True)
    for k, v in kwargs.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return ParsedIndicatorOut(
        id=str(row.id),
        indicator_name=row.indicator_name,
        period=row.period,
        value=float(row.value),
        change_pct=row.change_pct,
        unit=row.unit,
        source_name=row.source_name,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.delete("/parsed/{indicator_id}", status_code=204)
def delete_parsed_indicator(
    indicator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    """Delete a parsed indicator row."""
    import uuid as uuid_mod

    row = db.get(ParsedIndicator, uuid_mod.UUID(indicator_id))
    if not row:
        raise HTTPException(status_code=404, detail="Indicator not found")
    db.delete(row)
    db.commit()


class ParsedRowIn(BaseModel):
    indicator_name: str = Field(min_length=1)
    period: str = Field(min_length=1)
    value: float
    change_pct: float | None = None
    unit: str | None = None


class ImportParsedIn(BaseModel):
    rows: list[ParsedRowIn]
    source_name: str | None = None


@router.post("/parse-document")
def parse_document(
    file: UploadFile = File(...),
    user: User = Depends(require_role(Role.ADMIN)),
) -> list[dict]:
    """
    Parse PDF or image (PNG, JPG) and extract table data.
    Returns editable rows for review before save.
    """
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    ext = (file.filename or "").lower().split(".")[-1]
    if ext == "pdf":
        try:
            rows = extract_from_pdf(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parse error: {e}")
    elif ext in ("png", "jpg", "jpeg", "webp", "bmp"):
        try:
            rows = extract_from_image(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Image OCR error: {e}. Ensure Tesseract is installed.")
    else:
        raise HTTPException(status_code=400, detail="Supported: PDF, PNG, JPG, JPEG, WEBP, BMP")

    return rows


@router.post("/import-parsed")
def import_parsed(
    payload: ImportParsedIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Save edited parsed rows to database."""
    batch_id = uuid.uuid4()
    inserted = 0
    for r in payload.rows:
        row = ParsedIndicator(
            indicator_name=r.indicator_name,
            period=r.period,
            value=r.value,
            change_pct=r.change_pct,
            unit=r.unit,
            source_name=payload.source_name,
            import_batch_id=batch_id,
        )
        db.add(row)
        inserted += 1
    db.commit()
    return {"inserted": inserted, "batch_id": str(batch_id)}
