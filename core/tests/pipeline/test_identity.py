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


def _make_record(raw_designation, raw_issuer):
    return RawRecord(
        source_id=uuid.uuid4(),
        content_hash="sha256:identity-test",
        raw_designation=raw_designation,
        raw_issuer=raw_issuer,
        raw_title=None,
        full_text=None,
    )


def test_resolve_finds_existing_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
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
