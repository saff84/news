from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegionBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    federal_subjects: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    geographic_aliases: list[str] = Field(default_factory=list)
    is_active: bool = True


class RegionCreate(RegionBase):
    pass


class RegionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    federal_subjects: list[str] | None = None
    keywords: list[str] | None = None
    geographic_aliases: list[str] | None = None
    is_active: bool | None = None


class RegionOut(RegionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class RegionListOut(BaseModel):
    items: list[RegionOut]
    total: int

