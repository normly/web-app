# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import EdgeType
from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEdgeRepository,
)

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import ValidityResponse

validity_router = APIRouter(prefix="/v1/documents", tags=["validity"])


@validity_router.get(
    "/{document_id}/validity",
    response_model=ValidityResponse,
    responses=NOT_FOUND_RESPONSE,
)
def get_validity(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> ValidityResponse:
    # This endpoint makes a statement ABOUT one specific document, so it needs
    # the same gate as GET /v1/documents/{id}: an unclassified document must
    # 404, not receive a confident (and unfounded) "valid". A single 404 covers
    # both "no such document" and "exists but not classified for this
    # jurisdiction" -- non-disclosure, same as the detail endpoint.
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_for_jurisdiction(document_id, jurisdiction) is None:
        raise HTTPException(status_code=404, detail="document not found")

    # REPLACES/WITHDRAWN_BY edges point FROM the successor/withdrawal-notice
    # document TO this one, so the incoming-edges query (to_document_id ==
    # document_id) is what surfaces them -- the outgoing listings only return
    # edges where from_document_id == document_id.
    #
    # The free-layer variant, not list_incoming_edges_for_jurisdiction: this
    # endpoint is anonymous and public, so a COMMERCIAL-layer edge must
    # neither be returned nor influence the reported status.
    edge_repo = PostgresEdgeRepository(session)
    incoming = edge_repo.list_free_layer_incoming_edges_for_jurisdiction(
        document_id, jurisdiction
    )

    # Known limitation, deliberate and documented rather than overlooked:
    # "valid" here means "no successor VISIBLE TO THIS CALLER", not "no
    # successor exists". A REPLACES edge whose source document is not
    # classified in this jurisdiction, or whose layer is COMMERCIAL, is
    # correctly hidden by the gates above -- and the caller then reads
    # "valid" for a document that has, in fact, been replaced. Distinguishing
    # "genuinely no successor" from "a successor exists but you may not see
    # it" would need an existence-only check on incoming edges (the
    # get_document_unchecked pattern, one level up), plus a decision on what
    # a third status value would disclose about gated content. That is its
    # own design question and is not settled here.
    replaced_by = [e.from_document_id for e in incoming if e.edge_type == EdgeType.REPLACES]
    withdrawn_by = [e for e in incoming if e.edge_type == EdgeType.WITHDRAWN_BY]

    if replaced_by:
        status = "replaced"
    elif withdrawn_by:
        status = "withdrawn"
    else:
        status = "valid"

    return ValidityResponse(
        document_id=document_id, status=status, replaced_by=replaced_by,
        withdrawn_reference=(
            str(withdrawn_by[0].from_document_id) if withdrawn_by else None
        ),
    )
