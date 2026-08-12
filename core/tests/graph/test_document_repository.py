# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id,
        content_hash="sha256:doc-fixture",
        ingested_at=datetime.now(timezone.utc),
    )


def test_create_and_get_document(db_session):
    delivery = _make_delivery(db_session)
    repo = PostgresDocumentRepository(db_session)

    document = repo.create_document(
        origin_issuer="ISO",
        origin_number="9001",
        edition="2015",
        part=None,
        delivery_id=delivery.id,
    )

    fetched = repo.get_document(document.id)
    assert fetched == document
    assert fetched.created_via_delivery_id == delivery.id
