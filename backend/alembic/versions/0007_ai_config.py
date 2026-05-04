"""add ai_config for AI processing prompts per data type

Revision ID: 0007_ai_config
Revises: 0006_report_config
Create Date: 2026-03-05

"""

from __future__ import annotations

from alembic import op


revision = "0007_ai_config"
down_revision = "0006_report_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_config (
            id SERIAL PRIMARY KEY,
            settings_json JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        INSERT INTO ai_config (id, settings_json)
        SELECT 1, '{}'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM ai_config WHERE id = 1)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_config")
