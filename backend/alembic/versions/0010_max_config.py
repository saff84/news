"""add max_config table for MAX bot token

Revision ID: 0010_max_config
Revises: 0009_max_channel_support
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op


revision = "0010_max_config"
down_revision = "0009_max_channel_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS max_config (
            id SERIAL PRIMARY KEY,
            bot_token TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO max_config (id, bot_token)
        VALUES (1, NULL)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS max_config")
