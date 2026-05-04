"""add vk_config table for VK token

Revision ID: 0012_vk_config
Revises: 0011_vk_group_support
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op


revision = "0012_vk_config"
down_revision = "0011_vk_group_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vk_config (
            id SERIAL PRIMARY KEY,
            access_token TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO vk_config (id, access_token)
        VALUES (1, NULL)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vk_config")
