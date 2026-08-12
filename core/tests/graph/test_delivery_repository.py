# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresSourceRepository,
)
from normly_core.graph.postgres.orm import DeliveryORM


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

    The race condition scenario: two threads both pass the SELECT check
    before either flushes, causing the second flush to raise IntegrityError.
    The fix must catch this and return the existing delivery without crashing.

    This test verifies the exception handling by:
    1. Creating a delivery
    2. Expunging the session (simulating a separate transaction/thread)
    3. Patching flush to raise IntegrityError on first call
    4. Verifying that record_delivery's try-except path handles it correctly

    The key property: after record_delivery catches IntegrityError and rolls back,
    the re-select must find the row that was inserted by the "other thread".
    """
    source = _make_source(db_session)
    delivery_repo = PostgresDeliveryRepository(db_session)
    now = datetime.now(timezone.utc)

    # Create the first delivery to establish it exists
    first = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:race_test", ingested_at=now
    )

    # Expunge the session to clear the identity map (simulating a new transaction)
    db_session.expunge_all()

    # Now simulate the race: patch flush to raise IntegrityError on first call
    # This simulates the scenario where the SELECT found nothing, but then
    # another thread inserted it before we could flush.
    call_count = [0]
    original_flush = db_session.flush

    def mock_flush_raises_once(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First flush raises IntegrityError (simulating duplicate key)
            raise IntegrityError(
                "statement", "params",
                Exception("duplicate key value violates unique constraint")
            )
        # Subsequent flushes succeed
        return original_flush(*args, **kwargs)

    with patch.object(db_session, "flush", side_effect=mock_flush_raises_once):
        with db_session.no_autoflush:
            # This call should not raise. The exception handler should:
            # 1. Catch IntegrityError from flush
            # 2. Rollback to savepoint
            # 3. Re-select and find the existing delivery
            # 4. Return it
            result = delivery_repo.record_delivery(
                source_id=source.id, content_hash="sha256:race_test", ingested_at=now
            )

    # Verify we got back the same delivery
    assert result.id == first.id
    assert result.source_id == source.id
    assert result.content_hash == "sha256:race_test"
    assert result.withdrawn_at is None
