# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import EdgeType, LegalBasisCategory, Layer, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _seed_document(db_session, *, issuer, number, edition, work_id, content_hash, jurisdiction="DE"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher=issuer, retrieval_path="https://example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=number, edition=edition, part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=f"{number}:{edition}", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document, delivery


def test_work_endpoint_separates_editions_from_national_adoptions(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    din_2015, delivery = _seed_document(
        db_session, issuer="DIN", number="EN ISO 9001", edition="2015", work_id=work.id,
        content_hash="sha256:work-endpoint-1",
    )
    din_2018, _ = _seed_document(
        db_session, issuer="DIN", number="EN ISO 9001", edition="2018", work_id=work.id,
        content_hash="sha256:work-endpoint-2",
    )
    bs_2018, _ = _seed_document(
        db_session, issuer="BS", number="EN ISO 9001", edition="2018", work_id=work.id,
        content_hash="sha256:work-endpoint-3",
    )
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=din_2018.id, to_document_id=din_2015.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    edge_repo.create_edge(
        from_document_id=bs_2018.id, to_document_id=din_2018.id, edge_type=EdgeType.ADOPTED_FROM,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    response = client.get(
        f"/v1/documents/{din_2018.id}/work", params={"jurisdiction": "DE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["work_id"] == str(work.id)
    edition_ids = {e["document_id"] for e in body["editions"]}
    adoption_ids = {e["document_id"] for e in body["national_adoptions"]}
    assert edition_ids == {str(din_2015.id), str(din_2018.id)}
    assert adoption_ids == {str(bs_2018.id)}
    replaced = next(e for e in body["editions"] if e["document_id"] == str(din_2015.id))
    assert replaced["status"] == "replaced"


def test_work_endpoint_returns_404_for_a_document_not_visible_in_jurisdiction(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    document, _ = _seed_document(
        db_session, issuer="DGUV", number="Vorschrift 1", edition="2013", work_id=work.id,
        content_hash="sha256:work-endpoint-404", jurisdiction="FR",
    )

    response = client.get(f"/v1/documents/{document.id}/work", params={"jurisdiction": "DE"})

    assert response.status_code == 404
