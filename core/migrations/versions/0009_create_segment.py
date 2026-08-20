# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create segment table

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "segment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("heading", sa.String, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("language", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id", "sequence_number", name="uq_segment_document_sequence"
        ),
    )


def downgrade() -> None:
    op.drop_table("segment")
