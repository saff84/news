from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeveloperBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    region_ids: list[UUID] = Field(default_factory=list)
    is_active: bool = True


class DeveloperCreate(DeveloperBase):
    pass


class DeveloperUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    tags: list[str] | None = None
    region_ids: list[UUID] | None = None
    is_active: bool | None = None


class DeveloperOut(DeveloperBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class DeveloperListOut(BaseModel):
    items: list[DeveloperOut]
    total: int
