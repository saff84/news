"""add report_config for PDF export settings

Revision ID: 0006_report_config
Revises: 0005_telegram_config
Create Date: 2026-03-05

"""

from __future__ import annotations

from alembic import op


revision = "0006_report_config"
down_revision = "0005_telegram_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_config (
            id SERIAL PRIMARY KEY,
            settings_json JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        INSERT INTO report_config (id, settings_json)
        VALUES (1, '{}')
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_config")
