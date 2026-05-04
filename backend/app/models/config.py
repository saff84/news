"""System configuration models (DB-stored, not env)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TelegramConfig(Base):
    """Single-row table for Telegram parser credentials (UI-managed)."""

    __tablename__ = "telegram_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MaxConfig(Base):
    """Single-row table for MAX Bot API token."""

    __tablename__ = "max_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VkConfig(Base):
    """Single-row table for VK API access token."""

    __tablename__ = "vk_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportConfig(Base):
    """Single-row table for PDF report settings (header, footer, sections)."""

    __tablename__ = "report_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AIConfig(Base):
    """Single-row table for AI processing prompts per data type."""

    __tablename__ = "ai_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
