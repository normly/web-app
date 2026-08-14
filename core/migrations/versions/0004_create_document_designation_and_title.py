# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document_designation and document_title tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_designation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column("issuer", sa.String, nullable=False),
        sa.Column("designation", sa.String, nullable=False),
        sa.Column("language", sa.String, nullable=False),
        sa.Column("edition", sa.String, nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
    )
    op.create_table(
        "document_title",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column("language", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("document_title")
    op.drop_table("document_designation")
