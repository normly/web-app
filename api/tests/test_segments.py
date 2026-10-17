# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSegmentRepository,
    PostgresSourceRepository,
)


def _seed(db_session, *, content_hash, may_cite_passages=True, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://www.dguv.de/publikationen",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    document = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="DGUV", origin_number=content_hash, edition="2013", part=None,
        delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=may_cite_passages, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="§ 1 Geltungsbereich", text="Diese Vorschrift gilt für Unternehmer.",
        language="de",
    )
    return document, delivery, segment


def test_citable_segments_are_returned(client, db_session):
    document, _, segment = _seed(db_session, content_hash="sha256:api-segments-1")

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json() == [{
        "id": str(segment.id), "sequence_number": 1, "heading": "§ 1 Geltungsbereich",
        "text": "Diese Vorschrift gilt für Unternehmer.",
    }]


def test_a_visible_but_not_citable_document_returns_an_empty_list(client, db_session):
    document, _, _ = _seed(
        db_session, content_hash="sha256:api-segments-2", may_cite_passages=False,
    )

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json() == []


def test_a_document_not_visible_in_the_jurisdiction_is_404(client, db_session):
    document, _, _ = _seed(
        db_session, content_hash="sha256:api-segments-3", jurisdiction="FR",
    )

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 404


def test_an_unknown_document_is_404(client):
    response = client.get(f"/v1/documents/{uuid.uuid4()}/segments", params={"jurisdiction": "DE"})

    assert response.status_code == 404


def test_a_revoked_delivery_hides_the_document(client, db_session):
    document, delivery, _ = _seed(db_session, content_hash="sha256:api-segments-4")
    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    response = client.get(f"/v1/documents/{document.id}/segments", params={"jurisdiction": "DE"})

    # Revocation removes the only classification, so the document itself is
    # no longer visible -- the same 404 as an unclassified document.
    assert response.status_code == 404
