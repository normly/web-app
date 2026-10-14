# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add retired_at to work, document and edge

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

_TABLES = ("work", "document", "edge")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "retired_at")
