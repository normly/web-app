# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _make_document(db_session, content_hash="sha256:rights-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="BAuA",
        retrieval_path="https://www.baua.de/technische-regeln",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="BAuA",
        origin_number="TRGS 900",
        edition="2026",
        part=None,
        delivery_id=delivery.id,
    )
    return document, delivery


def test_document_without_classification_is_not_readable(db_session):
    document, _ = _make_document(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    assert doc_repo.list_documents_for_jurisdiction("DE") == []


def test_classified_document_is_readable_for_its_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=True,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    fetched = doc_repo.get_document_for_jurisdiction(document.id, "DE")
    assert fetched is not None
    assert fetched.id == document.id

    exported = doc_repo.list_documents_for_jurisdiction("DE")
    assert [d.id for d in exported] == [document.id]


def test_classification_does_not_grant_access_in_other_jurisdictions(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=True,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    assert doc_repo.get_document_for_jurisdiction(document.id, "US") is None


def test_may_process_false_still_blocks_read(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=False,
        may_index_fulltext=False,
        may_cite_passages=False,
        may_export_free=False,
        legal_basis_reference="unklar, in Prüfung",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
