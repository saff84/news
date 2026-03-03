"""domain schema (regions, sources, items, reports, indicators)

Revision ID: 0002_domain_schema
Revises: 0001_init_auth
Create Date: 2026-02-10

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_domain_schema"
down_revision = "0001_init_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source_type_enum = postgresql.ENUM(
        "RSS_ATOM",
        "HTML_LIST_DETAIL",
        "HTML_DETAIL_ONLY",
        "SITEMAP",
        "TELEGRAM_CHANNEL",
        name="source_type_enum",
    )
    indicator_series_enum = postgresql.ENUM(
        "HOUSING_COMMISSIONING",
        "KEY_RATE",
        "CNY_RUB",
        name="indicator_series_enum",
    )
    source_type_enum.create(op.get_bind(), checkfirst=True)
    indicator_series_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("federal_subjects", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("keywords", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("geographic_aliases", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_regions_name", "regions", ["name"], unique=True)

    op.create_table(
        "competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String(length=200)), nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("region_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_competitors_name", "competitors", ["name"], unique=True)

    op.create_table(
        "parsing_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("template_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_parsing_templates_name_version"),
    )

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "RSS_ATOM",
                "HTML_LIST_DETAIL",
                "HTML_DETAIL_ONLY",
                "SITEMAP",
                "TELEGRAM_CHANNEL",
                name="source_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("feed_url", sa.Text(), nullable=True),
        sa.Column("tg_channel_username", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=250), nullable=True),
        sa.Column("region_tags", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fetch_frequency_min", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delay_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_requests_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("respect_robots_txt", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "parsing_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parsing_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sources_source_type", "sources", ["source_type"], unique=False)
    op.create_index("ix_sources_enabled", "sources", ["enabled"], unique=False)
    op.create_index("ix_sources_priority", "sources", ["priority"], unique=False)
    op.create_index("ix_sources_backoff_until", "sources", ["backoff_until"], unique=False)
    op.create_index("ix_sources_competitor_id", "sources", ["competitor_id"], unique=False)

    op.create_table(
        "rss_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("etag", sa.String(length=500), nullable=True),
        sa.Column("last_modified", sa.String(length=500), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_id", name="uq_rss_state_source_id"),
    )

    op.create_table(
        "tg_channels_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_username", sa.String(length=128), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("last_message_id", sa.Integer(), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("fetched_count_last_run", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("source_id", name="uq_tg_channels_state_source_id"),
    )

    op.create_table(
        "news_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "competitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("competitors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("normalized_text_hash", sa.String(length=64), nullable=True),
        sa.Column("simhash64", sa.BigInteger(), nullable=True),
        sa.Column("region_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("topic_tags", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("competitor_mentions", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("raw_html_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("canonical_url", name="uq_news_items_canonical_url"),
    )
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"], unique=False)
    op.create_index("ix_news_items_normalized_text_hash", "news_items", ["normalized_text_hash"], unique=False)
    op.create_index("ix_news_items_simhash64", "news_items", ["simhash64"], unique=False)
    op.create_index("ix_news_items_source_id_published_at", "news_items", ["source_id", "published_at"], unique=False)

    op.create_table(
        "news_item_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("primary_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("news_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("related_item_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("similarity_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("primary_item_id", name="uq_news_item_clusters_primary_item_id"),
    )

    op.create_table(
        "indicators_monthly",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "series",
            postgresql.ENUM(
                "HOUSING_COMMISSIONING",
                "KEY_RATE",
                "CNY_RUB",
                name="indicator_series_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("period_month", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("series", "period_month", name="uq_indicators_series_month"),
    )
    op.create_index("ix_indicators_monthly_series", "indicators_monthly", ["series"], unique=False)
    op.create_index("ix_indicators_monthly_period_month", "indicators_monthly", ["period_month"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("html_path", sa.Text(), nullable=False),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reports_date_from", "reports", ["date_from"], unique=False)
    op.create_index("ix_reports_date_to", "reports", ["date_to"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reports_date_to", table_name="reports")
    op.drop_index("ix_reports_date_from", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_indicators_monthly_period_month", table_name="indicators_monthly")
    op.drop_index("ix_indicators_monthly_series", table_name="indicators_monthly")
    op.drop_table("indicators_monthly")

    op.drop_table("news_item_clusters")

    op.drop_index("ix_news_items_source_id_published_at", table_name="news_items")
    op.drop_index("ix_news_items_simhash64", table_name="news_items")
    op.drop_index("ix_news_items_normalized_text_hash", table_name="news_items")
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_table("news_items")

    op.drop_table("tg_channels_state")
    op.drop_table("rss_state")

    op.drop_index("ix_sources_competitor_id", table_name="sources")
    op.drop_index("ix_sources_backoff_until", table_name="sources")
    op.drop_index("ix_sources_priority", table_name="sources")
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_index("ix_sources_source_type", table_name="sources")
    op.drop_table("sources")

    op.drop_table("parsing_templates")
    op.drop_table("competitors")
    op.drop_index("ix_regions_name", table_name="regions")
    op.drop_table("regions")

    indicator_series_enum = postgresql.ENUM(
        "HOUSING_COMMISSIONING",
        "KEY_RATE",
        "CNY_RUB",
        name="indicator_series_enum",
    )
    source_type_enum = postgresql.ENUM(
        "RSS_ATOM",
        "HTML_LIST_DETAIL",
        "HTML_DETAIL_ONLY",
        "SITEMAP",
        "TELEGRAM_CHANNEL",
        name="source_type_enum",
    )
    indicator_series_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
