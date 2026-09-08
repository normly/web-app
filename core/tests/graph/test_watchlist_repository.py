# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def test_add_watch_creates_a_row(db_session):
    account = _make_account(db_session, "watch-add@example.de")
    work = _make_work(db_session)

    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=work.id
    )
    assert watch.account_id == account.id
    assert watch.work_id == work.id


def test_add_watch_is_idempotent(db_session):
    account = _make_account(db_session, "watch-idempotent@example.de")
    work = _make_work(db_session)
    repo = PostgresWatchlistRepository(db_session)

    first = repo.add_watch(account_id=account.id, work_id=work.id)
    second = repo.add_watch(account_id=account.id, work_id=work.id)
    assert first.id == second.id
    assert len(repo.list_watches_for_account(account.id)) == 1


def test_remove_watch_is_idempotent(db_session):
    account = _make_account(db_session, "watch-remove@example.de")
    work = _make_work(db_session)
    repo = PostgresWatchlistRepository(db_session)

    repo.add_watch(account_id=account.id, work_id=work.id)
    repo.remove_watch(account_id=account.id, work_id=work.id)
    repo.remove_watch(account_id=account.id, work_id=work.id)  # no error on the second call
    assert repo.list_watches_for_account(account.id) == []


def test_list_watches_for_account_only_returns_that_accounts_watches(db_session):
    repo = PostgresWatchlistRepository(db_session)
    account_a = _make_account(db_session, "watch-a@example.de")
    account_b = _make_account(db_session, "watch-b@example.de")
    work = _make_work(db_session)

    repo.add_watch(account_id=account_a.id, work_id=work.id)
    repo.add_watch(account_id=account_b.id, work_id=work.id)

    assert [w.account_id for w in repo.list_watches_for_account(account_a.id)] == [account_a.id]


def test_list_all_watches_returns_every_accounts_watches(db_session):
    repo = PostgresWatchlistRepository(db_session)
    account_a = _make_account(db_session, "watch-all-a@example.de")
    account_b = _make_account(db_session, "watch-all-b@example.de")
    work_1 = _make_work(db_session)
    work_2 = _make_work(db_session)

    repo.add_watch(account_id=account_a.id, work_id=work_1.id)
    repo.add_watch(account_id=account_b.id, work_id=work_2.id)

    pairs = {(w.account_id, w.work_id) for w in repo.list_all_watches()}
    assert pairs == {(account_a.id, work_1.id), (account_b.id, work_2.id)}
