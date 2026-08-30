# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add email_change to account_token_purpose

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-29
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_OLD_VALUES = ("password_reset", "email_verification", "magic_link")
_NEW_VALUES = _OLD_VALUES + ("email_change",)


def _values_sql(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"purpose IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint("account_token_purpose", "account_token", type_="check")
    op.create_check_constraint(
        "account_token_purpose", "account_token", _values_sql(_NEW_VALUES)
    )


def downgrade() -> None:
    op.drop_constraint("account_token_purpose", "account_token", type_="check")
    op.create_check_constraint(
        "account_token_purpose", "account_token", _values_sql(_OLD_VALUES)
    )
