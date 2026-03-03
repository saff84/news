"""add indicators_daily for daily series (MOEX)

Revision ID: 0003_indicators_daily
Revises: 0002_domain_schema
Create Date: 2026-02-23

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_indicators_daily"
down_revision = "0002_domain_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicators_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "series",
            postgresql.ENUM(
                "HOUSING_COMMISSIONING",
                "KEY_RATE",
                "CNY_RUB",
                name="indicator_series_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("series", "period_date", name="uq_indicators_series_date"),
    )
    op.create_index("ix_indicators_daily_series", "indicators_daily", ["series"], unique=False)
    op.create_index("ix_indicators_daily_period_date", "indicators_daily", ["period_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_indicators_daily_period_date", table_name="indicators_daily")
    op.drop_index("ix_indicators_daily_series", table_name="indicators_daily")
    op.drop_table("indicators_daily")

