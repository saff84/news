"""add telegram_config for UI-managed credentials

Revision ID: 0005_telegram_config
Revises: 0004_parsed_indicators
Create Date: 2026-03-04

"""

from __future__ import annotations

from alembic import op


revision = "0005_telegram_config"
down_revision = "0004_parsed_indicators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS telegram_config (
            id SERIAL PRIMARY KEY,
            api_id INTEGER,
            api_hash VARCHAR(100),
            session_string TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        INSERT INTO telegram_config (id, api_id, api_hash, session_string)
        VALUES (1, NULL, NULL, NULL)
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telegram_config")
