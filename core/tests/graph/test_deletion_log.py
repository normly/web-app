# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from normly_core.graph.postgres.repositories import PostgresDeletionLogRepository

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def test_record_and_entries_since(db_session):
    repo = PostgresDeletionLogRepository(db_session)
    old, recent = uuid.uuid4(), uuid.uuid4()
    repo.record(kind="account", entity_id=old, deleted_at=NOW - timedelta(days=10))
    repo.record(kind="chat_session", entity_id=recent, deleted_at=NOW - timedelta(days=1))

    entries = repo.entries_since(NOW - timedelta(days=2))

    assert entries == [("chat_session", recent, NOW - timedelta(days=1))]
    assert len(repo.entries_since(NOW - timedelta(days=11))) == 2


def test_record_is_idempotent_and_keeps_the_first_timestamp(db_session):
    repo = PostgresDeletionLogRepository(db_session)
    entity = uuid.uuid4()
    repo.record(kind="account", entity_id=entity, deleted_at=NOW)
    repo.record(kind="account", entity_id=entity, deleted_at=NOW + timedelta(days=1))

    assert repo.entries_since(NOW - timedelta(days=1)) == [("account", entity, NOW)]


def test_same_id_with_different_kind_is_a_separate_entry(db_session):
    repo = PostgresDeletionLogRepository(db_session)
    entity = uuid.uuid4()
    repo.record(kind="account", entity_id=entity, deleted_at=NOW)
    repo.record(kind="chat_session", entity_id=entity, deleted_at=NOW)

    assert len(repo.entries_since(NOW - timedelta(days=1))) == 2


def test_delete_older_than_is_strict(db_session):
    repo = PostgresDeletionLogRepository(db_session)
    cutoff = NOW - timedelta(days=90)
    before, at, after = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    repo.record(kind="account", entity_id=before, deleted_at=cutoff - timedelta(seconds=1))
    repo.record(kind="account", entity_id=at, deleted_at=cutoff)
    repo.record(kind="account", entity_id=after, deleted_at=cutoff + timedelta(seconds=1))

    assert repo.delete_older_than(cutoff) == 1
    assert repo.delete_older_than(cutoff) == 0
    remaining = {entity for _, entity, _ in repo.entries_since(cutoff - timedelta(days=1))}
    assert remaining == {at, after}


def test_unknown_kind_is_rejected_by_the_database(db_session):
    repo = PostgresDeletionLogRepository(db_session)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repo.record(kind="document", entity_id=uuid.uuid4(), deleted_at=NOW)
    assert db_session.execute(sa.text("SELECT 1")).scalar_one() == 1
