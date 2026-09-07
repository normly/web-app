# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from sqlalchemy.orm import Session

from normly_core.graph.domain import DocumentDesignation, DocumentTitle
from normly_core.graph.postgres.repositories import (
    PostgresDocumentEmbeddingRepository,
    PostgresDocumentRepository,
)
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel


def build_document_embedding_text(
    designations: list[DocumentDesignation], titles: list[DocumentTitle]
) -> str | None:
    """
    "<primary designation> — <first title>" for the search embedding, or just
    the designation if no title exists yet, or None if there is no primary
    designation to embed at all (nothing indexed until one exists).

    DocumentTitle has no `is_primary` flag (unlike DocumentDesignation) --
    the first title in insertion order wins. Deliberate simplification:
    multi-title documents are rare today, and a real "best title" concept is
    not something this sub-project introduces.
    """
    primary_designation = next((d for d in designations if d.is_primary), None)
    if primary_designation is None:
        return None
    if not titles:
        return primary_designation.designation
    return f"{primary_designation.designation} — {titles[0].title}"


def backfill_document_embeddings(session: Session) -> int:
    """
    Create a DocumentEmbedding for every Document that doesn't have one yet
    for the current model. Idempotent: a document that already has one is
    left untouched here -- re-embedding an existing document only happens
    through re-ingestion (runner.py), which is the only place a document's
    designation/title can actually change.
    """
    document_repo = PostgresDocumentRepository(session)
    embedding_repo = PostgresDocumentEmbeddingRepository(session)
    embedding_model: EmbeddingModel | None = None
    created = 0

    for document in embedding_repo.list_documents_without_embedding(MODEL_NAME):
        designations = document_repo.list_designations(document.id)
        titles = document_repo.list_titles(document.id)
        text = build_document_embedding_text(designations, titles)
        if text is None:
            continue

        # build_document_embedding_text only returns non-None when a primary
        # designation exists in `designations`, so this is guaranteed to find
        # one. Its delivery_id -- not document.created_via_delivery_id -- is
        # the delivery that actually produced the text just embedded: a
        # document can be created empty by one delivery and get its first
        # designation from a later, different delivery, and lineage must
        # point at the latter. This also can't reference a withdrawn
        # delivery: revoke_delivery's cascade deletes DocumentDesignationORM
        # rows for its own delivery_id, so a designation only shows up here
        # while its delivery is still active.
        primary_designation = next(d for d in designations if d.is_primary)

        if embedding_model is None:
            embedding_model = EmbeddingModel()
        embedding_repo.upsert_document_embedding(
            document_id=document.id,
            delivery_id=primary_designation.delivery_id,
            model_name=MODEL_NAME,
            vector=embedding_model.embed(text),
        )
        created += 1

    return created
