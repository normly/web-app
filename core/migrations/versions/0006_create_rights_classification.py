# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create rights_classification table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_classification",
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True
        ),
        sa.Column("jurisdiction", sa.String, primary_key=True),
        sa.Column("may_process", sa.Boolean, nullable=False),
        sa.Column("may_index_fulltext", sa.Boolean, nullable=False),
        sa.Column("may_cite_passages", sa.Boolean, nullable=False),
        sa.Column("may_export_free", sa.Boolean, nullable=False),
        sa.Column("legal_basis_reference", sa.String, nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("classified_by", sa.String, nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rights_classification")
