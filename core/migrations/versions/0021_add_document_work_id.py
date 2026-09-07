# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add nullable document.work_id column

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document",
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document", "work_id")
