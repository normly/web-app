# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer
from normly_core.graph.postgres.orm import EdgeORM, RightsClassificationORM
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


def _classify(db_session, document, delivery, jurisdiction="DE", may_process=True):
    PostgresRightsRepository(db_session).classify(
        document_id=document.id,
        jurisdiction=jurisdiction,
        may_process=may_process,
        may_index_fulltext=may_process,
        may_cite_passages=may_process,
        may_export_free=may_process,
        legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc),
        classified_by="J. Weber",
        delivery_id=delivery.id,
    )


def test_re_asserting_an_identical_active_edge_returns_the_same_edge(db_session):
    """
    Re-running an ingestion step is the normal case, not an error
    (CLAUDE.md: "Verarbeitungsschritte idempotent").
    """
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    first = edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    second = edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    assert second.id == first.id
    rows = db_session.execute(
        select(EdgeORM).where(EdgeORM.from_document_id == new.id)
    ).scalars().all()
    assert len(rows) == 1


def test_database_still_rejects_a_duplicate_active_edge(db_session):
    """
    Idempotency lives in the repository; the partial unique index stays the
    backstop for anything writing past it.
    """
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    with pytest.raises(IntegrityError):
        db_session.add(
            EdgeORM(
                id=uuid.uuid4(), from_document_id=new.id, to_document_id=old.id,
                edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
                delivery_id=delivery.id, revoked_at=None,
            )
        )
        db_session.flush()


def test_edges_only_listed_when_target_is_rights_classified(db_session):
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
    _classify(db_session, new, delivery)

    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []

    _classify(db_session, old, delivery)

    edges = edge_repo.list_edges_for_jurisdiction(new.id, "DE")
    assert len(edges) == 1
    assert edges[0].to_document_id == old.id


def test_edges_are_hidden_when_the_source_document_is_not_readable(db_session):
    """
    Listing a document's edges reveals that the document exists and what it
    references. That must be gated on the source too, not only the target.
    """
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)

    edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    # Target readable in DE, source not classified at all.
    _classify(db_session, old, delivery)

    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []

    # A source classified but explicitly not processable stays hidden as well.
    _classify(db_session, new, delivery, may_process=False)
    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []

    # And a revoked source classification hides the edges again.
    _classify(db_session, new, delivery, may_process=True)
    assert len(edge_repo.list_edges_for_jurisdiction(new.id, "DE")) == 1

    source_rights = db_session.get(RightsClassificationORM, (new.id, "DE"))
    source_rights.revoked_at = datetime.now(timezone.utc)
    db_session.flush()

    assert edge_repo.list_edges_for_jurisdiction(new.id, "DE") == []
