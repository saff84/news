from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class IndicatorLatestOut(BaseModel):
    series: str
    value: float
    unit: str | None = None
    source_name: str | None = None
    period_date: date
    fetched_at: datetime
    updated_at_msk: datetime | None = None


class IndicatorPointOut(BaseModel):
    period_date: date
    value: float


class IndicatorHistoryOut(BaseModel):
    series: str
    unit: str | None = None
    items: list[IndicatorPointOut]

