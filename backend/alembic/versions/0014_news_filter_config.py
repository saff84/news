"""news_filter_config — global minus/plus keywords

Revision ID: 0014_news_filter_config
Revises: 0013_developers
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op


revision = "0014_news_filter_config"
down_revision = "0013_developers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS news_filter_config (
            id SERIAL PRIMARY KEY,
            settings_json JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        INSERT INTO news_filter_config (id, settings_json)
        SELECT 1, '{}'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM news_filter_config WHERE id = 1)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS news_filter_config")
