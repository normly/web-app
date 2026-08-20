# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Document
from normly_core.graph.postgres.repositories import (
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
)

from normly_api.dependencies import get_session
from normly_api.schemas import (
    DesignationResponse,
    DocumentResponse,
    SourceResponse,
    TitleResponse,
)

documents_router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _document_to_response(document: Document, session: Session) -> DocumentResponse:
    """
    Build the full DocumentResponse for a document that has ALREADY passed the
    jurisdiction gate (get_document_for_jurisdiction returned non-None for it).
    Only after that gate may the ungated enrichment methods below run.
    """
    doc_repo = PostgresDocumentRepository(session)
    designations = [
        DesignationResponse(
            issuer=d.issuer, designation=d.designation, language=d.language,
            is_primary=d.is_primary,
        )
        for d in doc_repo.list_designations(document.id)
    ]
    titles = [
        TitleResponse(language=t.language, title=t.title)
        for t in doc_repo.list_titles(document.id)
    ]

    delivery = PostgresDeliveryRepository(session).get_delivery(document.created_via_delivery_id)
    source = PostgresSourceRepository(session).get_source(delivery.source_id)
    source_response = SourceResponse(
        publisher=source.publisher, retrieval_path=source.retrieval_path,
        legal_basis_category=source.legal_basis_category.value,
        jurisdiction=source.jurisdiction,
    )

    return DocumentResponse(
        id=document.id, origin_issuer=document.origin_issuer,
        origin_number=document.origin_number, edition=document.edition, part=document.part,
        designations=designations, titles=titles, source=source_response,
    )


@documents_router.get("", response_model=DocumentResponse)
def search_documents(
    issuer: str, designation: str, jurisdiction: str,
    session: Session = Depends(get_session),
) -> DocumentResponse:
    doc_repo = PostgresDocumentRepository(session)
    found = doc_repo.find_by_designation(issuer, designation)
    if found is None:
        raise HTTPException(status_code=404, detail="no document matches this designation")

    gated = doc_repo.get_document_for_jurisdiction(found.id, jurisdiction)
    if gated is None:
        raise HTTPException(
            status_code=404, detail="no document matches this designation"
        )

    return _document_to_response(gated, session)
