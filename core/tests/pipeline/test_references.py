# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference
from normly_core.pipeline.references import extract_references


def _setup(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:references-fixture",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    standard = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    return doc_repo, delivery, standard


def test_extract_references_creates_edge_when_target_exists(db_session):
    doc_repo, delivery, standard = _setup(db_session)
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=legal_act.id, issuer="EU", designation="2006/42/EC", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=uuid.uuid4(),
        content_hash="sha256:ref-record", raw_designation="EN ISO 12100:2010",
        raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )

    extract_references(record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo)

    edges = edge_repo.list_edges_for_jurisdiction(standard.id, "EU")
    # No rights classification exists yet in this test, so the gated list is empty by
    # design (REQ-PIPE-004) — assert directly against the ORM instead to prove the edge
    # was actually created, independent of the rights gate.
    from normly_core.graph.postgres.orm import EdgeORM
    from sqlalchemy import select

    created = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == legal_act.id
        )
    ).scalar_one_or_none()
    assert created is not None
    assert created.edge_type == EdgeType.BASED_ON_LAW


def test_extract_references_enqueues_case_when_target_missing(db_session):
    doc_repo, delivery, standard = _setup(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=uuid.uuid4(), content_hash="sha256:ref-missing-target",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="9999/99/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )

    extract_references(record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo)

    pending = identity_repo.list_pending_cases()
    assert any(c.reason == "reference_target_not_found" for c in pending)
