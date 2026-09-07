# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import WorkStructureEntry
from normly_core.graph.postgres.repositories import PostgresEdgeRepository

from normly_api.dependencies import get_session
from normly_api.errors import NOT_FOUND_RESPONSE
from normly_api.schemas import WorkStructureEntryResponse, WorkStructureResponse

work_router = APIRouter(prefix="/v1/documents", tags=["work"])


def _entry_to_response(entry: WorkStructureEntry) -> WorkStructureEntryResponse:
    return WorkStructureEntryResponse(
        document_id=entry.document_id, origin_issuer=entry.origin_issuer,
        origin_number=entry.origin_number, edition=entry.edition,
        designation=entry.designation, status=entry.status,
    )


@work_router.get(
    "/{document_id}/work", response_model=WorkStructureResponse, responses=NOT_FOUND_RESPONSE,
)
def get_work_structure(
    document_id: uuid.UUID, jurisdiction: str, session: Session = Depends(get_session),
) -> WorkStructureResponse:
    structure = PostgresEdgeRepository(session).get_work_structure_for_jurisdiction(
        document_id, jurisdiction
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="document not found")

    return WorkStructureResponse(
        work_id=structure.work_id,
        editions=[_entry_to_response(e) for e in structure.editions],
        national_adoptions=[_entry_to_response(e) for e in structure.national_adoptions],
    )
