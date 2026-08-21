# accounts/tests/test_session_persistence.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Regression test for the `get_session` dependency actually persisting writes.

Every other test in this suite goes through the `client` fixture in
conftest.py, which overrides `get_session` to hand every request the SAME
long-lived, savepoint-backed `db_session` object. That means the production
`get_session` generator in `normly_accounts.dependencies` is never actually
exercised by the rest of the suite -- a bug where it never commits (so every
write is silently rolled back when the session closes at the end of the
request) would go completely undetected.

This test builds the real app via `create_app()`, leaves `get_session`
un-overridden (only `get_email_sender` is swapped for a recording double, to
avoid a real SMTP attempt), and checks that data written by an HTTP request
is visible from a completely separate database session afterwards.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from normly_accounts.dependencies import get_email_sender
from normly_accounts.email import RecordingEmailSender
from normly_accounts.main import create_app
from normly_core.graph.postgres.repositories import PostgresAccountRepository


def test_register_write_is_visible_from_a_separate_session(db_url, migrated_engine, monkeypatch):
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)

    app = create_app()
    # Deliberately do NOT override get_session -- that's the one dependency
    # this test exists to exercise for real.
    app.dependency_overrides[get_email_sender] = lambda: RecordingEmailSender()

    email = f"persistence-{uuid.uuid4()}@example.de"
    account_id: uuid.UUID | None = None
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/accounts/register",
                json={"email": email, "password": "correct horse battery staple"},
            )
            assert response.status_code == 200
            account_id = uuid.UUID(response.json()["account"]["id"])

        # A fresh Session, bound to a different engine object than the one
        # the request used, talking to the same database. If get_session
        # never committed, the write would have been rolled back when the
        # request's session closed, and this account row would not exist.
        with Session(migrated_engine) as verification_session:
            account = PostgresAccountRepository(verification_session).get_account_by_email(email)
            assert account is not None
            assert account.id == account_id
    finally:
        if account_id is not None:
            with migrated_engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM account_session WHERE account_id = :id"),
                    {"id": account_id},
                )
                connection.execute(
                    text("DELETE FROM account_token WHERE account_id = :id"),
                    {"id": account_id},
                )
                connection.execute(
                    text("DELETE FROM account_google_identity WHERE account_id = :id"),
                    {"id": account_id},
                )
                connection.execute(
                    text("DELETE FROM account WHERE id = :id"), {"id": account_id}
                )
