from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.integrations.moex import fetch_cny_rub_tom
from app.models.domain import IndicatorDaily, IndicatorSeries


def _today_msk() -> dt.date:
    return dt.datetime.now(ZoneInfo("Europe/Moscow")).date()


def fetch_indicator_cny_rub(db: Session) -> dict:
    rate = fetch_cny_rub_tom()
    period_date = _today_msk()
    fetched_at = dt.datetime.now(dt.timezone.utc)

    stmt = pg_insert(IndicatorDaily).values(
        series=IndicatorSeries.CNY_RUB,
        period_date=period_date,
        value=rate.value,
        unit="RUB",
        source_name="MOEX",
        fetched_at=fetched_at,
        meta={
            "secid": rate.secid,
            "waprice": rate.waprice,
            "updated_at_msk": rate.updated_at_msk.isoformat() if rate.updated_at_msk else None,
        },
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_indicators_series_date",
        set_={
            "value": rate.value,
            "unit": "RUB",
            "source_name": "MOEX",
            "fetched_at": fetched_at,
            "meta": {
                "secid": rate.secid,
                "waprice": rate.waprice,
                "updated_at_msk": rate.updated_at_msk.isoformat() if rate.updated_at_msk else None,
            },
        },
    )
    db.execute(stmt)
    db.commit()

    return {
        "status": "ok",
        "series": "CNY_RUB",
        "period_date": period_date.isoformat(),
        "value": rate.value,
        "unit": "RUB",
        "source_name": "MOEX",
    }


def fetch_indicator_telegram_posts(db: Session) -> dict:
    from app.parsers.indicator_telegram_ingestor import ingest_indicator_telegram

    return ingest_indicator_telegram(db)

