# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import (
    NotificationPreference,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import AccountORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresWorkRepository,
)


def test_new_account_defaults_to_notification_preference_none(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-default@example.de", password_hash=None
    )
    assert account.notification_preference == NotificationPreference.NONE

    db_session.flush()
    orm = db_session.get(AccountORM, account.id)
    assert orm.notification_preference == NotificationPreference.NONE


def test_watchlist_rejects_a_duplicate_account_work_pair(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-dup@example.de", password_hash=None
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)

    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    db_session.flush()
    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_notification_orm_round_trip_and_nullable_trigger_columns(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-notif@example.de", password_hash=None
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)

    notification = NotificationORM(
        id=uuid.uuid4(),
        account_id=account.id,
        work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None,
        trigger_document_id=None,
        trigger_jurisdiction=None,
        may_process=None,
        may_index_fulltext=None,
        may_cite_passages=None,
        may_export_free=None,
        read_at=None,
        emailed_at=None,
    )
    db_session.add(notification)
    db_session.flush()

    fetched = db_session.get(NotificationORM, notification.id)
    assert fetched is not None
    assert fetched.trigger_type == NotificationTriggerType.NEW_EDITION
    assert fetched.read_at is None
    assert fetched.emailed_at is None
