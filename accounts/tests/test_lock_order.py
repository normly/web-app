# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""One lock order on every path: administrator rows, account row, token rows."""

from datetime import datetime, timedelta, timezone

import pytest

from normly_core.graph.domain import AccountTokenPurpose, Role
from normly_core.graph.postgres import repositories as repos
from normly_core.graph.postgres.repositories import (
    PostgresAccountTokenRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import make_account, make_admin


@pytest.fixture()
def lock_log(monkeypatch):
    log: list[str] = []

    def wrap(cls, name, label):
        original = getattr(cls, name)

        def recorder(self, *args, **kwargs):
            log.append(label)
            return original(self, *args, **kwargs)

        monkeypatch.setattr(cls, name, recorder)

    wrap(repos.PostgresAccountRepository, "lock_active_administrator_ids", "admins")
    wrap(repos.PostgresAccountRepository, "lock_account", "account")
    wrap(repos.PostgresAccountTokenRepository, "consume_token", "token")
    wrap(repos.PostgresAccountTokenRepository, "delete_for_account", "token")
    return log


def _first_positions(log):
    return {label: log.index(label) for label in set(log)}


def test_accept_for_an_unverified_administrator_locks_admins_before_the_account(
    client, db_session, lock_log
):
    _, headers = make_admin(db_session)
    unverified_admin = make_account(db_session, "unverified-admin@example.de",
                                    role=Role.ADMINISTRATOR, password="correct horse")
    client.post("/v1/admin/invitations", headers=headers,
                json={"email": unverified_admin.email, "role": "user"})
    token = PostgresInvitationRepository(db_session).get_invitation_by_email(
        unverified_admin.email
    ).token
    lock_log.clear()

    client.post("/v1/accounts/invitations/accept", json={"token": token})

    first = _first_positions(lock_log)
    assert first["admins"] < first["account"] < first["token"]


def test_email_change_confirm_locks_the_account_before_the_token(client, db_session, lock_log):
    account = make_account(db_session, "mover@example.de", password="correct horse")
    now = datetime.now(timezone.utc)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=account.id, email="moved@example.de",
        purpose=AccountTokenPurpose.EMAIL_CHANGE, token="change-tok",
        created_at=now, expires_at=now + timedelta(hours=1),
    )
    lock_log.clear()

    response = client.get("/v1/accounts/email/confirm", params={"token": "change-tok"})

    assert response.status_code == 200
    first = _first_positions(lock_log)
    assert first["account"] < first["token"]
