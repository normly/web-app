# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _make_two_documents(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:edge-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id,
    )
    return old, new, delivery


def test_create_edge(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge = edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    assert edge.edge_type == EdgeType.REPLACES
    assert edge.revoked_at is None


def test_duplicate_active_edge_is_rejected(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    with pytest.raises(Exception):
        edge_repo.create_edge(
            from_document_id=new.id,
            to_document_id=old.id,
            edge_type=EdgeType.REPLACES,
            jurisdiction=None,
            layer=Layer.FREE,
            delivery_id=delivery.id,
        )


def test_edges_only_listed_when_target_is_rights_classified(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id,
        to_document_id=old.id,
        edge_type=EdgeType.REPLACES,
        jurisdiction=None,
        layer=Layer.FREE,
        delivery_id=delivery.id,
    )

    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []

    rights_repo.classify(
        document_id=old.id,
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

    edges = edge_repo.list_edges_for_jurisdiction(new.id, "DE")
    assert len(edges) == 1
    assert edges[0].to_document_id == old.id
