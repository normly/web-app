# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)

from tests.test_edges import _seed_two_documents_with_an_edge


def _seed_a_contractually_processed_but_not_export_free_document(db_session):
    """
    A document that may be processed/served but is not licensed for
    redistribution in the public free-tier export -- e.g. content received
    under a contract permitting internal processing only.
    """
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DIN Media", retrieval_path="https://www.din.de/de/service/din-media",
        legal_basis_category=LegalBasisCategory.C, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
        contract_reference="Vertrag Nr. 2026-014",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-export-restricted-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction="EU", may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        legal_basis_reference="Vertrag Nr. 2026-014", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_export_excludes_a_document_not_licensed_for_the_free_export(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)
    restricted = _seed_a_contractually_processed_but_not_export_free_document(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    document_ids = {d["id"] for d in response.json()["documents"]}
    assert str(restricted.id) not in document_ids
    assert str(standard.id) in document_ids
    assert str(legal_act.id) in document_ids


def test_export_excludes_a_commercial_layer_edge(client, db_session):
    _seed_two_documents_with_an_edge(db_session, layer=Layer.COMMERCIAL)

    response = client.get("/v1/export", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    assert response.json()["edges"] == []


def test_export_returns_a_license_notice_and_the_classified_graph(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    body = response.json()
    assert body["license"]["license_name"] == "ODbL-1.0"
    assert body["jurisdiction"] == "EU"
    document_ids = {d["id"] for d in body["documents"]}
    assert str(standard.id) in document_ids
    assert str(legal_act.id) in document_ids
    assert len(body["edges"]) == 1


def test_export_excludes_documents_not_classified_for_the_requested_jurisdiction(
    client, db_session
):
    _seed_two_documents_with_an_edge(db_session)

    response = client.get("/v1/export", params={"jurisdiction": "FR"})

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_export_rejects_an_unsupported_format(client, db_session):
    response = client.get("/v1/export", params={"jurisdiction": "EU", "format": "xml"})

    assert response.status_code == 400
