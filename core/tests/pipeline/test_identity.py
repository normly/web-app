# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.domain import RawRecord
from normly_core.pipeline.identity import (
    ParsedDesignation,
    UnparseableDesignationError,
    parse_designation,
    resolve,
)


def test_parse_designation_splits_number_and_edition():
    parsed = parse_designation("EN ISO 12100:2010")
    assert parsed == ParsedDesignation(number="EN ISO 12100", edition="2010")


def test_parse_designation_without_edition():
    parsed = parse_designation("DGUV Vorschrift 1")
    assert parsed == ParsedDesignation(number="DGUV Vorschrift 1", edition=None)


def test_parse_designation_rejects_empty_string():
    with pytest.raises(UnparseableDesignationError):
        parse_designation("   ")


def _make_record(raw_designation, raw_issuer, edition=None):
    return RawRecord(
        source_id=uuid.uuid4(),
        content_hash="sha256:identity-test",
        raw_designation=raw_designation,
        raw_issuer=raw_issuer,
        raw_title=None,
        edition=edition,
        full_text=None,
    )


def test_resolve_finds_existing_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-existing",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 12100", edition="2010", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 12100:2010",
        language="en", edition=None, is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("EN ISO 12100:2010", "CEN")
    result = resolve(record, doc_repo)

    assert result.document_id == document.id
    assert result.is_new is False
    assert result.is_ambiguous is False


def test_resolve_reports_new_document(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("EN ISO 99999:2030", "CEN")

    result = resolve(record, doc_repo)

    assert result.document_id is None
    assert result.is_new is True
    assert result.is_ambiguous is False


def test_resolve_reports_ambiguous_for_unparseable_designation(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("   ", "CEN")

    result = resolve(record, doc_repo)

    assert result.is_ambiguous is True
    assert result.reason == "unparseable_designation"


def test_resolve_finds_the_same_edition_already_ingested(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-same-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2013-11-01")
    result = resolve(record, doc_repo)

    assert result.document_id == document.id
    assert result.is_new is False
    assert result.previous_edition_document_id is None


def test_resolve_reports_a_new_edition_of_a_known_designation(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-new-edition",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    old_document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 1", edition="2013-11-01",
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=old_document.id, issuer="DGUV", designation="DGUV Vorschrift 1",
        language="de", edition="2013-11-01", is_primary=True, delivery_id=delivery.id,
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2022-06-01")
    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id == old_document.id


def test_resolve_reports_new_document_with_no_previous_edition_for_a_first_appearance(
    db_session,
):
    doc_repo = PostgresDocumentRepository(db_session)
    record = _make_record("DGUV Vorschrift 999", "DGUV", edition="2026-01-01")

    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id is None


def _ingest_dguv_edition(doc_repo, delivery, *, designation: str, edition: str):
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number=designation, edition=edition,
        part=None, delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation=designation,
        language="de", edition=edition, is_primary=True, delivery_id=delivery.id,
    )
    return document


def test_resolve_does_not_invert_the_replaces_edge_when_an_older_edition_arrives_late(
    db_session,
):
    """Reproduces the review's Critical finding: a 2022 edition is already
    known, and a 2013 archive edition of the SAME designation arrives later.
    The edition-less find_by_designation used to treat the 2022 document as
    the "previous edition" of the 2013 one, producing a backwards REPLACES
    edge. previous_edition_document_id must be None here -- 2013 has no
    predecessor among what's known, since find_previous_edition only looks
    strictly backward in edition order."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-out-of-order-archive",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    _ingest_dguv_edition(
        doc_repo, delivery, designation="DGUV Vorschrift 1", edition="2022-06-01"
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2013-11-01")
    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id is None


def test_resolve_finds_the_adjacent_predecessor_not_a_more_distant_edition(db_session):
    """With 2013 and 2022 already present, resolving a record for the 2019
    edition must link back to 2013 (the correct, adjacent predecessor), not
    2022 -- which is a later edition, not a predecessor at all."""
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:resolve-adjacent-predecessor",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    edition_2013 = _ingest_dguv_edition(
        doc_repo, delivery, designation="DGUV Vorschrift 1", edition="2013-11-01"
    )
    _ingest_dguv_edition(
        doc_repo, delivery, designation="DGUV Vorschrift 1", edition="2022-06-01"
    )

    record = _make_record("DGUV Vorschrift 1", "DGUV", edition="2019-01-01")
    result = resolve(record, doc_repo)

    assert result.is_new is True
    assert result.document_id is None
    assert result.previous_edition_document_id == edition_2013.id
