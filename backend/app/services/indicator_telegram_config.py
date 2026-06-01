"""Настройки парсинга Telegram-канала для раздела «Индикаторы»."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.config import IndicatorTelegramConfig


def _default_config() -> dict[str, Any]:
    from app.services.indicator_telegram_report import default_report_groups

    return {
        "enabled": False,
        "channel_username": "",
        "include_keywords": [],
        "exclude_keywords": [],
        "match_whole_words": False,
        "backfill_limit": 100,
        "include_in_report": True,
        "ai_in_report": False,
        "report_groups": default_report_groups(),
        "last_message_id": None,
        "last_fetch_at": None,
        "last_error": None,
    }


def get_indicator_telegram_config(db: Session) -> dict[str, Any]:
    row = db.query(IndicatorTelegramConfig).filter(IndicatorTelegramConfig.id == 1).first()
    if row and row.settings_json:
        return {**_default_config(), **dict(row.settings_json)}
    return _default_config()


def save_indicator_telegram_config(db: Session, **kwargs: Any) -> IndicatorTelegramConfig:
    row = db.query(IndicatorTelegramConfig).filter(IndicatorTelegramConfig.id == 1).first()
    if not row:
        row = IndicatorTelegramConfig(id=1, settings_json={})
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
