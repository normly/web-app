# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresRightsRepository,
)

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import RightsClassificationResponse

rights_router = APIRouter(prefix="/v1/documents", tags=["rights"])


@rights_router.get(
    "/{document_id}/rights", response_model=RightsClassificationResponse,
    responses=NOT_FOUND_RESPONSE,
)
def get_rights(
    document_id: uuid.UUID, jurisdiction: str, session: Session = Depends(get_session),
) -> RightsClassificationResponse:
    # Same gate as GET .../validity: a document not visible in this
    # jurisdiction must 404, not silently confirm or deny anything about it.
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_for_jurisdiction(document_id, jurisdiction) is None:
        raise HTTPException(status_code=404, detail="document not found")

    classification = PostgresRightsRepository(session).get_classification(document_id, jurisdiction)
    if classification is None:
        # Structurally impossible: get_document_for_jurisdiction's own gate
        # already requires a matching, unrevoked RightsClassification row to
        # exist for this exact (document_id, jurisdiction) pair. Reaching
        # here means that invariant broke -- raise loudly rather than return
        # a response that quietly claims "no rights info" for a document the
        # caller was just told is visible.
        raise RuntimeError(
            f"document {document_id} passed the jurisdiction gate for "
            f"{jurisdiction!r} but has no rights classification"
        )

    return RightsClassificationResponse(
        jurisdiction=classification.jurisdiction, may_process=classification.may_process,
        may_index_fulltext=classification.may_index_fulltext,
        may_cite_passages=classification.may_cite_passages,
        may_export_free=classification.may_export_free,
        legal_basis_reference=classification.legal_basis_reference,
    )
