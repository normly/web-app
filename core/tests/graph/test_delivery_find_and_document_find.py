# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def test_find_delivery_returns_none_when_absent(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)

    assert delivery_repo.find_delivery(source.id, "sha256:never-seen") is None


def test_find_delivery_returns_existing_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery_repo = PostgresDeliveryRepository(db_session)
    created = delivery_repo.record_delivery(
        source_id=source.id, content_hash="sha256:find-me", ingested_at=datetime.now(timezone.utc)
    )

    found = delivery_repo.find_delivery(source.id, "sha256:find-me")

    assert found is not None
    assert found.id == created.id


def test_find_by_designation_returns_none_when_absent(db_session):
    doc_repo = PostgresDocumentRepository(db_session)
    assert doc_repo.find_by_designation("CEN", "EN 0000:0000") is None


def test_find_by_designation_returns_matching_document(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:designation-find", ingested_at=datetime.now(timezone.utc)
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

    found = doc_repo.find_by_designation("CEN", "EN ISO 12100:2010")

    assert found is not None
    assert found.id == document.id
