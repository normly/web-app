# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.postgres.repositories import PostgresAccountRepository, PostgresChatRepository
from normly_chat.accounts_client import ChatAccountIdentity
from normly_chat.session_resolution import resolve_session


def _make_account(db_session, email):
    # chat_session.account_id carries a real foreign key to account.id (see
    # Task 1's own migration and its test_chat_repository.py), so a
    # standalone uuid.uuid4() is rejected by the database -- an account row
    # has to exist first, exactly like PostgresChatRepository's own tests do.
    return PostgresAccountRepository(db_session).create_account(
        email=email, password_hash=None,
    )


class _FakeAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, token):
        return self._identity


def test_no_session_token_creates_a_new_anonymous_session(db_session):
    repo = PostgresChatRepository(db_session)
    session, is_new = resolve_session(
        None, None, "DE", "de", repo, _FakeAccountsClient(None),
    )
    assert is_new is True
    assert session.account_id is None


def test_unknown_session_token_creates_a_new_anonymous_session(db_session):
    repo = PostgresChatRepository(db_session)
    session, is_new = resolve_session(
        "not-a-real-token", None, "DE", "de", repo, _FakeAccountsClient(None),
    )
    assert is_new is True
    assert session.account_id is None


def test_valid_account_token_links_an_unlinked_session_and_keeps_its_history(db_session):
    repo = PostgresChatRepository(db_session)
    existing = repo.create_session(
        session_token="tok-existing", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc),
    )
    account = _make_account(db_session, "x@example.de")
    account_id = account.id
    identity = ChatAccountIdentity(account_id=account_id, email="x@example.de")

    session, is_new = resolve_session(
        "tok-existing", "acct-token", "DE", "de", repo, _FakeAccountsClient(identity),
    )
    assert is_new is False
    assert session.id == existing.id
    assert session.account_id == account_id


def test_valid_account_token_for_a_different_account_starts_a_fresh_session(db_session):
    repo = PostgresChatRepository(db_session)
    other_account_id = _make_account(db_session, "other@example.de").id
    existing = repo.create_session(
        session_token="tok-other-account", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc), account_id=other_account_id,
    )
    my_account_id = _make_account(db_session, "me@example.de").id
    identity = ChatAccountIdentity(account_id=my_account_id, email="me@example.de")

    session, is_new = resolve_session(
        "tok-other-account", "acct-token", "DE", "de", repo, _FakeAccountsClient(identity),
    )
    assert is_new is True
    assert session.id != existing.id
    assert session.account_id == my_account_id


def test_invalid_account_token_is_treated_as_no_token(db_session):
    repo = PostgresChatRepository(db_session)
    existing = repo.create_session(
        session_token="tok-anon", jurisdiction="DE", language="de",
        created_at=datetime.now(timezone.utc),
    )
    session, is_new = resolve_session(
        "tok-anon", "invalid-acct-token", "DE", "de", repo, _FakeAccountsClient(None),
    )
    assert is_new is False
    assert session.id == existing.id
    assert session.account_id is None
