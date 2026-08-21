# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""let an account_token address an email that has no account yet

The magic-link flow is a registration path as well as a login path, and the
design spec puts account creation at the `confirm` step: creating it at
`request` time would let anyone conjure an account for any address they can
type, without ever proving they can read that mailbox.

That needs a token that names an email rather than an account. `account_id`
therefore becomes nullable and a nullable `email` column joins it, with a check
constraint keeping exactly one of the two set — a token is bound either to an
existing account or to an address awaiting one, never to both (which would
raise the question of which wins when they disagree) and never to neither.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_ACCOUNT_OR_EMAIL = "(account_id IS NULL) != (email IS NULL)"


def upgrade() -> None:
    op.add_column("account_token", sa.Column("email", sa.String, nullable=True))
    op.alter_column("account_token", "account_id", nullable=True)
    op.create_check_constraint(
        "ck_account_token_account_or_email", "account_token", _ACCOUNT_OR_EMAIL
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_account_token_account_or_email", "account_token", type_="check"
    )
    # Email-bound tokens have no representation in the old shape, and inventing
    # an account for them on the way down would create exactly the accounts this
    # migration exists to avoid. They are short-lived one-time tokens, so
    # discarding them costs a user one retry of the magic-link request.
    op.execute(sa.text("DELETE FROM account_token WHERE account_id IS NULL"))
    op.alter_column("account_token", "account_id", nullable=False)
    op.drop_column("account_token", "email")
