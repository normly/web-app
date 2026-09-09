# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create rights_notification_baseline table

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_notification_baseline",
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True,
        ),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True),
        sa.Column(
            "trigger_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"),
            primary_key=True,
        ),
        sa.Column("trigger_jurisdiction", sa.String, primary_key=True),
        sa.Column("may_process", sa.Boolean, nullable=False),
        sa.Column("may_index_fulltext", sa.Boolean, nullable=False),
        sa.Column("may_cite_passages", sa.Boolean, nullable=False),
        sa.Column("may_export_free", sa.Boolean, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("rights_notification_baseline")
