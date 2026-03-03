"""add parsed_indicators for imported table data

Revision ID: 0004_parsed_indicators
Revises: 0003_indicators_daily
Create Date: 2026-02-23

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_parsed_indicators"
down_revision = "0003_indicators_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parsed_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("indicator_name", sa.String(length=500), nullable=False),
        sa.Column("period", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_parsed_indicators_indicator_name", "parsed_indicators", ["indicator_name"], unique=False)
    op.create_index("ix_parsed_indicators_period", "parsed_indicators", ["period"], unique=False)
    op.create_index("ix_parsed_indicators_import_batch_id", "parsed_indicators", ["import_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_parsed_indicators_import_batch_id", table_name="parsed_indicators")
    op.drop_index("ix_parsed_indicators_period", table_name="parsed_indicators")
    op.drop_index("ix_parsed_indicators_indicator_name", table_name="parsed_indicators")
    op.drop_table("parsed_indicators")
