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


def _seed_document(db_session, *, issuer, designation, jurisdiction="DE", content_hash):
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
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_endpoint_returns_matching_documents(client, db_session):
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-1",
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Vorschrift 1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == str(document.id)


def test_search_endpoint_returns_400_when_jurisdiction_is_missing(client, db_session):
    response = client.get("/v1/documents/search", params={"q": "Vorschrift"})

    assert response.status_code == 400


def test_search_endpoint_with_no_query_returns_everything_in_the_jurisdiction(client, db_session):
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-2",
    )

    response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_endpoint_respects_limit(client, db_session):
    for n in range(3):
        _seed_document(
            db_session, issuer="DGUV", designation=f"DGUV Vorschrift {n}",
            content_hash=f"sha256:endpoint-limit-{n}",
        )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": 2},
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["results"]) == 2
