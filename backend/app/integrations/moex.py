from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import httpx


@dataclass(frozen=True)
class MoexRate:
    secid: str
    value: float
    waprice: float | None
    updated_at_msk: dt.datetime | None


def _parse_marketdata_row(columns: list[str], row: list) -> dict[str, object]:
    return {columns[i]: row[i] for i in range(min(len(columns), len(row)))}


def fetch_cny_rub_tom(*, timeout_s: float = 20.0) -> MoexRate:
    """
    Fetch CNY/RUB rate from MOEX ISS (FX market, CETS board, TOM settlement).
    Uses free, delayed marketdata fields.
    """
    url = (
        "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/"
        "securities/CNYRUB_TOM.json"
        "?iss.meta=off&iss.only=marketdata&marketdata.columns=SECID,LAST,WAPRICE,UPDATETIME"
    )
    r = httpx.get(url, timeout=timeout_s, follow_redirects=True, headers={"User-Agent": "NewsIntParser/0.1"})
    r.raise_for_status()
    payload = r.json()

    md = payload.get("marketdata") or {}
    columns = md.get("columns") or []
    data = md.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list) or not data:
        raise RuntimeError("MOEX marketdata is empty")

    row0 = data[0]
    if not isinstance(row0, list):
        raise RuntimeError("MOEX marketdata row format is unexpected")

    m = _parse_marketdata_row(columns, row0)
    secid = str(m.get("SECID") or "CNYRUB_TOM")
    last = m.get("LAST")
    wap = m.get("WAPRICE")
    upd = m.get("UPDATETIME")

    value: float | None = float(last) if last is not None else None
    waprice: float | None = float(wap) if wap is not None else None
    if value is None and waprice is not None:
        value = waprice
    if value is None:
        raise RuntimeError("MOEX returned no LAST/WAPRICE for CNYRUB_TOM")

    updated_at_msk: dt.datetime | None = None
    if isinstance(upd, str) and upd.strip():
        # MOEX UPDATETIME is a time string in exchange timezone (MSK)
        try:
            t = dt.time.fromisoformat(upd.strip())
            now_msk = dt.datetime.now(ZoneInfo("Europe/Moscow"))
            updated_at_msk = dt.datetime.combine(now_msk.date(), t, tzinfo=ZoneInfo("Europe/Moscow"))
        except Exception:
            updated_at_msk = None

    return MoexRate(secid=secid, value=float(value), waprice=waprice, updated_at_msk=updated_at_msk)

