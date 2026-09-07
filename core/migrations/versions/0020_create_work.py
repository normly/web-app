# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create work table

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            sa.Enum(
                "active", "merged",
                name="work_status", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "merged_into_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True,
        ),
        sa.Column(
            "created_via",
            sa.Enum(
                "auto_matched", "manual",
                name="work_created_via", native_enum=False, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("work")
