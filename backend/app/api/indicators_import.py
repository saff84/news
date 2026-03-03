"""API for parsing and importing indicator tables from PDF/images."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import ParsedIndicator
from app.parsers.table_extractor import extract_from_image, extract_from_pdf

router = APIRouter(prefix="/indicators", tags=["indicators"])


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
