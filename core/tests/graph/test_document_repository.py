# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="Test Reviewer",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:doc-fixture",
        ingested_at=datetime.now(timezone.utc),
    )


def test_create_and_get_document(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresDocumentRepository(db_session)

    document = repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    fetched = repo.get_document_unchecked(document.id)
    assert fetched == document
    assert fetched.created_via_delivery_id == delivery.id


def test_list_documents_for_work_unchecked_returns_every_document_regardless_of_jurisdiction(
    db_session,
):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id, work_id=first.work_id,
    )
    # No rights_classification row exists for either document -- a gated
    # method would return nothing; the unchecked method must still see both.
    documents = doc_repo.list_documents_for_work_unchecked(first.work_id)
    assert {d.id for d in documents} == {first.id, second.id}
