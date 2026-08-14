# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("origin_issuer", sa.String, nullable=False),
        sa.Column("origin_number", sa.String, nullable=False),
        sa.Column("edition", sa.String, nullable=False),
        sa.Column("part", sa.String, nullable=True),
        sa.Column(
            "created_via_delivery_id",
            UUID(as_uuid=True),
            sa.ForeignKey("delivery.id"),
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
    op.drop_table("document")
