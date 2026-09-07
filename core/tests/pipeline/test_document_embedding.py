# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import DocumentDesignation, DocumentTitle, LegalBasisCategory
from normly_core.graph.postgres.orm import DocumentEmbeddingORM
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)
from normly_core.pipeline.document_embedding import (
    backfill_document_embeddings,
    build_document_embedding_text,
)


def _designation(designation: str, *, is_primary: bool) -> DocumentDesignation:
    return DocumentDesignation(
        id=uuid.uuid4(), document_id=uuid.uuid4(), issuer="CEN", designation=designation,
        language="de", edition=None, is_primary=is_primary, delivery_id=uuid.uuid4(),
    )


def _title(title: str) -> DocumentTitle:
    return DocumentTitle(
        id=uuid.uuid4(), document_id=uuid.uuid4(), language="de", title=title,
        delivery_id=uuid.uuid4(),
    )


def test_combines_primary_designation_and_first_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]
    titles = [_title("Qualitätsmanagementsysteme")]

    text = build_document_embedding_text(designations, titles)

    assert text == "EN ISO 9001:2018 — Qualitätsmanagementsysteme"


def test_ignores_a_non_primary_designation_when_a_primary_one_exists():
    designations = [
        _designation("wrong-secondary", is_primary=False),
        _designation("EN ISO 9001:2018", is_primary=True),
    ]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_falls_back_to_designation_alone_when_there_is_no_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_returns_none_when_there_is_no_primary_designation():
    text = build_document_embedding_text([], [_title("Qualitätsmanagementsysteme")])

    assert text is None


def _make_delivery_for_backfill(db_session, content_hash):
    source = PostgresSourceRepository(db_session).create_source(
        publisher="EUR-Lex", retrieval_path="https://single-market-economy.ec.europa.eu",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="EU",
        reviewed_at=date(2026, 1, 15), responsible_person="J. Weber",
    )
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash=content_hash, ingested_at=datetime.now(timezone.utc)
    )


def test_backfill_creates_embeddings_for_documents_missing_one(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-1")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 9001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 9001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )

    created = backfill_document_embeddings(db_session)

    assert created == 1
    embedding_repo = PostgresDocumentEmbeddingRepository(db_session)
    assert document.id not in {
        d.id for d in embedding_repo.list_documents_without_embedding("intfloat/multilingual-e5-large")
    }


def test_backfill_is_idempotent(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-2")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 45001", edition="2018", part=None,
        delivery_id=delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 45001:2018", language="de",
        edition=None, is_primary=True, delivery_id=delivery.id,
    )
    backfill_document_embeddings(db_session)

    second_run_created = backfill_document_embeddings(db_session)

    assert second_run_created == 0


def test_backfill_attributes_lineage_to_the_designations_delivery_not_the_documents_creation_delivery(
    db_session,
):
    # The document is created (empty, no designation) by one delivery, and
    # only gets its primary designation -- the text actually embedded --
    # from a second, later, different delivery. Per "Abstammung mitführen"
    # the embedding's delivery_id must point at the delivery that produced
    # the content it derives from (the designation), not the one that
    # happened to first create the Document row.
    creation_delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-lineage-creation")
    designation_delivery = _make_delivery_for_backfill(
        db_session, "sha256:backfill-lineage-designation"
    )
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="CEN", origin_number="EN ISO 50001", edition="2018", part=None,
        delivery_id=creation_delivery.id,
    )
    doc_repo.add_designation(
        document_id=document.id, issuer="CEN", designation="EN ISO 50001:2018", language="de",
        edition=None, is_primary=True, delivery_id=designation_delivery.id,
    )

    created = backfill_document_embeddings(db_session)

    assert created == 1
    embedding = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalar_one()
    assert embedding.delivery_id == designation_delivery.id
    assert embedding.delivery_id != creation_delivery.id


def test_backfill_skips_a_document_with_no_primary_designation(db_session):
    delivery = _make_delivery_for_backfill(db_session, "sha256:backfill-3")
    # A document created directly via create_document with no add_designation
    # call has no primary designation -- build_document_embedding_text
    # returns None for it, and the backfill must not choke on that.
    PostgresDocumentRepository(db_session).create_document(
        origin_issuer="CEN", origin_number="EN ISO 14001", edition="2018", part=None,
        delivery_id=delivery.id,
    )

    created = backfill_document_embeddings(db_session)

    assert created == 0
