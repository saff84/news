"""Структурированный вывод ИИ для отчётов (последующий рендер HTML/PDF)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReportCitation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", description="Текст ссылки")
    url: str = Field(default="", description="URL из входных данных")


class ReportBullet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    citations: list[ReportCitation] = Field(default_factory=list)


class ReportSubsection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[ReportBullet] = Field(default_factory=list)


class ReportSectionPayload(BaseModel):
    """
    Единая схема секции отчёта (конкурент, застройщик, регион, общие новости, кластеры, индикаторы).
    Поля опциональны: заполняйте только релевантные.
    """

    model_config = ConfigDict(extra="ignore")

    headline: str | None = None
    lead: str | None = None
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[ReportBullet] = Field(default_factory=list)
    subsections: list[ReportSubsection] = Field(default_factory=list)
    closing: str | None = None


REPORT_SECTION_JSON_INSTRUCTION = """
ОБЯЗАТЕЛЬНО: ответь ТОЛЬКО одним JSON-объектом (без markdown-ограждений ```, без текста до/после).
Схема (все ключи опциональны, кроме что должен быть непустой объект):
{
  "headline": "краткий заголовок секции или null",
  "lead": "вводный абзац или null",
  "paragraphs": ["абзац 1", "абзац 2"],
  "bullets": [
    {
      "text": "формулировка тезиса",
      "citations": [{"label": "краткий текст ссылки", "url": "https://..."}]
    }
  ],
  "subsections": [
    {
      "title": "название тематического раздела",
      "paragraphs": ["аналитический абзац раздела"],
      "bullets": [
        {
          "text": "конкретный факт",
          "citations": [{"label": "краткий текст", "url": "https://..."}]
        }
      ]
    }
  ],
  "closing": "итоговая мысль или null"
}
Правила: в citations.url используй ТОЛЬКО URL из блока «Данные» выше; не выдумывай ссылки.
"""

COMPETITOR_TG_SYNTHESIS_JSON_INSTRUCTION = """
ОБЯЗАТЕЛЬНО: ответь ТОЛЬКО одним JSON-объектом (без ``` и текста вокруг).
Минимальный объём: lead ≥ 5 предложений; каждый subsection — ≥ 2 paragraphs по 3–5 предложений + bullets с фактами.
Заголовки subsections — ТОЛЬКО тематические («Продукт и ассортимент», «Маркетинг и продажи»…), ЗАПРЕЩЕНЫ даты и диапазоны («2024-08-17 — 2025-12-24»).
Схема:
{
  "headline": "конкурент + период",
  "lead": "развёрнутая стратегическая картина",
  "subsections": [
    {
      "title": "тема",
      "paragraphs": ["аналитика", "интерпретация трендов"],
      "bullets": [{"text": "факт", "citations": [{"label": "...", "url": "..."}]}]
    }
  ],
  "closing": "вывод + что мониторить"
}
"""
