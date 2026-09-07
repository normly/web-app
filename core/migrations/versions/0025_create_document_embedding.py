# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create document_embedding table

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_embedding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True),
            sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("vector", Vector(1024), nullable=False),
        sa.Column(
            "delivery_id", UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id", "model_name", name="uq_document_embedding_document_model"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_embedding")
