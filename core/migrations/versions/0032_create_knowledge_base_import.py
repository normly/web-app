# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create knowledge_base_import

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_import",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dump_version", sa.String, nullable=False),
        sa.Column("exchange_schema_version", sa.Integer, nullable=False),
        sa.Column("embedding_model_revision", sa.String, nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_knowledge_base_import_single_row"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_base_import")
