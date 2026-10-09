# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWorkRepository,
)


def _seed_document(
    db_session, *, issuer, designation, jurisdiction="DE", content_hash, work_id=None,
):
    source = PostgresSourceRepository(db_session).create_source(
        publisher=issuer, retrieval_path="https://example.de", legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE", reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer=issuer, origin_number=designation, edition="2013", part=None,
        delivery_id=delivery.id, work_id=work_id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer=issuer, designation=designation, language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction=jurisdiction, may_process=True,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=True,
        legal_basis_reference="§ 5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="test", delivery_id=delivery.id,
    )
    return document


def test_search_endpoint_returns_a_work_grouped_result(client, db_session):
    document = _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-1",
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Vorschrift 1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["work_id"] == str(document.work_id)
    assert body["results"][0]["best_match"]["id"] == str(document.id)
    assert body["results"][0]["other_editions_count"] == 0


def test_search_endpoint_groups_two_documents_in_the_same_work(client, db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    _seed_document(
        db_session, issuer="DIN", designation="EN ISO 9001:2018", content_hash="sha256:endpoint-work-1",
        work_id=work.id,
    )
    _seed_document(
        db_session, issuer="BS", designation="EN ISO 9001:2018 UK",
        content_hash="sha256:endpoint-work-2", work_id=work.id,
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "ISO 9001"},
    )

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["other_editions_count"] == 1


def test_search_endpoint_finds_a_semantic_match_via_the_query_embedding(
    client, db_session, fake_embedding_model,
):
    # fake_embedding_model (api/tests/conftest.py) maps text to a one-hot
    # vector keyed by hash(text) % 1024 -- it's the SAME fixture instance the
    # `client` fixture wired up as the app's get_embedding_model override, so
    # embedding "Absturzsicherung" here produces exactly the vector the
    # running app will compute for that same query text. Pre-loading a
    # DocumentEmbedding with that vector and then searching for that exact
    # text proves the query embedding is actually computed and passed
    # through to Tier 2 end-to-end, without needing the real model.
    source = PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://example.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:endpoint-semantic",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="DGUV Vorschrift 38", edition="2013", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="DGUV", designation="DGUV Vorschrift 38", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    PostgresRightsRepository(db_session).classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="test", delivery_id=delivery.id,
    )
    vector = fake_embedding_model.embed_query("Absturzsicherung")
    PostgresDocumentEmbeddingRepository(db_session).upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id,
        model_name="intfloat/multilingual-e5-large", vector=vector,
    )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "q": "Absturzsicherung"},
    )

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["best_match"]["id"] == str(document.id)


def test_search_endpoint_returns_400_when_jurisdiction_is_missing(client, db_session):
    response = client.get("/v1/documents/search", params={"q": "Vorschrift"})

    assert response.status_code == 400


def test_search_endpoint_with_no_query_returns_everything_in_the_jurisdiction(client, db_session):
    _seed_document(
        db_session, issuer="DGUV", designation="DGUV Vorschrift 1", content_hash="sha256:endpoint-2",
    )

    response = client.get("/v1/documents/search", params={"jurisdiction": "DE"})

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_endpoint_respects_limit(client, db_session):
    for n in range(3):
        _seed_document(
            db_session, issuer="DGUV", designation=f"DGUV Vorschrift {n}",
            content_hash=f"sha256:endpoint-limit-{n}",
        )

    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": 2},
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["results"]) == 2


def test_search_endpoint_rejects_a_negative_limit_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": -1},
    )

    assert response.status_code == 400


def test_search_endpoint_rejects_a_negative_offset_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "offset": -1},
    )

    assert response.status_code == 400


def test_search_endpoint_rejects_a_limit_above_the_maximum_as_400(client, db_session):
    response = client.get(
        "/v1/documents/search", params={"jurisdiction": "DE", "limit": 101},
    )

    assert response.status_code == 400
