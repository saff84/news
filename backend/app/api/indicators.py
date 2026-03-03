from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import IndicatorDaily, IndicatorSeries
from app.schemas.indicators import IndicatorHistoryOut, IndicatorLatestOut, IndicatorPointOut
from app.workers.indicators import fetch_indicator_cny_rub


router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/cny-rub/latest", response_model=IndicatorLatestOut)
def cny_rub_latest(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> IndicatorLatestOut:
    row = (
        db.query(IndicatorDaily)
        .filter(IndicatorDaily.series == IndicatorSeries.CNY_RUB)
        .order_by(IndicatorDaily.period_date.desc(), IndicatorDaily.fetched_at.desc())
        .limit(1)
        .one_or_none()
    )
    if not row:
        # Return "empty" state as of today with value=0 is misleading; better raise a clean 404.
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CNY/RUB indicator is not collected yet")

    updated_at_msk = None
    try:
        v = (row.meta or {}).get("updated_at_msk")
        if isinstance(v, str) and v:
            updated_at_msk = dt.datetime.fromisoformat(v)
    except Exception:
        updated_at_msk = None

    return IndicatorLatestOut(
        series=row.series.value,
        value=float(row.value),
        unit=row.unit,
        source_name=row.source_name,
        period_date=row.period_date,
        fetched_at=row.fetched_at,
        updated_at_msk=updated_at_msk,
    )


@router.get("/cny-rub/history", response_model=IndicatorHistoryOut)
def cny_rub_history(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> IndicatorHistoryOut:
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = (
        db.query(IndicatorDaily)
        .filter(IndicatorDaily.series == IndicatorSeries.CNY_RUB)
        .filter(IndicatorDaily.period_date >= cutoff)
        .order_by(IndicatorDaily.period_date.asc())
        .all()
    )
    return IndicatorHistoryOut(
        series=IndicatorSeries.CNY_RUB.value,
        unit="RUB",
        items=[IndicatorPointOut(period_date=r.period_date, value=float(r.value)) for r in rows],
    )


@router.post("/cny-rub/collect-now")
def cny_rub_collect_now(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    return fetch_indicator_cny_rub(db)

