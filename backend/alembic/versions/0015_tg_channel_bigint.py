"""tg_channels_state channel_id and last_message_id as BIGINT

Revision ID: 0015_tg_channel_bigint
Revises: 0014_news_filter_config
Create Date: 2026-05-27
"""

from __future__ import annotations

from alembic import op


revision = "0015_tg_channel_bigint"
down_revision = "0014_news_filter_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tg_channels_state
            ALTER COLUMN channel_id TYPE BIGINT,
            ALTER COLUMN last_message_id TYPE BIGINT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE tg_channels_state
            ALTER COLUMN channel_id TYPE INTEGER,
            ALTER COLUMN last_message_id TYPE INTEGER
        """
    )
