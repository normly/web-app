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

    # Known limitation, deliberate and documented: provenance is resolved from
    # created_via_delivery_id -- the delivery that FIRST produced this document
    # -- without asking whether that delivery has since been withdrawn. A
    # document may remain readable through a later delivery's rights
    # classification while the source block still describes the withdrawn one.
    # Resolving "the currently active delivery for this document" is a
    # separate design question (there is no such concept in the repository
    # layer yet, and answering it touches the lineage model that revocation
    # depends on). It is not settled here.
    delivery = PostgresDeliveryRepository(session).get_delivery(document.created_via_delivery_id)
    if delivery is None:
        # Lineage is mandatory ("Abstammung mitführen"), so this is a broken
        # invariant, not a client error. Raise something explicit: an
        # AttributeError on None would surface as an anonymous 500 with no
        # indication of which link in the chain is missing. Neither is caught
        # by the 503 handler -- a defect must not read as a retryable outage.
        raise RuntimeError(
            f"document {document.id} references unknown delivery "
            f"{document.created_via_delivery_id}"
        )

    source = PostgresSourceRepository(session).get_source(delivery.source_id)
    if source is None:
        raise RuntimeError(
            f"delivery {delivery.id} references unknown source {delivery.source_id}"
        )

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


@documents_router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> DocumentResponse:
    doc_repo = PostgresDocumentRepository(session)
    gated = doc_repo.get_document_for_jurisdiction(document_id, jurisdiction)
    if gated is None:
        raise HTTPException(status_code=404, detail="document not found")

    return _document_to_response(gated, session)
