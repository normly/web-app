# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create identity_resolution_case table

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_resolution_case",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("raw_designation", sa.String, nullable=False),
        sa.Column("raw_issuer", sa.String, nullable=True),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "resolved", "rejected",
                name="identity_resolution_status", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "resolved_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("identity_resolution_case")
