# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""make document.work_id not null

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-06
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document", "work_id", nullable=False)


def downgrade() -> None:
    op.alter_column("document", "work_id", nullable=True)
