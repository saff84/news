"""indicator telegram posts: multiple image paths

Revision ID: 0017_indicator_tg_image_paths
Revises: 0016_indicator_telegram_posts
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0017_indicator_tg_image_paths"
down_revision = "0016_indicator_telegram_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "indicator_telegram_posts",
        sa.Column("image_paths", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )
    op.execute(
        "UPDATE indicator_telegram_posts "
        "SET image_paths = ARRAY[image_path] "
        "WHERE image_path IS NOT NULL AND image_path <> ''"
    )


def downgrade() -> None:
    op.drop_column("indicator_telegram_posts", "image_paths")
