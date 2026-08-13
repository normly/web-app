# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create edge table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "to_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
        ),
        sa.Column(
            "edge_type",
            sa.Enum(
                "references",
                "replaces",
                "withdrawn_by",
                "based_on_law",
                "adopted_from",
                name="edge_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String, nullable=True),
        sa.Column(
            "layer",
            sa.Enum("free", "commercial", name="layer", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_edge_active_from_to_type_jurisdiction",
        "edge",
        [
            "from_document_id",
            "to_document_id",
            "edge_type",
            sa.text("coalesce(jurisdiction, '')"),
        ],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_edge_active_from_to_type_jurisdiction", table_name="edge")
    op.drop_table("edge")
