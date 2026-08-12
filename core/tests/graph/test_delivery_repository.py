# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone
from unittest.mock import patch

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresSourceRepository,
)


def _make_source(db_session):
    source_repo = PostgresSourceRepository(db_session)
    return source_repo.create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )


def test_record_delivery_is_idempotent_by_content_hash(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    now = datetime.now(timezone.utc)

    first = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:abc123", ingested_at=now
    )
    second = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:abc123", ingested_at=now
    )

    assert first.id == second.id


def test_revoke_delivery_sets_withdrawn_at(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery = delivery_repo.record_delivery(
        source_id=source.id,
        content_hash="sha256:def456",
        ingested_at=datetime.now(timezone.utc),
    )

    delivery_repo.revoke_delivery(delivery.id)

    revoked = delivery_repo.get_delivery(delivery.id)
    assert revoked.withdrawn_at is not None


def test_revoke_delivery_is_idempotent(db_session):
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery = delivery_repo.record_delivery(
        source_id=source.id,
        content_hash="sha256:ghi789",
        ingested_at=datetime.now(timezone.utc),
    )

    delivery_repo.revoke_delivery(delivery.id)
    delivery_repo.revoke_delivery(delivery.id)  # must not raise

    revoked = delivery_repo.get_delivery(delivery.id)
    assert revoked.withdrawn_at is not None


def test_record_delivery_handles_concurrent_insert_race(db_session):
    """
    Test that record_delivery is race-safe under concurrent inserts.

    Simulates the TOCTOU (time-of-check-to-time-of-use) race condition:
    1. Thread A and B both execute the pre-check SELECT
    2. Both find no existing delivery (race window)
    3. Thread A flushes first → succeeds, row now in DB
    4. Thread B tries to flush → raises IntegrityError (duplicate key)
    5. Thread B's exception handler catches it and re-selects the row
    6. Thread B returns the existing delivery (idempotent behavior)

    This test simulates the race by making the pre-check SELECT lie (return None)
    even though the row genuinely exists in the DB. When the real INSERT then
    executes, it hits the real unique constraint and raises a genuine IntegrityError.
    The exception handler must catch it and re-select to find the existing row.
    """
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    now = datetime.now(timezone.utc)

    # Create the first delivery for real (row exists in DB)
    first = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:race", ingested_at=now
    )

    # Simulate the TOCTOU window: make the pre-check SELECT return None
    # even though the row exists, forcing the real INSERT to hit the unique constraint
    original_execute = db_session.execute
    call_count = {"n": 0}

    def execute_with_first_select_lying(statement, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First call (pre-check SELECT) lies and returns None
            class _EmptyResult:
                def scalar_one_or_none(self):
                    return None
            return _EmptyResult()
        # Subsequent calls (re-select after exception) use real execute
        return original_execute(statement, *args, **kwargs)

    with patch.object(db_session, "execute", side_effect=execute_with_first_select_lying):
        # This call will:
        # 1. Execute pre-check SELECT → mocked to return None (TOCTOU window)
        # 2. Create DeliveryORM instance
        # 3. Call begin_nested() for savepoint
        # 4. Try to flush → real INSERT hits unique constraint → raises IntegrityError
        # 5. Exception handler catches IntegrityError
        # 6. Exception handler re-executes SELECT → finds the real row (call_count["n"] == 2)
        # 7. Returns the existing delivery
        second = delivery_repo.record_delivery(
            source_id=source.id, content_hash="sha256:race", ingested_at=now
        )

    # Verify we got back the same delivery (idempotent)
    assert second.id == first.id
    assert second.source_id == source.id
    assert second.content_hash == "sha256:race"
    assert second.withdrawn_at is None
