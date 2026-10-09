# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresNotifiedRetirementRepository,
    PostgresSourceRepository,
)

_T1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
_T2 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="Test-Pub", retrieval_path="https://test.example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 1), responsible_person="Test User",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:notified-retirement",
        ingested_at=datetime.now(timezone.utc),
    )
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="Test", origin_number="TST-NR-1", edition="2026", part=None,
        delivery_id=delivery.id,
    )


def test_roundtrip_is_idempotent_and_keyed_by_retirement_time(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="notified-retirement@example.de", password_hash=None
    )
    document = _document(db_session)
    repo = PostgresNotifiedRetirementRepository(db_session)
    key = dict(account_id=account.id, work_id=document.work_id, document_id=document.id)

    assert repo.has_been_notified(**key, retired_at=_T1) is False
    repo.mark_notified(**key, retired_at=_T1)
    repo.mark_notified(**key, retired_at=_T1)

    assert repo.has_been_notified(**key, retired_at=_T1) is True
    assert repo.has_been_notified(**key, retired_at=_T2) is False
