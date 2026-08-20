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


class WithdrawnDeliveryError(Exception):
    """
    Raised when an artifact would be created or updated on a delivery that is
    withdrawn or unknown.

    Without this guard a repeat ingestion run — which the idempotency rule
    requires to be safe — would re-create artifacts a publisher's withdrawal
    had just locked, and `classify()` would clear `revoked_at` outright. The
    withdrawal commitment depends on this staying closed.
    """

    def __init__(self, delivery_id: uuid.UUID):
        self.delivery_id = delivery_id
        super().__init__(f"delivery {delivery_id} is withdrawn or does not exist")


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

    def find_by_publisher(self, publisher: str) -> Source | None: ...


class DeliveryRepository(Protocol):
    def record_delivery(
        self, *, source_id: uuid.UUID, content_hash: str, ingested_at: datetime
    ) -> Delivery: ...

    def get_delivery(self, delivery_id: uuid.UUID) -> Delivery | None: ...

    def find_delivery(self, source_id: uuid.UUID, content_hash: str) -> Delivery | None: ...

    def revoke_delivery(self, delivery_id: uuid.UUID) -> None: ...


class DocumentRepository(Protocol):
    """
    The rights-gated read and write surface for document nodes.

    Every read declared here takes a jurisdiction and filters through
    `rights_classification`; there is deliberately no method that returns
    documents unfiltered.

    `PostgresDocumentRepository` additionally carries three ungated methods
    that are **not** part of this Protocol and must not be treated as
    content-serving API: `get_document_unchecked` (existence check for
    pipeline and administrative use, e.g. proving a document node survived a
    delivery revocation), `list_designations` and `list_titles` (identity
    resolution and pipeline metadata — designations are the identity of a node
    across national adoptions, independent of any rights question). They are
    internal implementation methods.

    Exception: `get_document_unchecked` may be invoked by a public-facing read
    path only as a pure existence check—to decide 404 vs. content, e.g.
    distinguishing "no such document" from "document exists but has no visible
    content in this jurisdiction"—provided its result is never exposed in a
    response body or used to reveal anything about rights-gated content.

    Any public-facing read path — the API sub-project above all — MUST use
    `get_document_for_jurisdiction` / `list_documents_for_jurisdiction`.
    """

    def create_document(
        self,
        *,
        origin_issuer: str,
        origin_number: str,
        edition: str,
        part: str | None,
        delivery_id: uuid.UUID,
    ) -> Document: ...

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

    def get_document_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> Document | None: ...

    def list_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]: ...

    def list_exportable_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]:
        """
        Stricter than `list_documents_for_jurisdiction`: additionally requires
        `may_export_free=True`. A document may be processable/servable in a
        jurisdiction (`may_process=True`) without being licensed for
        redistribution in the public free-tier export — e.g. content received
        under a contract that permits internal processing but not
        republication. This is the correct method for any public/free-tier
        export or dump; never for internal/authenticated content-serving
        reads, which should keep using `get_document_for_jurisdiction` /
        `list_documents_for_jurisdiction`.
        """
        ...

    def find_by_designation(self, issuer: str, designation: str) -> Document | None: ...


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
    ) -> list[Edge]:
        """
        Outgoing edges (document_id == from_document_id), rights-gated on BOTH
        endpoints (may_process, unrevoked, matching jurisdiction) and nothing
        else. In particular this applies NO layer filter: COMMERCIAL-layer
        edges are returned.

        Callers in this repository: pipeline and processing code only. No HTTP
        endpoint may call this -- a public, anonymous caller would receive
        commercial-tier relationships. Public read paths use
        `list_free_layer_edges_for_jurisdiction`; the bulk export uses
        `list_exportable_edges_for_jurisdiction`.
        """
        ...

    def list_incoming_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        """
        Incoming edges (document_id == to_document_id) -- e.g. the
        REPLACES/WITHDRAWN_BY edges a successor or withdrawal-notice document
        points at document_id. Same dual rights-gating as
        `list_edges_for_jurisdiction`, direction reversed, and likewise NO
        layer filter: COMMERCIAL-layer edges are returned.

        Callers in this repository: pipeline and processing code only. No HTTP
        endpoint may call this; the public validity endpoint uses
        `list_free_layer_incoming_edges_for_jurisdiction`.
        """
        ...

    def list_free_layer_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        """
        `list_edges_for_jurisdiction` plus `layer == Layer.FREE`. Nothing else
        differs: same outgoing direction, same dual may_process gating, same
        ordering.

        This is the method for public, anonymous read paths that must not
        disclose commercial-tier relationships (REQ-GRAPH-002 reserves
        section-level references within licensed norms for the paid tier). It
        is deliberately NOT the bulk-export case: it does not require
        `may_export_free`, because "may this specific relationship be shown to
        a free-tier caller" is a narrower question than "is this document
        flagged for inclusion in the bulk dump". A document that is
        may_process=True but may_export_free=False still answers questions
        about itself over the API; it just does not appear in `/v1/export`.

        Caller in this repository: GET /v1/documents/{id}/edges.
        """
        ...

    def list_free_layer_incoming_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        """
        `list_incoming_edges_for_jurisdiction` plus `layer == Layer.FREE`.
        Incoming direction (document_id == to_document_id), otherwise the same
        relationship to its sibling as
        `list_free_layer_edges_for_jurisdiction` has to
        `list_edges_for_jurisdiction` -- see there for why this is distinct
        from the `may_export_free`-gated export methods.

        Caller in this repository: GET /v1/documents/{id}/validity.
        """
        ...

    def list_exportable_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        """
        `list_edges_for_jurisdiction` plus `layer == Layer.FREE` plus
        `may_export_free` on BOTH endpoints. The strictest of the four
        listings, and the only one that consults `may_export_free`.

        This is the bulk free-tier dump gate, not general public visibility:
        an endpoint answering about one document should use
        `list_free_layer_edges_for_jurisdiction` instead, which does not
        require the export flag.

        Caller in this repository: GET /v1/export.
        """
        ...


@dataclass(frozen=True)
class Segment:
    id: uuid.UUID
    document_id: uuid.UUID
    delivery_id: uuid.UUID
    sequence_number: int
    heading: str | None
    text: str
    language: str
    created_at: datetime


class SegmentRepository(Protocol):
    def add_segment(
        self,
        *,
        document_id: uuid.UUID,
        delivery_id: uuid.UUID,
        sequence_number: int,
        heading: str | None,
        text: str,
        language: str,
    ) -> tuple[Segment, bool]:
        """
        Store one segment; return it together with whether this call created it.

        The flag is what keeps a run summary honest: on the idempotent path the
        segment comes back unchanged and nothing was created.
        """
        ...

    def list_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]: ...


@dataclass(frozen=True)
class Embedding:
    id: uuid.UUID
    segment_id: uuid.UUID
    delivery_id: uuid.UUID
    model_name: str
    vector: list[float]
    created_at: datetime


class EmbeddingRepository(Protocol):
    """
    The write surface for segment embeddings.

    `PostgresEmbeddingRepository` additionally carries `get_embedding_unchecked`,
    which is **not** part of this Protocol: it takes no jurisdiction and joins no
    rights classification, so it is a pipeline and administrative method, never a
    content-serving read — the same split `DocumentRepository` documents for
    `get_document_unchecked`.
    """

    def add_embedding(
        self,
        *,
        segment_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> tuple[Embedding, bool]:
        """Store one embedding; return it and whether this call created it."""
        ...


class IdentityResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IdentityResolutionCase:
    id: uuid.UUID
    delivery_id: uuid.UUID
    raw_designation: str
    raw_issuer: str | None
    reason: str
    status: IdentityResolutionStatus
    resolved_document_id: uuid.UUID | None
    resolved_at: datetime | None
    resolved_by: str | None
    created_at: datetime


class IdentityResolutionRepository(Protocol):
    def enqueue_case(
        self,
        *,
        delivery_id: uuid.UUID,
        raw_designation: str,
        raw_issuer: str | None,
        reason: str,
    ) -> IdentityResolutionCase: ...

    def list_pending_cases(self) -> list[IdentityResolutionCase]: ...

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase: ...

    def reject_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase: ...
