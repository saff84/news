"""Load/save report config for PDF export."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.config import ReportConfig


def get_report_config(db: Session) -> dict[str, Any]:
    """Get report config. Returns default dict if not set."""
    row = db.query(ReportConfig).filter(ReportConfig.id == 1).first()
    if row and row.settings_json:
        return dict(row.settings_json)
    return _default_config()


def save_report_config(db: Session, **kwargs: Any) -> ReportConfig:
    """Update report config. Merges with existing."""
    row = db.query(ReportConfig).filter(ReportConfig.id == 1).first()
    if not row:
        row = ReportConfig(id=1, settings_json={})
        db.add(row)
    current = dict(row.settings_json or {})
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v
        elif k in current:
            del current[k]
    row.settings_json = current
    db.commit()
    db.refresh(row)
    return row


def _default_config() -> dict[str, Any]:
    return {
        "title": "Аналитический отчёт",
        "subtitle": "",
        "company_name": "",
        "company_address": "",
        "footer_text": "",
        "include_news": True,
        "include_indicators": True,
        "include_regions": True,
        "date_range_days": 30,
        "report_month": None,  # "YYYY-MM" — отчёт за месяц; приоритет над date_range_days
    }
