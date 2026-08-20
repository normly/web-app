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


def _seed_document(db_session, *, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-search-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_finds_a_classified_document(client, db_session):
    document = _seed_document(db_session, jurisdiction="DE")

    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1", "jurisdiction": "DE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(document.id)
    assert body["source"]["publisher"] == "DGUV"
    assert body["source"]["retrieval_path"] == "https://www.dguv.de/publikationen"


def test_search_hides_a_document_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    _seed_document(db_session, jurisdiction="DE")

    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1", "jurisdiction": "FR"},
    )

    assert response.status_code == 404


def test_search_returns_404_for_an_unknown_designation(client, db_session):
    response = client.get(
        "/v1/documents",
        params={"issuer": "DGUV", "designation": "does-not-exist", "jurisdiction": "DE"},
    )

    assert response.status_code == 404


def test_search_returns_400_when_jurisdiction_is_missing(client, db_session):
    response = client.get(
        "/v1/documents", params={"issuer": "DGUV", "designation": "DGUV Vorschrift 1"}
    )

    assert response.status_code == 400
