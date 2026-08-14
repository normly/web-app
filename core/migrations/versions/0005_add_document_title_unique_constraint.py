# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add unique constraint to document_title

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_title_document_language_title",
        "document_title",
        ["document_id", "language", "title"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_title_document_language_title", "document_title")
