from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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


class MonitoringAlertOut(BaseModel):
    id: str
    severity: str  # info|warning|critical
    code: str
    message: str
    source_id: UUID | None = None
    source_label: str | None = None
    meta: dict = Field(default_factory=dict)


class MonitoringAlertsOut(BaseModel):
    generated_at: datetime
    critical_count: int
    warning_count: int
    info_count: int
    items: list[MonitoringAlertOut]


class SourceCrawlScheduleOut(BaseModel):
    id: UUID
    source_type: str
    name: str | None
    display_label: str
    enabled: bool
    fetch_frequency_min: int
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    backoff_until: datetime | None
    is_due: bool
    next_expected_enqueue_at: datetime | None


class SourceCrawlScheduleListOut(BaseModel):
    server_now: datetime
    items: list[SourceCrawlScheduleOut]
    due_count: int


class EnqueueDueOut(BaseModel):
    enqueued: int


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


class MaxStateOut(BaseModel):
    source_id: UUID
    channel_id: str
    last_message_id: str | None
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    fetched_count_last_run: int


class VkStateOut(BaseModel):
    source_id: UUID
    group_id: str
    last_post_id: int | None
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    fetched_count_last_run: int

