# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add account profile columns (name, avatar)

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account", sa.Column("first_name", sa.String, nullable=True))
    op.add_column("account", sa.Column("last_name", sa.String, nullable=True))
    op.add_column("account", sa.Column("avatar_image", sa.LargeBinary, nullable=True))
    op.add_column("account", sa.Column("avatar_content_type", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("account", "avatar_content_type")
    op.drop_column("account", "avatar_image")
    op.drop_column("account", "last_name")
    op.drop_column("account", "first_name")
