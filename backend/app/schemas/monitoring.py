from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SourceHealthOut(BaseModel):
    id: UUID
    source_type: str
    name: str | None
    base_url: str | None
    feed_url: str | None
    tg_channel_username: str | None
    enabled: bool
    fetch_frequency_min: int
    priority: int
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    backoff_until: datetime | None


class SourceHealthListOut(BaseModel):
    items: list[SourceHealthOut]
    total: int


class RssStateOut(BaseModel):
    source_id: UUID
    etag: str | None
    last_modified: str | None
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


class TgStateOut(BaseModel):
    source_id: UUID
    channel_username: str
    channel_id: int | None
    last_message_id: int | None
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    fetched_count_last_run: int

