# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, Layer, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresIdentityResolutionRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference, RightsRule
from normly_core.pipeline.references import extract_references


def _rule(*, may_export_free: bool = True) -> RightsRule:
    return RightsRule(
        jurisdiction="EU", may_process=True, may_index_fulltext=False,
        may_cite_passages=False, may_export_free=may_export_free,
        legal_basis_reference="§ 5 UrhG",
    )


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

    extract_references(
        record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo, _rule()
    )

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
    assert created.layer == Layer.FREE


def test_extract_references_puts_edges_of_non_exportable_records_in_the_commercial_layer(
    db_session,
):
    from sqlalchemy import select

    from normly_core.graph.postgres.orm import EdgeORM

    doc_repo, delivery, standard = _setup(db_session)
    legal_act = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=legal_act.id, issuer="EU", designation="2006/42/EC", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = RawRecord(
        source_id=uuid.uuid4(), content_hash="sha256:ref-commercial",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.BASED_ON_LAW)
        ],
    )

    extract_references(
        record, standard.id, delivery.id, doc_repo,
        PostgresEdgeRepository(db_session), PostgresIdentityResolutionRepository(db_session),
        _rule(may_export_free=False),
    )

    created = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == legal_act.id
        )
    ).scalar_one()
    assert created.layer == Layer.COMMERCIAL


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

    extract_references(
        record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo, _rule()
    )

    pending = identity_repo.list_pending_cases()
    assert any(c.reason == "reference_target_not_found" for c in pending)


def test_extract_references_neither_edges_nor_enqueues_a_case_for_a_self_referential_reference(
    db_session,
):
    # Simulates a DGUV re-edition sharing its predecessor's exact designation
    # string: identity.resolve() used to treat the ingestion as an update to
    # the SAME existing document, so the REPLACES reference this adapter
    # attaches ended up resolving, via find_by_designation, to the record's
    # own document -- caught by the (still-present, defense-in-depth)
    # `target.id == document_id` guard below, which used to enqueue a
    # self_referential_reference case for this exact scenario.
    #
    # This sub-project's own fix (the top-of-loop own-designation guard)
    # intercepts this case earlier and more precisely: a reference naming
    # the record's own (issuer, designation) is now silently skipped before
    # find_by_designation ever runs, so this scenario produces NEITHER an
    # edge NOR a case at all -- see
    # test_extract_references_skips_a_reference_naming_the_records_own_designation
    # for the dedicated test of that new guard. This test is kept to prove
    # the OLD failure mode (a spurious case) no longer happens for this
    # input, now that the new guard makes the older `target.id ==
    # document_id` fallback unreachable for it.
    from sqlalchemy import select

    from normly_core.graph.postgres.orm import EdgeORM

    doc_repo, delivery, standard = _setup(db_session)
    doc_repo.add_designation(
        document_id=standard.id, issuer="CEN", designation="EN ISO 12100:2010", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=uuid.uuid4(), content_hash="sha256:ref-self-referential",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(
                target_issuer="CEN", target_designation="EN ISO 12100:2010",
                edge_type=EdgeType.REPLACES,
            )
        ],
    )

    extract_references(
        record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo, _rule()
    )

    self_loop = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == standard.id
        )
    ).scalar_one_or_none()
    assert self_loop is None

    pending = identity_repo.list_pending_cases()
    assert not any(c.reason == "self_referential_reference" for c in pending)
    assert pending == []


def test_extract_references_skips_a_reference_naming_the_records_own_designation(db_session):
    """The new guard: a reference naming the record's OWN (issuer,
    designation) -- e.g. a DGUV re-edition's Inkrafttreten section citing its
    own bare designation with no edition qualifier -- must be silently
    skipped. That lineage is already handled by identity.resolve()'s
    find_previous_edition + runner.py's own REPLACES-edge creation; running
    it again here through the edition-blind find_by_designation would either
    hit the record's own just-created document (a spurious
    self_referential_reference case) or an unrelated same-designation
    document picked by insertion order. Neither an edge nor ANY case should
    be produced for this reference."""
    doc_repo, delivery, standard = _setup(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    identity_repo = PostgresIdentityResolutionRepository(db_session)
    record = RawRecord(
        source_id=uuid.uuid4(), content_hash="sha256:ref-own-designation",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(
                target_issuer="CEN", target_designation="EN ISO 12100:2010",
                edge_type=EdgeType.REPLACES,
            )
        ],
    )

    extract_references(
        record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo, _rule()
    )

    from sqlalchemy import select

    from normly_core.graph.postgres.orm import EdgeORM

    any_edge_from_standard = db_session.execute(
        select(EdgeORM).where(EdgeORM.from_document_id == standard.id)
    ).scalar_one_or_none()
    assert any_edge_from_standard is None
    assert identity_repo.list_pending_cases() == []


def test_extract_references_processes_other_references_unaffected_by_the_own_designation_guard(
    db_session,
):
    """A mix: one reference names the record's own designation (skipped by
    the new guard) and a second names a genuinely different, resolvable
    designation (must still create a real edge, unaffected by the guard)."""
    from sqlalchemy import select

    from normly_core.graph.postgres.orm import EdgeORM

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
        source_id=uuid.uuid4(), content_hash="sha256:ref-mixed-own-and-other",
        raw_designation="EN ISO 12100:2010", raw_issuer="CEN", raw_title=None, full_text=None,
        raw_references=[
            RawReference(
                target_issuer="CEN", target_designation="EN ISO 12100:2010",
                edge_type=EdgeType.REPLACES,
            ),
            RawReference(
                target_issuer="EU", target_designation="2006/42/EC",
                edge_type=EdgeType.BASED_ON_LAW,
            ),
        ],
    )

    extract_references(
        record, standard.id, delivery.id, doc_repo, edge_repo, identity_repo, _rule()
    )

    self_loop = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == standard.id
        )
    ).scalar_one_or_none()
    assert self_loop is None

    real_edge = db_session.execute(
        select(EdgeORM).where(
            EdgeORM.from_document_id == standard.id, EdgeORM.to_document_id == legal_act.id
        )
    ).scalar_one_or_none()
    assert real_edge is not None
    assert real_edge.edge_type == EdgeType.BASED_ON_LAW

    assert identity_repo.list_pending_cases() == []
