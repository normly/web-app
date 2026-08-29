# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresDocumentRepository

from normly_api.dependencies import get_session
from normly_api.routers.documents import document_to_response
from normly_api.schemas import DocumentSearchResponse

search_router = APIRouter(prefix="/v1/documents", tags=["search"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@search_router.get("/search", response_model=DocumentSearchResponse)
def search_documents_endpoint(
    jurisdiction: str, q: str | None = None, issuer: str | None = None,
    limit: int = _DEFAULT_LIMIT, offset: int = 0,
    session: Session = Depends(get_session),
) -> DocumentSearchResponse:
    limit = min(limit, _MAX_LIMIT)
    doc_repo = PostgresDocumentRepository(session)
    documents, total = doc_repo.search_documents_for_jurisdiction(
        jurisdiction, q=q, issuer=issuer, limit=limit, offset=offset,
    )
    return DocumentSearchResponse(
        results=[document_to_response(d, session) for d in documents], total=total,
    )
