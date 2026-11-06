# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import pytest

from normly_core.admin import AdminGrantError, grant_administrator
from normly_core.graph.domain import AdminAction, BlockReason, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def test_grant_sets_the_role_clears_a_binding_and_is_idempotent(db_session):
    accounts = PostgresAccountRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(name="DIN Media", created_at=NOW)
    account = accounts.create_account(email="first-admin@example.de", password_hash=None)
    accounts.set_role(account.id, role=Role.PUBLISHER, publisher_id=publisher.id)

    assert grant_administrator(db_session, email="first-admin@example.de", now=NOW) == "granted"
    assert grant_administrator(db_session, email="first-admin@example.de", now=NOW) == "unchanged"

    granted = accounts.get_account_by_id(account.id)
    assert (granted.role, granted.publisher_id) == (Role.ADMINISTRATOR, None)
    [entry] = PostgresAdminAuditRepository(db_session).list_for_target_account(account.id)
    assert (entry.action, entry.actor_account_id) == (AdminAction.ADMINISTRATOR_GRANTED_CLI, None)


def test_grant_refuses_unknown_and_blocked_accounts(db_session):
    with pytest.raises(AdminGrantError, match="no account"):
        grant_administrator(db_session, email="nobody@example.de", now=NOW)
    accounts = PostgresAccountRepository(db_session)
    blocked = accounts.create_account(email="blocked-admin@example.de", password_hash=None)
    accounts.block_account(blocked.id, reason=BlockReason.OTHER, blocked_at=NOW)
    with pytest.raises(AdminGrantError, match="blocked"):
        grant_administrator(db_session, email="blocked-admin@example.de", now=NOW)
