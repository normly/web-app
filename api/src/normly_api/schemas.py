# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DesignationResponse(BaseModel):
    issuer: str
    designation: str
    language: str
    is_primary: bool


class TitleResponse(BaseModel):
    language: str
    title: str


class SourceResponse(BaseModel):
    publisher: str
    retrieval_path: str
    legal_basis_category: str
    jurisdiction: str


class DocumentResponse(BaseModel):
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    designations: list[DesignationResponse]
    titles: list[TitleResponse]
    source: SourceResponse


class EdgeResponse(BaseModel):
    edge_type: str
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    jurisdiction: str | None
    layer: str


class ValidityResponse(BaseModel):
    document_id: uuid.UUID
    status: Literal["valid", "replaced", "withdrawn"]
    replaced_by: list[uuid.UUID]
    withdrawn_reference: str | None


class LicenseNotice(BaseModel):
    license_name: str
    license_url: str
    attribution: str


class ExportResponse(BaseModel):
    license: LicenseNotice
    schema_version: str
    jurisdiction: str
    generated_at: datetime
    documents: list[DocumentResponse]
    edges: list[EdgeResponse]


class ErrorResponse(BaseModel):
    detail: str
