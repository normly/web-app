# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create notified_edge table, index notification.created_at

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notified_edge",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "new_edition", "national_adoption", "rights_change",
                name="notification_trigger_type",
                native_enum=False,
                create_constraint=True,
            ),
            primary_key=True,
        ),
        sa.Column(
            "trigger_edge_id", UUID(as_uuid=True), sa.ForeignKey("edge.id"), primary_key=True,
        ),
        sa.Column(
            "notified_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # cleanup-notifications (Task 2) filters on both columns; without this,
    # every run is a full table scan of a table the design spec expects to
    # grow without bound between cleanups.
    op.create_index("ix_notification_created_at", "notification", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_created_at", table_name="notification")
    op.drop_table("notified_edge")
