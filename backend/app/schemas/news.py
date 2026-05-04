from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NewsItemOut(BaseModel):
    id: UUID
    source_id: UUID | None
    source_name: str | None = None
    competitor_id: UUID | None
    developer_id: UUID | None = None
    url: str
    canonical_url: str
    title: str | None
    author: str | None
    published_at: datetime | None
    snippet: str | None
    content_text: str | None
    region_ids: list[UUID] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    competitor_mentions: list[UUID] = Field(default_factory=list)
    competitor_mentions_names: list[str] = Field(default_factory=list)  # названия конкурентов для отображения тегов
    developer_mentions: list[UUID] = Field(default_factory=list)
    developer_mentions_names: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NewsItemListOut(BaseModel):
    items: list[NewsItemOut]
    total: int
