# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
)


def _seed_document(db_session, *, jurisdiction="DE", content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="Vorschrift 1", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=False, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_rights_endpoint_returns_the_classification(client, db_session):
    document = _seed_document(db_session, content_hash="sha256:rights-endpoint-1")

    response = client.get(f"/v1/documents/{document.id}/rights", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    body = response.json()
    assert body["jurisdiction"] == "DE"
    assert body["may_process"] is True
    assert body["may_cite_passages"] is False
    assert body["legal_basis_reference"] == "§ 5 UrhG"


def test_rights_endpoint_returns_404_for_a_document_not_visible_in_jurisdiction(client, db_session):
    document = _seed_document(db_session, content_hash="sha256:rights-endpoint-2", jurisdiction="FR")

    response = client.get(f"/v1/documents/{document.id}/rights", params={"jurisdiction": "DE"})

    assert response.status_code == 404
