# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""bind the pending address to the e-mail change token

The confirm step used to take the new address from the link's query string,
unbound to the token, so a signed-in person could move their account to any
free address without controlling that mailbox. An `email_change` token now
carries both the account and the pending address; every other purpose keeps
"exactly one of account_id and email" (0014). An `email_change` token without
an address (issued before this revision) stays valid in shape and is refused
by the confirm endpoint.

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

_NAME = "ck_account_token_account_or_email"
_OLD = "(account_id IS NULL) != (email IS NULL)"
_NEW = (
    "(purpose = 'email_change' AND account_id IS NOT NULL)"
    " OR (purpose <> 'email_change' AND (account_id IS NULL) != (email IS NULL))"
)


def upgrade() -> None:
    op.drop_constraint(_NAME, "account_token", type_="check")
    op.create_check_constraint(_NAME, "account_token", _NEW)


def downgrade() -> None:
    # A token bound to both has no shape in the old constraint. They are
    # short-lived; the person requests the change again.
    op.execute(sa.text(
        "DELETE FROM account_token WHERE purpose = 'email_change' "
        "AND account_id IS NOT NULL AND email IS NOT NULL"
    ))
    op.drop_constraint(_NAME, "account_token", type_="check")
    op.create_check_constraint(_NAME, "account_token", _OLD)
