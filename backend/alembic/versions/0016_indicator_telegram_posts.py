"""indicator telegram posts and config

Revision ID: 0016_indicator_telegram_posts
Revises: 0015_tg_channel_bigint
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_indicator_telegram_posts"
down_revision = "0015_tg_channel_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicator_telegram_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel_username", sa.String(128), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("post_url", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_keywords", postgresql.ARRAY(sa.String(120)), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("channel_username", "message_id", name="uq_indicator_tg_posts_channel_message"),
    )
    op.create_index("ix_indicator_telegram_posts_published_at", "indicator_telegram_posts", ["published_at"])

    op.create_table(
        "indicator_telegram_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settings_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute(
        "INSERT INTO indicator_telegram_config (id, settings_json) "
        "SELECT 1, '{}' WHERE NOT EXISTS (SELECT 1 FROM indicator_telegram_config WHERE id = 1)"
    )


def downgrade() -> None:
    op.drop_table("indicator_telegram_config")
    op.drop_index("ix_indicator_telegram_posts_published_at", table_name="indicator_telegram_posts")
    op.drop_table("indicator_telegram_posts")
