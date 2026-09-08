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


class AccountTokenPurpose(str, Enum):
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    MAGIC_LINK = "magic_link"
    EMAIL_CHANGE = "email_change"


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
    work_id: uuid.UUID
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


@dataclass(frozen=True)
class WorkStructureEntry:
    document_id: uuid.UUID
    origin_issuer: str
    origin_number: str
    edition: str
    designation: str | None
    status: str


@dataclass(frozen=True)
class WorkStructure:
    work_id: uuid.UUID
    editions: list[WorkStructureEntry]
    national_adoptions: list[WorkStructureEntry]


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
        work_id: uuid.UUID | None = None,
    ) -> Document:
        """
        `work_id` is the pipeline's explicit assignment when an ingestion
        signal (REPLACES/WITHDRAWN_BY/ADOPTED_FROM to a known document)
        resolved one -- see `normly_core.pipeline.work_assignment`. Omitted,
        the repository creates a fresh 1:1 Work for this document, which is
        the correct default whenever nothing links it to an existing one.
        """
        ...

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

    def search_documents_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Document], int]:
        """
        Free-text (designation/title, case-insensitive substring) and/or
        issuer-filtered listing, paginated. Returns (page, total_matching) --
        `total` reflects the full filtered set, not just this page's length.
        An empty q and issuer returns the whole jurisdiction, paginated --
        this is also how "browse by issuer" and "browse everything" work,
        without a separate method.
        """
        ...

    def search_works_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        query_vector: list[float] | None = None, embedding_model_name: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[WorkSearchHit], int]:
        """
        Hybrid, Work-grouped search: exact ILIKE matches on designation/title
        (Tier 1, via search_documents_for_jurisdiction) rank first, then
        documents ranked by cosine distance to `query_vector` (Tier 2) fill
        the rest. Both tiers are deduplicated by work_id -- exactly one hit
        per Work, led by its best-ranked Document. `total` counts distinct
        Works matched, not raw document rows.

        `query_vector` must already be computed (via
        `EmbeddingModel.embed_query`) by the caller -- this repository never
        calls the embedding model itself. `embedding_model_name` is required
        whenever `query_vector` is given (mixing vectors from different
        models in one ORDER BY compares distances from unrelated vector
        spaces); if either is omitted, Tier 2 is skipped and this behaves as
        Tier-1-only, Work-grouped search.
        """
        ...

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

    def find_by_designation(
        self, issuer: str, designation: str, edition: str | None = None
    ) -> Document | None: ...

    def find_previous_edition(
        self, issuer: str, designation: str, before_edition: str
    ) -> Document | None:
        """
        The edition immediately preceding `before_edition` for this
        (issuer, designation) -- the greatest `edition` value strictly less
        than `before_edition` among that designation's other documents, or
        None if none exists (including when `before_edition` is itself the
        oldest known edition).

        Unlike `find_by_designation`'s edition-less fallback (which answers
        "most recently INSERTED"), this answers "the true predecessor in
        edition order" -- out-of-order ingestion (an older archive edition
        arriving after its newer successor is already known) or same-
        transaction batches (where created_at ties are common) must not
        produce an inverted or nondeterministic REPLACES edge.
        """
        ...


class RateLimitRepository(Protocol):
    """
    A generic, jurisdiction-independent request counter used to enforce
    REQ-ACC-003's anonymous quota. Not part of the graph model, but kept in
    the same repository layer as everything else that touches the database,
    per CLAUDE.md's "Datenbankzugriff nur über die Repository-Schicht".
    """

    def record_and_check(
        self, *, key: str, window_start: datetime, limit: int
    ) -> bool:
        """
        Atomically increments the request counter for `key` within the
        window starting at `window_start`, and reports whether the caller
        is still within `limit`. Returns True when the request should be
        allowed (count <= limit after incrementing), False when it should
        be rejected.
        """
        ...


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

    def get_work_structure_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> WorkStructure | None:
        """
        None if `document_id` is not visible in `jurisdiction` (same gate as
        get_document_for_jurisdiction). Otherwise: every Document sharing this
        document's work_id and visible in this jurisdiction, split into two
        lists by edge type among a BOUNDED set (this Work's documents and the
        edges between them only -- not an unbounded graph traversal, matches
        ADR-006's "graph queries stay shallow"):

        `editions` -- every Work member connected to `document_id` via a path
        of ONLY REPLACES/WITHDRAWN_BY edges (same-lineage chain, typically one
        issuer), including `document_id` itself -- UNLESS `document_id` is
        the only visible Work member, in which case both lists are empty
        (nothing to list itself against).

        `national_adoptions` -- every OTHER Work member (not in the editions
        chain). Together the two lists cover every visible Work member
        exactly once (or are both empty in the single-member case above).

        Each entry's `status` is computed the same way GET .../validity
        computes it for a single document: an entry with an incoming
        REPLACES edge (within this bounded edge set) is "replaced", an
        incoming WITHDRAWN_BY edge is "withdrawn", otherwise "valid".
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

    def find_similar_segments_for_jurisdiction(
        self, query_vector: list[float], jurisdiction: str, model_name: str, limit: int = 5,
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


@dataclass(frozen=True)
class DocumentEmbedding:
    id: uuid.UUID
    document_id: uuid.UUID
    model_name: str
    vector: list[float]
    delivery_id: uuid.UUID
    created_at: datetime


class DocumentEmbeddingRepository(Protocol):
    """
    The write surface for per-Document search embeddings.

    Unlike `EmbeddingRepository.add_embedding` (segment-scoped, create-if-
    absent -- segment text never changes, so no update is ever needed),
    `upsert_document_embedding` always (re)writes the vector: a Document's
    primary designation/title can change across re-ingestion, so the
    embedding must track it rather than freeze on the first value ever seen.
    """

    def upsert_document_embedding(
        self,
        *,
        document_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> DocumentEmbedding: ...

    def list_documents_without_embedding(self, model_name: str) -> list[Document]:
        """
        Every Document with no DocumentEmbedding row for `model_name` yet.
        Pipeline/administrative method (used by the `backfill-document-
        embeddings` CLI command) -- nothing here is served to a public
        caller, it only decides what the backfill still has to do.
        """
        ...


@dataclass(frozen=True)
class WorkSearchHit:
    work_id: uuid.UUID
    best_match: Document
    other_editions_count: int


class WorkStatus(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"


class WorkCreatedVia(str, Enum):
    AUTO_MATCHED = "auto_matched"
    MANUAL = "manual"


@dataclass(frozen=True)
class Work:
    id: uuid.UUID
    status: WorkStatus
    merged_into_work_id: uuid.UUID | None
    created_via: WorkCreatedVia
    created_at: datetime


class WorkRepository(Protocol):
    def create_work(self, *, created_via: WorkCreatedVia) -> Work: ...

    def get_work(self, work_id: uuid.UUID) -> Work | None:
        """
        Look up a Work by id. If it has been merged into another Work
        (`status == MERGED`), returns the target Work it was merged into
        instead -- callers never see a retired Work as if it were current.
        """
        ...


class ContradictoryWorkMergeError(Exception):
    def __init__(self, source_work_id: uuid.UUID, target_work_id: uuid.UUID):
        self.source_work_id = source_work_id
        self.target_work_id = target_work_id
        super().__init__(
            f"cannot merge work {source_work_id} into {target_work_id}: "
            "same work, or target is not active"
        )


class IdentityResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class IdentityResolutionCaseType(str, Enum):
    NEW_DOCUMENT = "new_document"
    WORK_MERGE = "work_merge"


@dataclass(frozen=True)
class IdentityResolutionCase:
    id: uuid.UUID
    delivery_id: uuid.UUID
    case_type: IdentityResolutionCaseType
    raw_designation: str | None
    raw_issuer: str | None
    reason: str
    status: IdentityResolutionStatus
    resolved_document_id: uuid.UUID | None
    source_work_id: uuid.UUID | None
    target_work_id: uuid.UUID | None
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

    def enqueue_work_merge_case(
        self,
        *,
        delivery_id: uuid.UUID,
        source_work_id: uuid.UUID,
        target_work_id: uuid.UUID,
        reason: str,
    ) -> IdentityResolutionCase: ...

    def list_pending_cases(self) -> list[IdentityResolutionCase]: ...

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase: ...

    def resolve_work_merge_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase:
        """
        Reassign every Document.work_id from the case's source_work_id to its
        target_work_id, mark the source Work MERGED, and mark the case
        RESOLVED. Raises ContradictoryWorkMergeError -- writing nothing -- if
        source_work_id == target_work_id or the target Work is not ACTIVE
        (already merged elsewhere).
        """
        ...

    def reject_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase: ...


class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatAnswerType(str, Enum):
    STRUCTURAL = "structural"
    SYNTHESIS = "synthesis"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ChatSession:
    id: uuid.UUID
    session_token: str
    account_id: uuid.UUID | None
    jurisdiction: str
    language: str
    created_at: datetime


@dataclass(frozen=True)
class ChatMessage:
    id: uuid.UUID
    session_id: uuid.UUID
    role: ChatMessageRole
    content: str
    answer_type: ChatAnswerType | None
    created_at: datetime


@dataclass(frozen=True)
class ChatMessageCitation:
    id: uuid.UUID
    message_id: uuid.UUID
    document_id: uuid.UUID
    segment_id: uuid.UUID | None


class ChatRepository(Protocol):
    """
    Chat session identity and message history.

    A session is anonymous (`account_id is None`) until a valid account
    session token links it (see the `chat/` package's session-resolution
    logic) — linking never happens in this layer, it is a plain field
    update the caller drives after verifying the token elsewhere (`chat/`
    talks to `accounts/` over HTTP; this repository has no opinion on
    accounts beyond storing the id).
    """

    def create_session(
        self, *, session_token: str, jurisdiction: str, language: str,
        created_at: datetime, account_id: uuid.UUID | None = None,
    ) -> ChatSession: ...

    def get_session_by_token(self, session_token: str) -> ChatSession | None: ...

    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[ChatSession]: ...

    def link_account(self, session_id: uuid.UUID, account_id: uuid.UUID) -> None: ...

    def create_message(
        self, *, session_id: uuid.UUID, role: ChatMessageRole, content: str,
        answer_type: ChatAnswerType | None, created_at: datetime,
    ) -> ChatMessage: ...

    def list_messages_for_session(self, session_id: uuid.UUID) -> list[ChatMessage]: ...

    def add_citation(
        self, *, message_id: uuid.UUID, document_id: uuid.UUID,
        segment_id: uuid.UUID | None,
    ) -> ChatMessageCitation: ...


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    email: str
    password_hash: str | None
    email_verified_at: datetime | None
    created_at: datetime
    first_name: str | None
    last_name: str | None
    avatar_image: bytes | None
    avatar_content_type: str | None


@dataclass(frozen=True)
class AccountSession:
    id: uuid.UUID
    account_id: uuid.UUID
    session_token: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class AccountGoogleIdentity:
    account_id: uuid.UUID
    google_subject_id: str


@dataclass(frozen=True)
class AccountToken:
    id: uuid.UUID
    account_id: uuid.UUID | None
    purpose: AccountTokenPurpose
    token: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    email: str | None


class AccountRepository(Protocol):
    """
    Account identity — email/password accounts. Google-only accounts have
    `password_hash=None`.

    `create_account` is deliberately NOT idempotent on a duplicate email like
    `record_delivery`/`add_designation` elsewhere in this file — two different
    registrants submitting the same email must never silently share an
    account. It raises `EmailAlreadyRegisteredError` instead.
    """

    def create_account(self, *, email: str, password_hash: str | None) -> Account: ...

    def get_account_by_id(self, account_id: uuid.UUID) -> Account | None: ...

    def get_account_by_email(self, email: str) -> Account | None: ...

    def mark_email_verified(self, account_id: uuid.UUID, verified_at: datetime) -> None: ...

    def set_password_hash(self, account_id: uuid.UUID, password_hash: str) -> None: ...

    def update_email(self, account_id: uuid.UUID, new_email: str) -> None: ...

    def update_profile_names(
        self, account_id: uuid.UUID, *, first_name: str | None, last_name: str | None
    ) -> None: ...

    def set_avatar(
        self, account_id: uuid.UUID, *, avatar_image: bytes, avatar_content_type: str
    ) -> None: ...

    def clear_avatar(self, account_id: uuid.UUID) -> None: ...

    def delete_account(self, account_id: uuid.UUID) -> None: ...


class EmailAlreadyRegisteredError(Exception):
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"an account already exists for {email!r}")


class AccountGoogleIdentityRepository(Protocol):
    """
    An account carries at most one Google identity: `account_id` is the
    primary key of `account_google_identity`, and `google_subject_id` is
    unique across it.

    `link_google_identity` is idempotent for a link that already exists
    exactly as requested, following the same convention as `record_delivery`
    and `add_designation`. Any other collision — a second Google subject for
    an already-linked account, or a subject already linked to a different
    account — raises `GoogleIdentityAlreadyLinkedError` rather than an
    `IntegrityError` that would leave the session unusable.
    """

    def link_google_identity(
        self, *, account_id: uuid.UUID, google_subject_id: str
    ) -> AccountGoogleIdentity: ...

    def get_account_by_google_subject(self, google_subject_id: str) -> Account | None: ...

    def has_google_identity(self, account_id: uuid.UUID) -> bool: ...


class GoogleIdentityAlreadyLinkedError(Exception):
    def __init__(self, account_id: uuid.UUID, google_subject_id: str):
        self.account_id = account_id
        self.google_subject_id = google_subject_id
        super().__init__(
            f"cannot link Google subject {google_subject_id!r} to account "
            f"{account_id}: a conflicting link already exists"
        )


class AccountSessionRepository(Protocol):
    def create_session(
        self, *, account_id: uuid.UUID, session_token: str, created_at: datetime,
        expires_at: datetime,
    ) -> AccountSession: ...

    def get_session_by_token(self, session_token: str) -> AccountSession | None: ...

    def extend_session(self, session_id: uuid.UUID, new_expires_at: datetime) -> None: ...

    def revoke_session(self, session_token: str) -> None: ...

    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[AccountSession]: ...

    def revoke_session_by_id(self, session_id: uuid.UUID, account_id: uuid.UUID) -> bool: ...


class AccountTokenRepository(Protocol):
    """
    One-time tokens for password reset, email verification, and magic-link
    login, distinguished by `purpose`.

    `consume_token` MUST be a single atomic UPDATE ... WHERE used_at IS NULL
    AND expires_at > now ... RETURNING statement, not a SELECT followed by a
    separate UPDATE — two concurrent requests with the same token must not
    both succeed.

    A token names either an existing account or a bare email address that has
    no account yet: magic-link is a registration path too, and the account for
    an unknown address is created when the link is confirmed, not when it is
    requested — otherwise anyone could conjure an account for any address they
    can type without proving they can read that mailbox. `create_token`
    therefore takes exactly one of `account_id` and `email`; passing both or
    neither is a programming error and raises `ValueError`.
    """

    def create_token(
        self, *, account_id: uuid.UUID | None = None, email: str | None = None,
        purpose: AccountTokenPurpose, token: str, created_at: datetime,
        expires_at: datetime,
    ) -> AccountToken: ...

    def consume_token(
        self, token: str, purpose: AccountTokenPurpose
    ) -> AccountToken | None: ...
