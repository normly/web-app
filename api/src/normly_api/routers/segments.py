# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresSegmentRepository,
)

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import SegmentResponse

segments_router = APIRouter(prefix="/v1/documents", tags=["segments"])


@segments_router.get(
    "/{document_id}/segments",
    response_model=list[SegmentResponse],
    responses=NOT_FOUND_RESPONSE,
)
def list_segments(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> list[SegmentResponse]:
    # Same non-disclosure as GET /v1/documents/{id}: a document that is not
    # visible in this jurisdiction is a 404, whether it exists or not.
    if PostgresDocumentRepository(session).get_document_for_jurisdiction(
        document_id, jurisdiction
    ) is None:
        raise HTTPException(status_code=404, detail="document not found")

    # A visible document whose text may not be shown answers with an empty
    # list; the caller reads the reason from GET /v1/documents/{id}/rights.
    segments = PostgresSegmentRepository(session).list_citable_segments_for_jurisdiction(
        document_id, jurisdiction
    )
    return [
        SegmentResponse(
            id=s.id, sequence_number=s.sequence_number, heading=s.heading, text=s.text,
        )
        for s in segments
    ]
