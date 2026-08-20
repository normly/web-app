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


def _seed_two_documents_with_an_edge(
    db_session, *, edge_type=EdgeType.BASED_ON_LAW, layer=Layer.FREE
):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:api-edges-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    rights_repo = PostgresRightsRepository(db_session)
    for doc in (standard, legal_act):
        rights_repo.classify(
            document_id=doc.id, jurisdiction="EU", may_process=True,
            may_index_fulltext=False, may_cite_passages=False, may_export_free=True,
            legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
            classified_by="test", delivery_id=delivery.id,
        )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=standard.id, to_document_id=legal_act.id, edge_type=edge_type,
        jurisdiction=None, layer=layer, delivery_id=delivery.id,
    )
    return standard, legal_act


def test_edges_lists_relationships_for_a_classified_document(client, db_session):
    standard, legal_act = _seed_two_documents_with_an_edge(db_session)

    response = client.get(f"/v1/documents/{standard.id}/edges", params={"jurisdiction": "EU"})

    assert response.status_code == 200
    edges = response.json()
    assert len(edges) == 1
    assert edges[0]["to_document_id"] == str(legal_act.id)
    assert edges[0]["edge_type"] == "based_on_law"


def test_edges_filters_by_edge_type(client, db_session):
    standard, _ = _seed_two_documents_with_an_edge(db_session, edge_type=EdgeType.REFERENCES)

    matching = client.get(
        f"/v1/documents/{standard.id}/edges",
        params={"jurisdiction": "EU", "edge_type": "references"},
    )
    non_matching = client.get(
        f"/v1/documents/{standard.id}/edges",
        params={"jurisdiction": "EU", "edge_type": "replaces"},
    )

    assert len(matching.json()) == 1
    assert len(non_matching.json()) == 0


def test_edges_returns_empty_list_for_a_document_not_classified_in_this_jurisdiction(
    client, db_session
):
    standard, _ = _seed_two_documents_with_an_edge(db_session)

    response = client.get(f"/v1/documents/{standard.id}/edges", params={"jurisdiction": "FR"})

    assert response.status_code == 200
    assert response.json() == []


def test_edges_returns_404_for_an_unknown_document_id(client, db_session):
    response = client.get(
        f"/v1/documents/{uuid.uuid4()}/edges", params={"jurisdiction": "EU"}
    )

    assert response.status_code == 404
