from __future__ import annotations

import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Float,
    Date,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class SourceType(str, enum.Enum):
    RSS_ATOM = "RSS_ATOM"
    HTML_LIST_DETAIL = "HTML_LIST_DETAIL"
    HTML_DETAIL_ONLY = "HTML_DETAIL_ONLY"
    SITEMAP = "SITEMAP"
    TELEGRAM_CHANNEL = "TELEGRAM_CHANNEL"
    MAX_CHANNEL = "MAX_CHANNEL"
    VK_GROUP = "VK_GROUP"


class FetchDetailPolicy(str, enum.Enum):
    ALWAYS = "ALWAYS"
    ONLY_IF_SHORT = "ONLY_IF_SHORT"
    NEVER = "NEVER"


class ImpactLabel(str, enum.Enum):
    OPPORTUNITY = "Opportunity"
    NEUTRAL = "Neutral"
    THREAT = "Threat"


class Region(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regions"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    federal_subjects: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    geographic_aliases: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Competitor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "competitors"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    region_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Developer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Застройщик: отдельно от конкурента; тегирование и отчёты по алиасам."""

    __tablename__ = "developers"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    region_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ParsingTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "parsing_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("name", "version", name="uq_parsing_templates_name_version"),)


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sources"

    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type_enum"), nullable=False, index=True)

    # One of:
    base_url: Mapped[str | None] = mapped_column(Text)
    feed_url: Mapped[str | None] = mapped_column(Text)
    tg_channel_username: Mapped[str | None] = mapped_column(String(128))

    name: Mapped[str | None] = mapped_column(String(250))

    region_tags: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="SET NULL"))
    developer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("developers.id", ondelete="SET NULL"))

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    fetch_frequency_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    respect_robots_txt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parsing_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parsing_templates.id", ondelete="SET NULL")
    )

    # Per-source extra settings (rss/tg/html): stored as json
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    competitor: Mapped[Competitor | None] = relationship()
    developer: Mapped[Developer | None] = relationship()
    parsing_template: Mapped[ParsingTemplate | None] = relationship()


Index("ix_sources_competitor_id", Source.competitor_id)
Index("ix_sources_developer_id", Source.developer_id)


class RssState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rss_state"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), unique=True)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship()


class TgChannelState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "tg_channels_state"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), unique=True)
    channel_username: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_id: Mapped[int | None] = mapped_column(Integer)
    last_message_id: Mapped[int | None] = mapped_column(Integer)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    fetched_count_last_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[Source] = relationship()


class MaxChannelState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "max_channels_state"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), unique=True)
    channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    last_message_id: Mapped[str | None] = mapped_column(String(128))
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    fetched_count_last_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[Source] = relationship()


class VkGroupState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vk_groups_state"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), unique=True)
    group_id: Mapped[str] = mapped_column(String(128), nullable=False)
    last_post_id: Mapped[int | None] = mapped_column(Integer)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    fetched_count_last_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[Source] = relationship()


class NewsItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_items"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"))
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="SET NULL"))
    developer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("developers.id", ondelete="SET NULL"))

    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    period_month: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)  # первый день месяца для отчётов

    snippet: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)

    normalized_text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    # 64-bit simhash stored as bigint
    simhash64: Mapped[int | None] = mapped_column(BigInteger, index=True)

    region_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    competitor_mentions: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    developer_mentions: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)

    raw_html_path: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source | None] = relationship()
    competitor: Mapped[Competitor | None] = relationship()
    developer: Mapped[Developer | None] = relationship()

    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_news_items_canonical_url"),
        Index("ix_news_items_source_id_published_at", "source_id", "published_at"),
    )


class NewsItemCluster(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_item_clusters"

    primary_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("news_items.id", ondelete="CASCADE"), unique=True)
    related_item_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    similarity_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # hamming dist threshold
    note: Mapped[str | None] = mapped_column(Text)

    primary_item: Mapped[NewsItem] = relationship(foreign_keys=[primary_item_id])


class IndicatorSeries(str, enum.Enum):
    HOUSING_COMMISSIONING = "HOUSING_COMMISSIONING"
    KEY_RATE = "KEY_RATE"
    CNY_RUB = "CNY_RUB"


class IndicatorMonthly(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indicators_monthly"

    series: Mapped[IndicatorSeries] = mapped_column(Enum(IndicatorSeries, name="indicator_series_enum"), nullable=False, index=True)
    period_month: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)  # normalized to 1st day
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    source_name: Mapped[str | None] = mapped_column(String(200))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("series", "period_month", name="uq_indicators_series_month"),)


class IndicatorDaily(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indicators_daily"

    series: Mapped[IndicatorSeries] = mapped_column(Enum(IndicatorSeries, name="indicator_series_enum"), nullable=False, index=True)
    period_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    source_name: Mapped[str | None] = mapped_column(String(200))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("series", "period_date", name="uq_indicators_series_date"),)


class ParsedIndicator(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "parsed_indicators"

    indicator_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(100))
    source_name: Mapped[str | None] = mapped_column(String(200))
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reports"

    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    html_path: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_by: Mapped["User | None"] = relationship("User")  # type: ignore[name-defined]

