"""competitor telegram profiles, posts, summaries

Revision ID: 0018_competitor_telegram
Revises: 0017_indicator_tg_image_paths
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_competitor_telegram"
down_revision = "0017_indicator_tg_image_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitor_telegram_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tg_channel_username", sa.String(128), nullable=False),
        sa.Column("include_keywords", postgresql.ARRAY(sa.String(200)), nullable=False, server_default="{}"),
        sa.Column("exclude_keywords", postgresql.ARRAY(sa.String(200)), nullable=False, server_default="{}"),
        sa.Column("match_whole_words", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("backfill_until_date", sa.Date(), nullable=True),
        sa.Column("last_message_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("backfill_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("backfill_cursor_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("competitor_id", name="uq_competitor_tg_profiles_competitor"),
    )
    op.create_index("ix_competitor_tg_profiles_competitor_id", "competitor_telegram_profiles", ["competitor_id"])

    op.create_table(
        "competitor_telegram_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("competitor_telegram_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("post_url", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("profile_id", "message_id", name="uq_competitor_tg_posts_profile_message"),
    )
    op.create_index("ix_competitor_telegram_posts_profile_id", "competitor_telegram_posts", ["profile_id"])
    op.create_index("ix_competitor_telegram_posts_published_at", "competitor_telegram_posts", ["published_at"])

    op.create_table(
        "competitor_telegram_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("competitor_telegram_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("posts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_competitor_tg_summaries_profile_id", "competitor_telegram_summaries", ["profile_id"])
    op.create_index("ix_competitor_tg_summaries_status", "competitor_telegram_summaries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_competitor_tg_summaries_status", table_name="competitor_telegram_summaries")
    op.drop_index("ix_competitor_tg_summaries_profile_id", table_name="competitor_telegram_summaries")
    op.drop_table("competitor_telegram_summaries")
    op.drop_index("ix_competitor_telegram_posts_published_at", table_name="competitor_telegram_posts")
    op.drop_index("ix_competitor_telegram_posts_profile_id", table_name="competitor_telegram_posts")
    op.drop_table("competitor_telegram_posts")
    op.drop_index("ix_competitor_tg_profiles_competitor_id", table_name="competitor_telegram_profiles")
    op.drop_table("competitor_telegram_profiles")
