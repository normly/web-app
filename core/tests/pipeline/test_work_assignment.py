# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord, RawReference
from normly_core.pipeline.work_assignment import determine_work_assignment


def _make_delivery(db_session, content_hash="sha256:work-assignment-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_record(raw_references):
    return RawRecord(
        source_id=None, content_hash="sha256:record", raw_designation="BS EN ISO 9001:2018",
        raw_issuer="BS", raw_title=None, full_text=None, raw_references=raw_references,
    )


def test_no_references_means_no_signal(db_session):
    doc_repo = PostgresDocumentRepository(db_session)

    result = determine_work_assignment(_make_record([]), doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_a_references_only_edge_gives_no_signal(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    target = doc_repo.create_document(
        origin_issuer="EU", origin_number="2006/42/EC", edition="2006", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=target.id, issuer="EU", designation="2006/42/EC", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [RawReference(target_issuer="EU", target_designation="2006/42/EC", edge_type=EdgeType.REFERENCES)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_an_adopted_from_signal_to_a_known_document_reuses_its_work(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    target = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=target.id, issuer="DIN", designation="EN ISO 9001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2018", edge_type=EdgeType.ADOPTED_FROM)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id == target.work_id
    assert result.is_ambiguous is False


def test_a_signal_to_an_unresolvable_target_is_treated_as_no_signal(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record(
        [RawReference(target_issuer="DIN", target_designation="EN ISO 99999:2030", edge_type=EdgeType.REPLACES)]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.work_id is None
    assert result.is_ambiguous is False


def test_conflicting_work_linking_signals_are_ambiguous(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="ISO", origin_number="9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=first.id, issuer="DIN", designation="EN ISO 9001:2015", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=second.id, issuer="ISO", designation="9001:2015", language="en",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    record = _make_record(
        [
            RawReference(target_issuer="DIN", target_designation="EN ISO 9001:2015", edge_type=EdgeType.ADOPTED_FROM),
            RawReference(target_issuer="ISO", target_designation="9001:2015", edge_type=EdgeType.REPLACES),
        ]
    )

    result = determine_work_assignment(record, doc_repo)

    assert result.is_ambiguous is True
    assert result.reason == "conflicting_work_signal"
    assert result.candidate_work_ids == frozenset({first.work_id, second.work_id})
