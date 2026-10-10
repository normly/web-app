# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create the deletion_log table

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deletion_log",
        sa.Column("kind", sa.String(12), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('account', 'chat_session')", name="deletion_log_kind"),
    )
    op.create_index("ix_deletion_log_deleted_at", "deletion_log", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_deletion_log_deleted_at", table_name="deletion_log")
    op.drop_table("deletion_log")
