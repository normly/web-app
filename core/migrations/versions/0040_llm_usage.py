# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add LLM cost-cap counters

Token usage per cost pool and UTC day, AI answers per caller and day, and the
dedup record of sent budget alerts (issue #40).

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_token_usage",
        sa.Column("pool", sa.String(16), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("pool IN ('anonymous', 'registered')", name="ck_llm_token_usage_pool"),
    )
    op.create_table(
        "llm_question_count",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("question_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_llm_question_count_day", "llm_question_count", ["day"])
    op.create_table(
        "llm_budget_alert",
        sa.Column("pool", sa.String(16), primary_key=True),
        sa.Column("period", sa.String(10), primary_key=True),
        sa.Column("threshold", sa.Integer, primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_budget_alert")
    op.drop_index("ix_llm_question_count_day", table_name="llm_question_count")
    op.drop_table("llm_question_count")
    op.drop_table("llm_token_usage")
