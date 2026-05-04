"""add VK_GROUP source type and vk state table

Revision ID: 0011_vk_group_support
Revises: 0010_max_config
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op


revision = "0011_vk_group_support"
down_revision = "0010_max_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TYPE source_type_enum ADD VALUE IF NOT EXISTS 'VK_GROUP';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vk_groups_state (
            id UUID PRIMARY KEY,
            source_id UUID NOT NULL UNIQUE REFERENCES sources(id) ON DELETE CASCADE,
            group_id VARCHAR(128) NOT NULL,
            last_post_id INTEGER,
            last_fetch_at TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            last_error TEXT,
            fetched_count_last_run INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vk_groups_state")
