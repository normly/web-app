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
from normly_api.schemas import EdgeResponse

edges_router = APIRouter(prefix="/v1/documents", tags=["edges"])


@edges_router.get(
    "/{document_id}/edges",
    response_model=list[EdgeResponse],
    responses=NOT_FOUND_RESPONSE,
)
def list_edges(
    # EdgeType, not str: an unknown value is a client mistake and now yields a
    # 400 through the validation handler, instead of silently returning an
    # empty list that reads like "this document has no such edges". EdgeType
    # is a str-Enum, so the comparison against e.edge_type.value still holds.
    document_id: uuid.UUID, jurisdiction: str, edge_type: EdgeType | None = None,
    session: Session = Depends(get_session),
) -> list[EdgeResponse]:
    # list_edges_for_jurisdiction alone cannot distinguish "no such document" from
    # "document exists, no edges visible in this jurisdiction" -- both produce an
    # empty result from that join. get_document_unchecked is the one sanctioned use
    # of an otherwise-internal method: an existence check that reveals nothing about
    # rights-gated content, only whether the id refers to a real document at all.
    doc_repo = PostgresDocumentRepository(session)
    if doc_repo.get_document_unchecked(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")

    # list_free_layer_edges_for_jurisdiction, not list_edges_for_jurisdiction:
    # this endpoint is anonymous and public, so COMMERCIAL-layer edges (the
    # paid tier's section-level references, REQ-GRAPH-002) must not appear.
    # Not the export gate either -- may_export_free asks a different question.
    edges = PostgresEdgeRepository(session).list_free_layer_edges_for_jurisdiction(
        document_id, jurisdiction
    )
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type.value == edge_type]

    return [
        EdgeResponse(
            edge_type=e.edge_type.value, from_document_id=e.from_document_id,
            to_document_id=e.to_document_id, jurisdiction=e.jurisdiction,
            layer=e.layer.value,
        )
        for e in edges
    ]
