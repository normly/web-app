# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)


def _make_delivery(db_session, content_hash="sha256:document-embedding-fixture"):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def _make_document(db_session, delivery_id):
    return PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery_id,
    )


def test_upsert_document_embedding_creates_a_new_row(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)

    embedding = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    assert embedding.document_id == document.id
    assert embedding.model_name == "test-model"
    assert embedding.vector == [0.1] * 1024


def test_upsert_document_embedding_overwrites_the_existing_vector(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)
    first = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    second = repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.9] * 1024,
    )

    assert second.id == first.id
    assert second.vector == [0.9] * 1024


def test_list_documents_without_embedding_excludes_documents_with_one(db_session):
    delivery = _make_delivery(db_session)
    with_embedding = _make_document(db_session, delivery.id)
    without_embedding = PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 45001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    repo = PostgresDocumentEmbeddingRepository(db_session)
    repo.upsert_document_embedding(
        document_id=with_embedding.id, delivery_id=delivery.id, model_name="test-model",
        vector=[0.1] * 1024,
    )

    missing = repo.list_documents_without_embedding("test-model")

    missing_ids = {document.id for document in missing}
    assert without_embedding.id in missing_ids
    assert with_embedding.id not in missing_ids


def test_list_documents_without_embedding_is_scoped_to_the_model_name(db_session):
    delivery = _make_delivery(db_session)
    document = _make_document(db_session, delivery.id)
    repo = PostgresDocumentEmbeddingRepository(db_session)
    repo.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name="old-model",
        vector=[0.1] * 1024,
    )

    missing = repo.list_documents_without_embedding("new-model")

    assert document.id in {d.id for d in missing}
