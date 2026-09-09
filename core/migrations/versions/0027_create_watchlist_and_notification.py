# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create watchlist and notification tables, add account.notification_preference

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column(
            "notification_preference",
            sa.Enum(
                "none", "in_app", "email", "both",
                name="notification_preference",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="none",
        ),
    )

    op.create_table(
        "watchlist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "work_id", name="uq_watchlist_account_work"),
    )

    op.create_table(
        "notification",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "new_edition", "national_adoption", "rights_change",
                name="notification_trigger_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("trigger_edge_id", UUID(as_uuid=True), sa.ForeignKey("edge.id"), nullable=True),
        sa.Column(
            "trigger_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"),
            nullable=True,
        ),
        sa.Column("trigger_jurisdiction", sa.String, nullable=True),
        sa.Column("may_process", sa.Boolean, nullable=True),
        sa.Column("may_index_fulltext", sa.Boolean, nullable=True),
        sa.Column("may_cite_passages", sa.Boolean, nullable=True),
        sa.Column("may_export_free", sa.Boolean, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "account_id", "work_id", "trigger_type", "trigger_edge_id",
            name="uq_notification_account_work_trigger_edge",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification")
    op.drop_table("watchlist")
    op.drop_column("account", "notification_preference")
