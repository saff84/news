"""API for PDF report configuration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.services.report_config import get_report_config, save_report_config
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/report-config", tags=["report-config"])


class ReportConfigOut(BaseModel):
    title: str
    subtitle: str
    company_name: str
    company_address: str
    footer_text: str
    include_news: bool
    include_indicators: bool
    include_regions: bool
    date_range_days: int
    report_month: str | None  # "YYYY-MM" — отчёт за месяц (приоритет над date_range_days)


class ReportConfigUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    company_name: str | None = Field(default=None, max_length=200)
    company_address: str | None = Field(default=None, max_length=500)
    footer_text: str | None = Field(default=None, max_length=500)
    include_news: bool | None = None
    include_indicators: bool | None = None
    include_regions: bool | None = None
    date_range_days: int | None = Field(default=None, ge=1, le=365)
    report_month: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2})?$")  # "2026-01" or empty

    @field_validator("report_month", mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> str | None:
        return None if v == "" else (v if isinstance(v, str) else None)


def _to_out(cfg: dict[str, Any]) -> ReportConfigOut:
    defaults = {
        "title": "Аналитический отчёт",
        "subtitle": "",
        "company_name": "",
        "company_address": "",
        "footer_text": "",
        "include_news": True,
        "include_indicators": True,
        "include_regions": True,
        "date_range_days": 30,
        "report_month": None,
    }
    merged = {**defaults, **cfg}
    return ReportConfigOut(**{k: merged.get(k, v) for k, v in defaults.items()})


@router.get("", response_model=ReportConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> ReportConfigOut:
    """Get report config for PDF export."""
    cfg = get_report_config(db)
    return _to_out(cfg)


@router.put("", response_model=ReportConfigOut)
def update_config(
    payload: ReportConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ReportConfigOut:
    """Update report config (Admin only)."""
    kwargs = payload.model_dump(exclude_unset=True)
    save_report_config(db, **kwargs)
    cfg = get_report_config(db)
    return _to_out(cfg)
