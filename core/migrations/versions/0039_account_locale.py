# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add account.locale

The language an account's emails are written in. Job-triggered mails
(Normtracker, deletion warning) have no request to take a language from, so
it is stored. Existing accounts keep NULL: their language is unknown, and the
deletion warning then goes out in German and English.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = language unknown (account created before it was stored); a CHECK
    # passes NULL.
    op.add_column("account", sa.Column("locale", sa.String(2), nullable=True))
    op.create_check_constraint("ck_account_locale", "account", "locale IN ('de', 'en')")


def downgrade() -> None:
    op.drop_constraint("ck_account_locale", "account", type_="check")
    op.drop_column("account", "locale")
