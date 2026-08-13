# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV",
        retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    delivery_a = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:revoke-a", ingested_at=datetime.now(timezone.utc)
    )
    delivery_b = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:revoke-b", ingested_at=datetime.now(timezone.utc)
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery_a.id,
    )
    other = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2026", part=None,
        delivery_id=delivery_a.id,
    )
    return document, other, delivery_a, delivery_b, doc_repo, delivery_repo


def test_revoking_a_delivery_locks_only_its_own_edges(db_session):
    document, other, delivery_a, delivery_b, doc_repo, delivery_repo = _setup(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    rights_repo.classify(
        document_id=other.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery_a.id,
    )
    edge_from_a = edge_repo.create_edge(
        from_document_id=document.id, to_document_id=other.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery_a.id,
    )
    edge_from_b = edge_repo.create_edge(
        from_document_id=other.id, to_document_id=document.id, edge_type=EdgeType.REFERENCES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery_b.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    edges_de = edge_repo.list_edges_for_jurisdiction(other.id, "DE")
    remaining_ids = {e.id for e in edges_de}
    assert edge_from_a.id not in remaining_ids


def test_document_stays_readable_when_a_second_delivery_still_supports_it(db_session):
    document, _other, delivery_a, delivery_b, doc_repo, delivery_repo = _setup(db_session)
    rights_repo = PostgresRightsRepository(db_session)

    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="J. Weber",
        delivery_id=delivery_a.id,
    )
    doc_repo.add_title(
        document_id=document.id, language="de", title="DGUV Regel 1",
        delivery_id=delivery_b.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    assert doc_repo.get_document_for_jurisdiction(document.id, "DE") is None
    remaining_titles = doc_repo.list_titles(document.id)
    assert len(remaining_titles) == 1


def test_designations_from_revoked_delivery_are_removed(db_session):
    document, _other, delivery_a, _delivery_b, doc_repo, delivery_repo = _setup(db_session)

    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Regel 1",
        language="de", edition=None, is_primary=True, delivery_id=delivery_a.id,
    )

    delivery_repo.revoke_delivery(delivery_a.id)

    assert doc_repo.list_designations(document.id) == []
