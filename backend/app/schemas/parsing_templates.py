from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ParsingTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(default=1, ge=1, le=10_000)
    template_json: dict = Field(default_factory=dict)
    is_active: bool = True


class ParsingTemplateCreate(ParsingTemplateBase):
    pass


class ParsingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1, le=10_000)
    template_json: dict | None = None
    is_active: bool | None = None


class ParsingTemplateOut(ParsingTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ParsingTemplateListOut(BaseModel):
    items: list[ParsingTemplateOut]
    total: int

