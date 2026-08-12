# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

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
