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
from normly_api.schemas import ValidityResponse

validity_router = APIRouter(prefix="/v1/documents", tags=["validity"])


@validity_router.get("/{document_id}/validity", response_model=ValidityResponse)
def get_validity(
    document_id: uuid.UUID, jurisdiction: str,
    session: Session = Depends(get_session),
) -> ValidityResponse:
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_unchecked(document_id) is None:
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
