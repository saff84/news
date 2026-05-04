"""developers entity + news/source links

Revision ID: 0013_developers
Revises: 0012_vk_config
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0013_developers"
down_revision = "0012_vk_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "developers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String(length=200)), nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("region_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_developers_name", "developers", ["name"], unique=True)

    op.add_column(
        "sources",
        sa.Column("developer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("developers.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_sources_developer_id", "sources", ["developer_id"], unique=False)

    op.add_column(
        "news_items",
        sa.Column("developer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("developers.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "news_items",
        sa.Column(
            "developer_mentions",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_news_items_developer_id", "news_items", ["developer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_items_developer_id", table_name="news_items")
    op.drop_column("news_items", "developer_mentions")
    op.drop_column("news_items", "developer_id")

    op.drop_index("ix_sources_developer_id", table_name="sources")
    op.drop_column("sources", "developer_id")

    op.drop_index("ix_developers_name", table_name="developers")
    op.drop_table("developers")
