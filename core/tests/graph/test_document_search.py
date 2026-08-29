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


def _seed_document(
    db_session, *, issuer, designation, title, jurisdiction="DE", content_hash,
):
    source = PostgresSourceRepository(db_session).create_source(
        publisher=issuer, retrieval_path="https://example.de", legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE", reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=designation, edition="2013", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=designation, language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_title(
        document_id=document.id, language="de", title=title, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_finds_a_document_by_partial_designation(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-1",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", q="Vorschrift 1")

    assert total == 1
    assert [d.id for d in results] == [document.id]


def test_search_finds_a_document_by_partial_title(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-2",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", q="Prävention")

    assert total == 1
    assert [d.id for d in results] == [document.id]


def test_search_filters_by_issuer(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    dguv_doc = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        content_hash="sha256:search-3",
    )
    _seed_document(
        db_session, issuer="DIN", designation="DIN EN ISO 9001", title="B",
        content_hash="sha256:search-4",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", issuer="DGUV")

    assert total == 1
    assert [d.id for d in results] == [dguv_doc.id]


def test_search_hides_documents_not_classified_for_the_requested_jurisdiction(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        jurisdiction="DE", content_hash="sha256:search-5",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("FR", q="Vorschrift")

    assert total == 0
    assert results == []


def test_search_paginates_with_limit_and_offset(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    docs = [
        _seed_document(
            db_session, issuer="DGUV", designation=f"DGUV Vorschrift {n}", title=f"Titel {n}",
            content_hash=f"sha256:search-page-{n}",
        )
        for n in range(5)
    ]

    first_page, total = doc_repo.search_documents_for_jurisdiction(
        "DE", issuer="DGUV", limit=2, offset=0,
    )
    second_page, _ = doc_repo.search_documents_for_jurisdiction(
        "DE", issuer="DGUV", limit=2, offset=2,
    )

    assert total == 5
    assert len(first_page) == 2
    assert len(second_page) == 2
    assert {d.id for d in first_page}.isdisjoint({d.id for d in second_page})
    assert {d.id for d in docs} >= {d.id for d in first_page} | {d.id for d in second_page}


def test_search_with_no_filters_returns_everything_in_the_jurisdiction(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", title="A",
        content_hash="sha256:search-6",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE")

    assert total == 1
    assert [d.id for d in results] == [document.id]


def test_a_literal_percent_sign_is_not_treated_as_a_wildcard(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    matching = _seed_document(
        db_session, issuer="DGUV", designation="DGUV 50% Regel",
        title="Halbe Sache", content_hash="sha256:search-percent-1",
    )
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 3",
        title="Elektrische Anlagen", content_hash="sha256:search-percent-2",
    )

    results, total = doc_repo.search_documents_for_jurisdiction("DE", q="50%")

    assert total == 1
    assert [d.id for d in results] == [matching.id]


def test_a_bare_percent_sign_does_not_match_the_whole_catalogue(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-percent-3",
    )

    _, total = doc_repo.search_documents_for_jurisdiction("DE", q="%")

    assert total == 0


def test_a_literal_underscore_is_not_treated_as_a_single_character_wildcard(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1",
        title="Grundsätze der Prävention", content_hash="sha256:search-underscore-1",
    )

    # "Vorschrift_1" would match "Vorschrift 1" if _ stayed a wildcard.
    _, total = doc_repo.search_documents_for_jurisdiction("DE", q="Vorschrift_1")

    assert total == 0
