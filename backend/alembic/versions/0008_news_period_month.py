"""add period_month to news_items for monthly report filtering

Revision ID: 0008_news_period_month
Revises: 0007_ai_config
Create Date: 2026-03-05

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_news_period_month"
down_revision = "0007_ai_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: skip if column already exists (e.g. partial previous run)
    conn = op.get_bind()
    r = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name='news_items' AND column_name='period_month'"
    )).scalar()
    if not r:
        op.add_column("news_items", sa.Column("period_month", sa.Date(), nullable=True))
        op.create_index("ix_news_items_period_month", "news_items", ["period_month"], unique=False)
    # Backfill: period_month = first day of month from published_at or created_at
    op.execute(sa.text("""
        UPDATE news_items
        SET period_month = (DATE_TRUNC('month', COALESCE(published_at AT TIME ZONE 'UTC', created_at AT TIME ZONE 'UTC')))::date
        WHERE period_month IS NULL AND (published_at IS NOT NULL OR created_at IS NOT NULL)
    """))


def downgrade() -> None:
    op.drop_index("ix_news_items_period_month", table_name="news_items")
    op.drop_column("news_items", "period_month")
