# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _seed_classified_document(db_session, *, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-validity-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 2", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document, delivery


def test_validity_reports_valid_for_a_document_with_no_replaces_or_withdrawn_by_edges(
    client, db_session
):
    document, _ = _seed_classified_document(db_session)

    response = client.get(
        f"/v1/documents/{document.id}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["replaced_by"] == []


def test_validity_reports_replaced_when_a_replaces_edge_points_at_this_document(
    client, db_session
):
    document, delivery = _seed_classified_document(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    successor = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 2", edition="2021", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=successor.id, jurisdiction="DE", may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=successor.id, to_document_id=document.id,
        edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    response = client.get(
        f"/v1/documents/{document.id}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "replaced"
    assert body["replaced_by"] == [str(successor.id)]


def test_validity_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(
        f"/v1/documents/{uuid.uuid4()}/validity", params={"jurisdiction": "DE"}
    )

    assert response.status_code == 404
