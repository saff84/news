from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    source_type: str
    name: str | None = Field(default=None, max_length=250)

    base_url: str | None = None
    feed_url: str | None = None
    tg_channel_username: str | None = Field(default=None, max_length=128)

    region_tags: list[UUID] = Field(default_factory=list)
    competitor_id: UUID | None = None

    enabled: bool = True
    fetch_frequency_min: int = Field(default=60, ge=1, le=7 * 24 * 60)
    priority: int = Field(default=0, ge=-1000, le=1000)

    delay_ms: int = Field(default=0, ge=0, le=60_000)
    max_requests_per_minute: int = Field(default=60, ge=1, le=10_000)
    retries: int = Field(default=3, ge=0, le=20)

    respect_robots_txt: bool = False
    parsing_template_id: UUID | None = None
    settings_json: dict = Field(default_factory=dict)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    source_type: str | None = None
    name: str | None = Field(default=None, max_length=250)
    base_url: str | None = None
    feed_url: str | None = None
    tg_channel_username: str | None = Field(default=None, max_length=128)
    region_tags: list[UUID] | None = None
    competitor_id: UUID | None = None
    enabled: bool | None = None
    fetch_frequency_min: int | None = Field(default=None, ge=1, le=7 * 24 * 60)
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    delay_ms: int | None = Field(default=None, ge=0, le=60_000)
    max_requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    retries: int | None = Field(default=None, ge=0, le=20)
    respect_robots_txt: bool | None = None
    parsing_template_id: UUID | None = None
    settings_json: dict | None = None


class SourceOut(SourceBase):
    id: UUID
    last_fetch_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    backoff_until: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceListOut(BaseModel):
    items: list[SourceOut]
    total: int

