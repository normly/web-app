# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

NOW = datetime.now(timezone.utc)


def test_find_unconsumed_token_ignores_used_expired_and_other_purposes(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="lookup@example.de", password_hash=None
    )
    tokens = PostgresAccountTokenRepository(db_session)
    tokens.create_token(account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK,
                        token="live", created_at=NOW, expires_at=NOW + timedelta(minutes=5))
    tokens.create_token(account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK,
                        token="old", created_at=NOW, expires_at=NOW - timedelta(minutes=1))

    found = tokens.find_unconsumed_token("live", AccountTokenPurpose.MAGIC_LINK)
    assert found is not None and found.account_id == account.id
    assert tokens.find_unconsumed_token("live", AccountTokenPurpose.PASSWORD_RESET) is None
    assert tokens.find_unconsumed_token("old", AccountTokenPurpose.MAGIC_LINK) is None
    tokens.consume_token("live", AccountTokenPurpose.MAGIC_LINK)
    assert tokens.find_unconsumed_token("live", AccountTokenPurpose.MAGIC_LINK) is None
