# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEdgeRepository,
)

from normly_api.dependencies import get_session
from normly_api.routers.documents import _document_to_response
from normly_api.schemas import EdgeResponse, ExportResponse, LicenseNotice

export_router = APIRouter(prefix="/v1", tags=["export"])

_SCHEMA_VERSION = "1.0"


@export_router.get("/export", response_model=ExportResponse)
def export_free_graph(
    jurisdiction: str, format: str = "json",
    session: Session = Depends(get_session),
) -> ExportResponse:
    if format != "json":
        raise HTTPException(
            status_code=400, detail=f"unsupported export format: {format!r}"
        )

    doc_repo = PostgresDocumentRepository(session)
    edge_repo = PostgresEdgeRepository(session)

    documents = doc_repo.list_exportable_documents_for_jurisdiction(jurisdiction)
    document_responses = [_document_to_response(d, session) for d in documents]

    seen_edge_ids: set = set()
    edge_responses: list[EdgeResponse] = []
    for document in documents:
        for edge in edge_repo.list_exportable_edges_for_jurisdiction(document.id, jurisdiction):
            if edge.id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge.id)
            edge_responses.append(
                EdgeResponse(
                    edge_type=edge.edge_type.value, from_document_id=edge.from_document_id,
                    to_document_id=edge.to_document_id, jurisdiction=edge.jurisdiction,
                    layer=edge.layer.value,
                )
            )

    return ExportResponse(
        license=LicenseNotice(
            license_name="ODbL-1.0",
            license_url="https://opendatacommons.org/licenses/odbl/1-0/",
            attribution="normly contributors",
        ),
        schema_version=_SCHEMA_VERSION,
        jurisdiction=jurisdiction,
        generated_at=datetime.now(timezone.utc),
        documents=document_responses,
        edges=edge_responses,
    )
