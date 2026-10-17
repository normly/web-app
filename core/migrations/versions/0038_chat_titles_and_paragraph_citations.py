# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add chat_session.title and chat_message_citation.paragraph_index

title holds the model-generated session title; NULL means none was generated
and the reader falls back to the first question. paragraph_index ties a
citation to one paragraph of its answer; NULL means the whole answer (the
fallback when the model set no source markers, and every citation written
before this revision).

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_session", sa.Column("title", sa.String(), nullable=True))
    op.add_column(
        "chat_message_citation", sa.Column("paragraph_index", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_message_citation", "paragraph_index")
    op.drop_column("chat_session", "title")
