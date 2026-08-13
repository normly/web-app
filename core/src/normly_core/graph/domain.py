# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Protocol


class LegalBasisCategory(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class TdmOptOutResult(str, Enum):
    NONE_FOUND = "none_found"
    OPT_OUT_PRESENT = "opt_out_present"


class EdgeType(str, Enum):
    REFERENCES = "references"
    REPLACES = "replaces"
    WITHDRAWN_BY = "withdrawn_by"
    BASED_ON_LAW = "based_on_law"
    ADOPTED_FROM = "adopted_from"


class Layer(str, Enum):
    FREE = "free"
    COMMERCIAL = "commercial"


@dataclass(frozen=True)
class Source:
    id: uuid.UUID
    publisher: str
    retrieval_path: str
    legal_basis_category: LegalBasisCategory
    jurisdiction: str
    reviewed_at: date
    responsible_person: str
    commercial_catalog: bool
    contract_reference: str | None
    tdm_opt_out_checked_at: date | None
    tdm_opt_out_result: TdmOptOutResult | None


@dataclass(frozen=True)
class Delivery:
    id: uuid.UUID
    source_id: uuid.UUID
    content_hash: str
    ingested_at: datetime
    withdrawn_at: datetime | None


@dataclass(frozen=True)
class Document:
    id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    part: str | None
    created_via_delivery_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True)
class DocumentDesignation:
    id: uuid.UUID
    document_id: uuid.UUID
    issuer: str
    designation: str
    language: str
    edition: str | None
    is_primary: bool
    delivery_id: uuid.UUID


@dataclass(frozen=True)
class DocumentTitle:
    id: uuid.UUID
    document_id: uuid.UUID
    language: str
    title: str
    delivery_id: uuid.UUID


@dataclass(frozen=True)
class Edge:
    id: uuid.UUID
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    edge_type: EdgeType
    jurisdiction: str | None
    layer: Layer
    delivery_id: uuid.UUID
    revoked_at: datetime | None


@dataclass(frozen=True)
class RightsClassification:
    document_id: uuid.UUID
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str
    classified_at: datetime
    classified_by: str
    delivery_id: uuid.UUID
    revoked_at: datetime | None


class SourceRepository(Protocol):
    def create_source(
        self,
        *,
        publisher: str,
        retrieval_path: str,
        legal_basis_category: LegalBasisCategory,
        jurisdiction: str,
        reviewed_at: date,
        responsible_person: str,
        commercial_catalog: bool = False,
        contract_reference: str | None = None,
        tdm_opt_out_checked_at: date | None = None,
        tdm_opt_out_result: TdmOptOutResult | None = None,
    ) -> Source: ...

    def get_source(self, source_id: uuid.UUID) -> Source | None: ...


class DeliveryRepository(Protocol):
    def record_delivery(
        self, *, source_id: uuid.UUID, content_hash: str, ingested_at: datetime
    ) -> Delivery: ...

    def get_delivery(self, delivery_id: uuid.UUID) -> Delivery | None: ...

    def revoke_delivery(self, delivery_id: uuid.UUID) -> None: ...


class DocumentRepository(Protocol):
    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
    ) -> Document: ...

    def get_document_unchecked(self, document_id: uuid.UUID) -> Document | None: ...

    def add_designation(
        self,
        *,
        document_id: uuid.UUID,
        issuer: str,
        designation: str,
        language: str,
        edition: str | None,
        is_primary: bool,
        delivery_id: uuid.UUID,
    ) -> DocumentDesignation: ...

    def add_title(
        self, *, document_id: uuid.UUID, language: str, title: str, delivery_id: uuid.UUID
    ) -> DocumentTitle: ...

    def list_designations(self, document_id: uuid.UUID) -> list[DocumentDesignation]: ...

    def list_titles(self, document_id: uuid.UUID) -> list[DocumentTitle]: ...

    def get_document_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> Document | None: ...

    def list_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]: ...


class RightsRepository(Protocol):
    def classify(
        self,
        *,
        document_id: uuid.UUID,
        jurisdiction: str,
        may_process: bool,
        may_index_fulltext: bool,
        may_cite_passages: bool,
        may_export_free: bool,
        legal_basis_reference: str,
        classified_at: datetime,
        classified_by: str,
        delivery_id: uuid.UUID,
    ) -> RightsClassification: ...

    def get_classification(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> RightsClassification | None: ...


class EdgeRepository(Protocol):
    def create_edge(
        self,
        *,
        from_document_id: uuid.UUID,
        to_document_id: uuid.UUID,
        edge_type: EdgeType,
        jurisdiction: str | None,
        layer: Layer,
        delivery_id: uuid.UUID,
    ) -> Edge: ...

    def list_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]: ...
