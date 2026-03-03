from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class TemplateTestRequest(BaseModel):
    url: HttpUrl
    template_json: dict = Field(default_factory=dict)


class TemplateTestResult(BaseModel):
    url: str
    title: str | None
    author: str | None
    published_at_raw: str | None
    published_at: str | None
    body_text_preview: str | None
    body_text_length: int

