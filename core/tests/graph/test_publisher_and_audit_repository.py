# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from normly_core.graph.domain import AdminAction, PublisherNameTakenError
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def test_create_and_list_publishers_sorted_by_name(db_session):
    repo = PostgresPublisherRepository(db_session)
    vde = repo.create_publisher(name="VDE Verlag", created_at=NOW)
    din = repo.create_publisher(name="DIN Media", created_at=NOW)

    assert [p.name for p in repo.list_publishers()] == ["DIN Media", "VDE Verlag"]
    assert repo.get_publisher(vde.id) == vde
    assert repo.get_publisher(uuid.uuid4()) is None
    assert din.created_at == NOW


def test_duplicate_publisher_name_raises_and_keeps_the_session_usable(db_session):
    repo = PostgresPublisherRepository(db_session)
    repo.create_publisher(name="DIN Media", created_at=NOW)
    with pytest.raises(PublisherNameTakenError):
        repo.create_publisher(name="din media", created_at=NOW)
    assert len(repo.list_publishers()) == 1


def test_audit_entries_survive_account_deletion_and_carry_no_email(db_session):
    accounts = PostgresAccountRepository(db_session)
    target = accounts.create_account(email="audited@example.de", password_hash=None)
    audit = PostgresAdminAuditRepository(db_session)
    audit.record(
        action=AdminAction.ACCOUNT_BLOCKED, actor_account_id=None, occurred_at=NOW,
        target_account_id=target.id, details={"reason": "abuse"},
    )
    accounts.delete_account(target.id)

    entries = audit.list_for_target_account(target.id)
    assert [(e.action, e.details) for e in entries] == [
        (AdminAction.ACCOUNT_BLOCKED, {"reason": "abuse"})
    ]
    assert "audited@example.de" not in repr(entries)


def test_delete_older_than_only_removes_old_entries(db_session):
    audit = PostgresAdminAuditRepository(db_session)
    target = uuid.uuid4()
    audit.record(action=AdminAction.ROLE_CHANGED, actor_account_id=None,
                 occurred_at=NOW - timedelta(days=800), target_account_id=target)
    audit.record(action=AdminAction.ROLE_CHANGED, actor_account_id=None,
                 occurred_at=NOW, target_account_id=target)

    assert audit.delete_older_than(NOW - timedelta(days=730)) == 1
    assert len(audit.list_for_target_account(target)) == 1
