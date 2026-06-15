"""API for PDF report configuration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.services.general_news_themes import default_general_news_themes, normalize_general_news_themes
from app.services.report_config import get_report_config, save_report_config
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

router = APIRouter(prefix="/report-config", tags=["report-config"])


class GeneralNewsThemeOut(BaseModel):
    title: str
    keywords: list[str] = Field(default_factory=list)


class GeneralNewsThemeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(default_factory=list)


class ReportConfigOut(BaseModel):
    title: str
    subtitle: str
    company_name: str
    company_address: str
    footer_text: str
    include_news: bool
    include_indicators: bool
    include_regions: bool
    include_competitors: bool
    include_developers: bool
    include_general_news: bool
    include_clusters: bool
    include_region_unassigned: bool
    disabled_competitor_ids: list[str]
    disabled_developer_ids: list[str]
    disabled_region_ids: list[str]
    date_range_days: int
    report_month: str | None  # "YYYY-MM" — отчёт за месяц (приоритет над date_range_days)
    general_news_themes: list[GeneralNewsThemeOut] = Field(default_factory=list)


class ReportConfigUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    company_name: str | None = Field(default=None, max_length=200)
    company_address: str | None = Field(default=None, max_length=500)
    footer_text: str | None = Field(default=None, max_length=500)
    include_news: bool | None = None
    include_indicators: bool | None = None
    include_regions: bool | None = None
    include_competitors: bool | None = None
    include_developers: bool | None = None
    include_general_news: bool | None = None
    include_clusters: bool | None = None
    include_region_unassigned: bool | None = None
    disabled_competitor_ids: list[UUID] | None = None
    disabled_developer_ids: list[UUID] | None = None
    disabled_region_ids: list[UUID] | None = None
    date_range_days: int | None = Field(default=None, ge=1, le=365)
    report_month: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2})?$")  # "2026-01" or empty
    general_news_themes: list[GeneralNewsThemeIn] | None = None

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
        "include_competitors": True,
        "include_developers": True,
        "include_general_news": True,
        "include_clusters": True,
        "include_region_unassigned": True,
        "disabled_competitor_ids": [],
        "disabled_developer_ids": [],
        "disabled_region_ids": [],
        "date_range_days": 30,
        "report_month": None,
        "general_news_themes": default_general_news_themes(),
    }
    merged = {**defaults, **cfg}
    out = {k: merged.get(k, v) for k, v in defaults.items()}
    for key in ("disabled_competitor_ids", "disabled_developer_ids", "disabled_region_ids"):
        out[key] = [str(x) for x in (out.get(key) or [])]
    themes = normalize_general_news_themes(out.get("general_news_themes"))
    out["general_news_themes"] = [
        GeneralNewsThemeOut(title=str(t["title"]), keywords=list(t.get("keywords") or [])) for t in themes
    ]
    return ReportConfigOut(**out)


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
    kwargs = payload.model_dump(exclude_unset=True, mode="json")
    if "general_news_themes" in kwargs and kwargs["general_news_themes"] is not None:
        kwargs["general_news_themes"] = [
            {"title": g["title"], "keywords": g.get("keywords") or []}
            for g in kwargs["general_news_themes"]
        ]
    save_report_config(db, **kwargs)
    cfg = get_report_config(db)
    return _to_out(cfg)
