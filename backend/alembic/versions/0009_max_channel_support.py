"""add MAX_CHANNEL source type and max state table

Revision ID: 0009_max_channel_support
Revises: 0008_news_period_month
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op


revision = "0009_max_channel_support"
down_revision = "0008_news_period_month"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TYPE source_type_enum ADD VALUE IF NOT EXISTS 'MAX_CHANNEL';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS max_channels_state (
            id UUID PRIMARY KEY,
            source_id UUID NOT NULL UNIQUE REFERENCES sources(id) ON DELETE CASCADE,
            channel_id VARCHAR(128) NOT NULL,
            last_message_id VARCHAR(128),
            last_fetch_at TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            last_error TEXT,
            fetched_count_last_run INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS max_channels_state")
