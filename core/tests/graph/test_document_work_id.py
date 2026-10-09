# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _make_delivery(db_session, content_hash="sha256:work-id-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_create_document_without_work_id_gets_its_own_new_work(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )

    assert document.work_id is not None
    work = PostgresWorkRepository(db_session).get_work(document.work_id)
    assert work.created_via == WorkCreatedVia.AUTO_MATCHED


def test_create_document_without_work_id_gets_distinct_works(db_session):
    delivery = _make_delivery(db_session)
    doc_repo = PostgresDocumentRepository(db_session)

    first = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )

    assert first.work_id != second.work_id


def test_create_document_honours_an_explicit_work_id(db_session):
    delivery = _make_delivery(db_session)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    doc_repo = PostgresDocumentRepository(db_session)

    first = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=work.id,
    )
    second = doc_repo.create_document(
        origin_issuer="BS", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id, work_id=work.id,
    )

    assert first.work_id == work.id
    assert second.work_id == work.id
