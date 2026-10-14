# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add the no_longer_available trigger type and the notified_retirement table

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

_OLD_VALUES = ("new_edition", "national_adoption", "rights_change")
_NEW_VALUES = (*_OLD_VALUES, "no_longer_available")
_CONSTRAINT = "notification_trigger_type"
# The constraint exists on both tables under the same name.
_TABLES = ("notification", "notified_edge")


def _in_list(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"trigger_type IN ({quoted})"


def _replace_constraint(values: tuple[str, ...]) -> None:
    # sa.Enum(native_enum=False) sizes the column to the longest value
    # (VARCHAR(17) before, VARCHAR(19) with "no_longer_available"), so the
    # column length changes together with the CHECK list.
    length = max(len(value) for value in values)
    for table in _TABLES:
        op.drop_constraint(_CONSTRAINT, table, type_="check")
        op.alter_column(
            table, "trigger_type", type_=sa.String(length), existing_nullable=False,
        )
        op.create_check_constraint(_CONSTRAINT, table, _in_list(values))


def upgrade() -> None:
    _replace_constraint(_NEW_VALUES)
    op.create_table(
        "notified_retirement",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column(
            "notified_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("notified_retirement")
    # The new value is never written to notified_edge; notification may hold it.
    op.execute("DELETE FROM notification WHERE trigger_type = 'no_longer_available'")
    _replace_constraint(_OLD_VALUES)
