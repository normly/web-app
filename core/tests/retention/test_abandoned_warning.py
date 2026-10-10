# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import logging
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core import retention
from normly_core.graph.postgres.orm import AccountORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresDeletionLogRepository,
)
from normly_core.notifications.email import NullEmailSender, RecordingEmailSender
from normly_core.pipeline.cli import _cleanup_user_data

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
OLD = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE - timedelta(days=5)
NOTICE = retention.ACCOUNT_DELETION_NOTICE_PERIOD


class FailingEmailSender:
    def __init__(self):
        self.calls = 0

    def send(self, *, to, subject, body):
        self.calls += 1
        raise RuntimeError("relay down")


def _account(session, email, *, created_at=OLD, warned_at=None, verified=False):
    account = PostgresAccountRepository(session).create_account(email=email, password_hash=None)
    session.execute(
        sa.update(AccountORM).where(AccountORM.id == account.id).values(
            created_at=created_at, deletion_warned_at=warned_at,
            email_verified_at=NOW if verified else None,
        )
    )
    return account


def _warned_at(session, account_id):
    session.expire_all()
    return session.execute(
        sa.select(AccountORM.deletion_warned_at).where(AccountORM.id == account_id)
    ).scalar_one_or_none()


def _exists(session, account_id) -> bool:
    return session.execute(
        sa.select(sa.func.count()).select_from(AccountORM).where(AccountORM.id == account_id)
    ).scalar_one() == 1


def _summary(line: str) -> dict[str, int]:
    return {k: int(v) for k, v in (part.split("=") for part in line.split())}


def test_abandoned_unwarned_account_gets_a_bilingual_warning(db_session, monkeypatch):
    monkeypatch.setenv("NORMLY_PUBLIC_BASE_URL", "https://app.example.org")
    account = _account(db_session, "warn@example.de")
    sender = RecordingEmailSender()

    summary = _summary(_cleanup_user_data(db_session, NOW, sender))

    assert summary["warnings_sent"] == 1
    assert summary["unverified_accounts"] == 0
    assert len(sender.sent) == 1
    mail = sender.sent[0]
    assert mail["to"] == "warn@example.de"
    assert mail["subject"] == (
        "Dein normly-Konto wird gelöscht / Your normly account will be deleted"
    )
    delete_on = (NOW + NOTICE).date().isoformat()
    assert delete_on in mail["body"]
    assert "https://app.example.org" in mail["body"]
    assert "Konto" in mail["body"] and "account" in mail["body"]
    assert _warned_at(db_session, account.id) == NOW
    assert _exists(db_session, account.id)


def test_warning_without_base_url_has_no_link(db_session, monkeypatch):
    monkeypatch.delenv("NORMLY_PUBLIC_BASE_URL", raising=False)
    _account(db_session, "nolink@example.de")
    sender = RecordingEmailSender()

    _cleanup_user_data(db_session, NOW, sender)

    assert "http" not in sender.sent[0]["body"]


def test_failed_send_leaves_the_account_unwarned_and_does_not_abort(db_session):
    account = _account(db_session, "fail@example.de")
    sender = FailingEmailSender()

    summary = _summary(_cleanup_user_data(db_session, NOW, sender))

    assert sender.calls == 1
    assert summary["warnings_sent"] == 0
    assert _warned_at(db_session, account.id) is None
    assert _exists(db_session, account.id)


def test_without_smtp_nothing_is_warned_or_deleted(db_session):
    account = _account(db_session, "null@example.de", created_at=NOW - timedelta(days=900))

    first = _summary(_cleanup_user_data(db_session, NOW, NullEmailSender()))
    second = _summary(_cleanup_user_data(db_session, NOW + timedelta(days=60), NullEmailSender()))

    assert first["warnings_sent"] == second["warnings_sent"] == 0
    assert first["unverified_accounts"] == second["unverified_accounts"] == 0
    assert _warned_at(db_session, account.id) is None
    assert _exists(db_session, account.id)


def test_without_smtp_logs_one_line_and_no_traceback(db_session, caplog):
    name = "normly_core.notifications.abandoned_registration"
    # The Alembic fileConfig run by the migrated_engine fixture disables loggers.
    logging.getLogger(name).disabled = False
    caplog.set_level("WARNING", logger=name)
    _account(db_session, "a@example.de")
    _account(db_session, "b@example.de")

    _cleanup_user_data(db_session, NOW, NullEmailSender())

    records = [r for r in caplog.records if "SMTP" in r.getMessage()]
    assert len(records) == 1
    assert not any(r.exc_info for r in caplog.records)


def test_warning_is_committed_per_mail(db_session, monkeypatch):
    _account(db_session, "c@example.de")
    commits = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    summary = _summary(_cleanup_user_data(db_session, NOW, RecordingEmailSender()))

    assert summary["warnings_sent"] == 1 and commits == [1]


def test_notice_period_boundaries(db_session):
    thirteen = _account(db_session, "d13@example.de", warned_at=NOW - timedelta(days=13))
    exactly = _account(db_session, "d14@example.de", warned_at=NOW - NOTICE)
    fifteen = _account(db_session, "d15@example.de", warned_at=NOW - timedelta(days=15))
    sender = RecordingEmailSender()

    summary = _summary(_cleanup_user_data(db_session, NOW, sender))

    assert summary["unverified_accounts"] == 1
    assert summary["warnings_sent"] == 0
    assert sender.sent == []
    assert _exists(db_session, thirteen.id)
    assert _exists(db_session, exactly.id)
    assert not _exists(db_session, fifteen.id)
    entries = PostgresDeletionLogRepository(db_session).entries_since(NOW - timedelta(days=1))
    assert [(k, e) for k, e, _ in entries] == [("account", fifteen.id)]


def test_recovered_accounts_are_reset_and_kept(db_session):
    warned = NOW - timedelta(days=20)
    verified = _account(db_session, "ver@example.de", warned_at=warned, verified=True)
    google = _account(db_session, "goo@example.de", warned_at=warned)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=google.id, google_subject_id="subject-warn",
    )
    logged_in = _account(db_session, "login@example.de", warned_at=warned)
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=logged_in.id, session_token="warn-sess", created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )

    sender = RecordingEmailSender()
    summary = _summary(_cleanup_user_data(db_session, NOW, sender))

    assert summary["unverified_accounts"] == 0
    assert sender.sent == []
    for account in (verified, google, logged_in):
        assert _exists(db_session, account.id)
        assert _warned_at(db_session, account.id) is None


def test_expired_session_after_warning_still_resets_the_warning(db_session):
    account = _account(db_session, "back@example.de", warned_at=NOW - timedelta(days=20))
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="expired-sess",
        created_at=NOW - timedelta(days=60), expires_at=NOW - timedelta(days=30),
    )

    sender = RecordingEmailSender()
    summary = _summary(_cleanup_user_data(db_session, NOW, sender))

    # The old warning is void: the account is kept and gets a fresh notice period.
    assert summary["sessions"] == 1 and summary["unverified_accounts"] == 0
    assert summary["warnings_sent"] == 1 and len(sender.sent) == 1
    assert _exists(db_session, account.id)
    assert _warned_at(db_session, account.id) == NOW


def test_no_account_is_warned_and_deleted_in_one_run_and_reruns_are_idempotent(db_session):
    account = _account(db_session, "once@example.de", created_at=NOW - timedelta(days=900))
    sender = RecordingEmailSender()

    first = _summary(_cleanup_user_data(db_session, NOW, sender))
    assert first["warnings_sent"] == 1 and first["unverified_accounts"] == 0
    assert _exists(db_session, account.id)

    same_day = _summary(_cleanup_user_data(db_session, NOW + timedelta(days=1), sender))
    assert same_day["warnings_sent"] == 0 and same_day["unverified_accounts"] == 0
    assert len(sender.sent) == 1

    later = _summary(_cleanup_user_data(db_session, NOW + NOTICE + timedelta(seconds=1), sender))
    assert later["unverified_accounts"] == 1 and later["warnings_sent"] == 0
    assert not _exists(db_session, account.id)

    again = _summary(_cleanup_user_data(db_session, NOW + NOTICE + timedelta(days=1), sender))
    assert again["unverified_accounts"] == 0 and again["warnings_sent"] == 0
    assert len(sender.sent) == 1


def test_delete_recheck_includes_the_warning_condition(db_session):
    account = _account(db_session, "recheck@example.de", warned_at=NOW - timedelta(days=20))
    repo = PostgresAccountRepository(db_session)
    cutoff = NOW - retention.UNVERIFIED_ACCOUNT_MAX_AGE

    selected = repo._abandoned_registration_ids(cutoff, warned_before=NOW - NOTICE, lock=True)
    assert selected == [account.id]
    db_session.execute(
        sa.update(AccountORM).where(AccountORM.id == account.id).values(deletion_warned_at=NOW)
    )

    assert repo._abandoned_registration_ids(
        cutoff, warned_before=NOW - NOTICE, only=selected
    ) == []
