# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresDocumentRepository
from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel

from normly_api.dependencies import get_embedding_model, get_session
from normly_api.routers.documents import document_to_response
from normly_api.schemas import WorkSearchResponse, WorkSearchResultResponse

search_router = APIRouter(prefix="/v1/documents", tags=["search"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@search_router.get("/search", response_model=WorkSearchResponse)
def search_documents_endpoint(
    jurisdiction: str, q: str | None = None, issuer: str | None = None,
    # Declarative bounds rather than a manual min() clamp: the clamp only
    # capped the upper end, so a negative value reached SQL and came back as a
    # 503 -- an unauthenticated caller could raise the exact signal that means
    # "the database is down" at will, and the caller was told to retry a
    # request that can never succeed. These also document themselves in the
    # OpenAPI schema.
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    embedding_model: EmbeddingModel = Depends(get_embedding_model),
) -> WorkSearchResponse:
    query_vector = embedding_model.embed_query(q) if q is not None else None
    doc_repo = PostgresDocumentRepository(session)
    hits, total = doc_repo.search_works_for_jurisdiction(
        jurisdiction, q=q, issuer=issuer, query_vector=query_vector,
        embedding_model_name=MODEL_NAME if query_vector is not None else None,
        limit=limit, offset=offset,
    )
    return WorkSearchResponse(
        results=[
            WorkSearchResultResponse(
                work_id=hit.work_id,
                best_match=document_to_response(hit.best_match, session),
                other_editions_count=hit.other_editions_count,
            )
            for hit in hits
        ],
        total=total,
    )
