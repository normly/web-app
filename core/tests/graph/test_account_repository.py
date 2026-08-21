# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.orm import AccountTokenORM
from normly_core.graph.postgres.repositories import (
    EmailAlreadyRegisteredError,
    GoogleIdentityAlreadyLinkedError,
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
)


def test_create_account_and_look_it_up(db_session):
    repo = PostgresAccountRepository(db_session)

    account = repo.create_account(email="j.weber@example.de", password_hash="hashed")

    assert repo.get_account_by_id(account.id) == account
    assert repo.get_account_by_email("j.weber@example.de") == account
    assert account.email_verified_at is None


def test_create_account_rejects_a_duplicate_email(db_session):
    repo = PostgresAccountRepository(db_session)
    repo.create_account(email="dup@example.de", password_hash="hashed-1")

    with pytest.raises(EmailAlreadyRegisteredError):
        repo.create_account(email="dup@example.de", password_hash="hashed-2")


def test_create_account_allows_a_null_password_hash(db_session):
    repo = PostgresAccountRepository(db_session)

    account = repo.create_account(email="google-only@example.de", password_hash=None)

    assert account.password_hash is None


def test_mark_email_verified(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="verify@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)

    repo.mark_email_verified(account.id, now)

    assert repo.get_account_by_id(account.id).email_verified_at == now


def test_set_password_hash(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="reset@example.de", password_hash="old-hash")

    repo.set_password_hash(account.id, "new-hash")

    assert repo.get_account_by_id(account.id).password_hash == "new-hash"


def test_google_identity_links_and_resolves_to_the_account(db_session):
    account_repo = PostgresAccountRepository(db_session)
    google_repo = PostgresAccountGoogleIdentityRepository(db_session)
    account = account_repo.create_account(email="g@example.de", password_hash=None)

    google_repo.link_google_identity(account_id=account.id, google_subject_id="sub-123")

    assert google_repo.get_account_by_google_subject("sub-123") == account
    assert google_repo.get_account_by_google_subject("unknown-subject") is None


def test_session_create_lookup_extend_and_revoke(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    account = account_repo.create_account(email="sess@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=30)

    session = session_repo.create_session(
        account_id=account.id, session_token="tok-abc", created_at=now, expires_at=expires,
    )
    assert session_repo.get_session_by_token("tok-abc") == session

    later = now + timedelta(days=31)
    session_repo.extend_session(session.id, later)
    assert session_repo.get_session_by_token("tok-abc").expires_at == later

    session_repo.revoke_session("tok-abc")
    assert session_repo.get_session_by_token("tok-abc") is None


def test_get_session_by_token_returns_none_for_an_unknown_token(db_session):
    session_repo = PostgresAccountSessionRepository(db_session)

    assert session_repo.get_session_by_token("no-such-token") is None


def test_token_create_and_consume(db_session):
    account_repo = PostgresAccountRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="tok@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)

    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK, token="magic-1",
        created_at=now, expires_at=now + timedelta(minutes=15),
    )

    consumed = token_repo.consume_token("magic-1", AccountTokenPurpose.MAGIC_LINK)
    assert consumed is not None
    assert consumed.account_id == account.id
    assert consumed.used_at is not None


def test_consume_token_is_single_use(db_session):
    account_repo = PostgresAccountRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="single@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)
    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET, token="reset-1",
        created_at=now, expires_at=now + timedelta(hours=1),
    )

    first = token_repo.consume_token("reset-1", AccountTokenPurpose.PASSWORD_RESET)
    second = token_repo.consume_token("reset-1", AccountTokenPurpose.PASSWORD_RESET)

    assert first is not None
    assert second is None


def test_consume_token_rejects_an_expired_token(db_session):
    account_repo = PostgresAccountRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="expired@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)
    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token="expired-1", created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )

    assert token_repo.consume_token("expired-1", AccountTokenPurpose.EMAIL_VERIFICATION) is None


def test_consume_token_rejects_the_wrong_purpose(db_session):
    account_repo = PostgresAccountRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="wrongpurpose@example.de", password_hash="h")
    now = datetime.now(timezone.utc)
    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK, token="mixed-1",
        created_at=now, expires_at=now + timedelta(minutes=15),
    )

    assert token_repo.consume_token("mixed-1", AccountTokenPurpose.PASSWORD_RESET) is None


def test_create_token_binds_to_an_email_that_has_no_account_yet(db_session):
    """
    Magic-link is a registration path: the token names the address, and the
    account is created when the link is confirmed and the mailbox is thereby
    proven readable.
    """
    token_repo = PostgresAccountTokenRepository(db_session)
    now = datetime.now(timezone.utc)

    created = token_repo.create_token(
        email="nobody-yet@example.de", purpose=AccountTokenPurpose.MAGIC_LINK,
        token="pending-1", created_at=now, expires_at=now + timedelta(minutes=15),
    )

    assert created.account_id is None
    assert created.email == "nobody-yet@example.de"

    consumed = token_repo.consume_token("pending-1", AccountTokenPurpose.MAGIC_LINK)
    assert consumed is not None
    assert consumed.account_id is None
    assert consumed.email == "nobody-yet@example.de"


def test_create_token_rejects_both_an_account_and_an_email(db_session):
    account_repo = PostgresAccountRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="both@example.de", password_hash="hashed")
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        token_repo.create_token(
            account_id=account.id, email="both@example.de",
            purpose=AccountTokenPurpose.MAGIC_LINK, token="both-1",
            created_at=now, expires_at=now + timedelta(minutes=15),
        )


def test_create_token_rejects_neither_an_account_nor_an_email(db_session):
    token_repo = PostgresAccountTokenRepository(db_session)
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        token_repo.create_token(
            purpose=AccountTokenPurpose.MAGIC_LINK, token="neither-1",
            created_at=now, expires_at=now + timedelta(minutes=15),
        )


def test_the_database_enforces_exactly_one_of_account_and_email(db_session):
    """
    The repository's ValueError is what callers rely on; this proves the check
    constraint behind it is actually deployed, for any writer that goes around
    the repository.
    """
    account_repo = PostgresAccountRepository(db_session)
    account = account_repo.create_account(email="dbcheck@example.de", password_hash="h")
    now = datetime.now(timezone.utc)

    for account_id, email, token in (
        (None, None, "raw-neither"), (account.id, "dbcheck@example.de", "raw-both"),
    ):
        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                db_session.add(
                    AccountTokenORM(
                        account_id=account_id, email=email,
                        purpose=AccountTokenPurpose.MAGIC_LINK, token=token,
                        created_at=now, expires_at=now + timedelta(minutes=15),
                        used_at=None,
                    )
                )
                db_session.flush()


def test_link_google_identity_is_idempotent_for_an_identical_link(db_session):
    account_repo = PostgresAccountRepository(db_session)
    google_repo = PostgresAccountGoogleIdentityRepository(db_session)
    account = account_repo.create_account(email="again@example.de", password_hash=None)

    first = google_repo.link_google_identity(
        account_id=account.id, google_subject_id="sub-same"
    )
    second = google_repo.link_google_identity(
        account_id=account.id, google_subject_id="sub-same"
    )

    assert first == second


def test_link_google_identity_rejects_a_second_subject_for_the_same_account(db_session):
    """
    account_id is the primary key, so an account carries at most one Google
    identity. The collision must surface as a named error -- an unguarded
    IntegrityError would also poison the session for the rest of the request.
    """
    account_repo = PostgresAccountRepository(db_session)
    google_repo = PostgresAccountGoogleIdentityRepository(db_session)
    account = account_repo.create_account(email="twosubs@example.de", password_hash=None)
    google_repo.link_google_identity(account_id=account.id, google_subject_id="sub-first")

    with pytest.raises(GoogleIdentityAlreadyLinkedError):
        google_repo.link_google_identity(
            account_id=account.id, google_subject_id="sub-second"
        )

    # The session survived the failed insert: the savepoint rolled back, not
    # the enclosing transaction.
    assert google_repo.get_account_by_google_subject("sub-first") == account


def test_link_google_identity_rejects_a_subject_already_linked_elsewhere(db_session):
    account_repo = PostgresAccountRepository(db_session)
    google_repo = PostgresAccountGoogleIdentityRepository(db_session)
    first_account = account_repo.create_account(email="owner@example.de", password_hash=None)
    second_account = account_repo.create_account(email="other@example.de", password_hash=None)
    google_repo.link_google_identity(
        account_id=first_account.id, google_subject_id="sub-shared"
    )

    with pytest.raises(GoogleIdentityAlreadyLinkedError):
        google_repo.link_google_identity(
            account_id=second_account.id, google_subject_id="sub-shared"
        )

    assert google_repo.get_account_by_google_subject("sub-shared") == first_account
