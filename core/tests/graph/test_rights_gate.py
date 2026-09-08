# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import RightsClassificationORM
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
    assert doc_repo.list_documents_for_jurisdiction("US") == []


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
    assert doc_repo.list_documents_for_jurisdiction("DE") == []


def test_revoked_classification_blocks_read(db_session):
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

    # Confirm it is readable before revocation, so the assertions below
    # actually exercise the revoked_at predicate and not some other gap.
    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is not None

    orm = db_session.get(RightsClassificationORM, (document.id, "DE"))
    orm.revoked_at = datetime.now(timezone.utc)
    db_session.flush()

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    assert doc_repo.list_documents_for_jurisdiction("DE") == []


def test_may_export_free_false_excludes_document_from_exportable_list_but_not_from_processable_list(
    db_session,
):
    """
    `list_exportable_documents_for_jurisdiction` and
    `list_documents_for_jurisdiction` must have genuinely different semantics:
    a document that may be processed/served internally but is not licensed
    for the public free-tier export (e.g. contractually received, no
    redistribution right) must appear in the latter but not the former.
    """
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    rights_repo.classify(
        document_id=document.id,
        jurisdiction="DE",
        may_process=True,
        may_index_fulltext=True,
        may_cite_passages=True,
        may_export_free=False,
        legal_basis_reference="Vertrag Nr. 2026-014",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )

    assert [d.id for d in doc_repo.list_documents_for_jurisdiction("DE")] == [document.id]
    assert doc_repo.list_exportable_documents_for_jurisdiction("DE") == []


def test_may_export_free_true_includes_document_in_exportable_list(db_session):
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

    exported = doc_repo.list_exportable_documents_for_jurisdiction("DE")
    assert [d.id for d in exported] == [document.id]


def test_classify_is_idempotent_and_updates_existing_classification(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    first = rights_repo.classify(
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

    second = rights_repo.classify(
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

    assert first.may_process is False
    assert second.may_process is True
    assert second.legal_basis_reference == "§ 5 UrhG"

    fetched = rights_repo.get_classification(document.id, "DE")
    assert fetched.may_process is True
    assert fetched.legal_basis_reference == "§ 5 UrhG"

    rows = db_session.execute(
        select(RightsClassificationORM).where(
            RightsClassificationORM.document_id == document.id,
            RightsClassificationORM.jurisdiction == "DE",
        )
    ).scalars().all()
    assert len(rows) == 1


def test_list_classifications_for_document_unchecked_returns_every_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="pipeline",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=document.id, jurisdiction="AT", may_process=False, may_index_fulltext=False,
        may_cite_passages=False, may_export_free=False, legal_basis_reference="n/a",
        classified_at=datetime.now(timezone.utc), classified_by="pipeline",
        delivery_id=delivery.id,
    )

    classifications = rights_repo.list_classifications_for_document_unchecked(document.id)
    assert {c.jurisdiction for c in classifications} == {"DE", "AT"}
