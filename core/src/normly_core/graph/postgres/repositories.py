# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from normly_core.graph.domain import (
    Account,
    AccountGoogleIdentity,
    AccountSession,
    AccountToken,
    AccountTokenPurpose,
    ChatAnswerType,
    ChatMessage,
    ChatMessageCitation,
    ChatMessageRole,
    ChatSession,
    ContradictoryWorkMergeError,
    Delivery,
    Document,
    DocumentDesignation,
    DocumentEmbedding,
    DocumentTitle,
    Edge,
    EdgeType,
    Embedding,
    EmailAlreadyRegisteredError,
    GoogleIdentityAlreadyLinkedError,
    IdentityResolutionCase,
    IdentityResolutionCaseType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    Layer,
    Notification,
    NotificationPreference,
    NotificationTriggerType,
    OAuthState,
    RightsClassification,
    RightsNotificationBaseline,
    Segment,
    Source,
    TdmOptOutResult,
    Watchlist,
    WithdrawnDeliveryError,
    Work,
    WorkCreatedVia,
    WorkSearchHit,
    WorkStatus,
    WorkStructure,
    WorkStructureEntry,
)
from normly_core.graph.postgres.orm import (
    AccountGoogleIdentityORM,
    AccountORM,
    AccountSessionORM,
    AccountTokenORM,
    ChatMessageCitationORM,
    ChatMessageORM,
    ChatSessionORM,
    DeliveryORM,
    DocumentORM,
    DocumentDesignationORM,
    DocumentEmbeddingORM,
    DocumentTitleORM,
    EdgeORM,
    EmbeddingORM,
    IdentityResolutionCaseORM,
    NotificationORM,
    OAuthStateORM,
    RateLimitBucketORM,
    RightsClassificationORM,
    RightsNotificationBaselineORM,
    SegmentORM,
    SourceORM,
    WatchlistORM,
    WorkORM,
)


# How many nearest-neighbour candidates Tier 2 (semantic) pulls per search --
# not a page size. search_works_for_jurisdiction groups these (plus Tier 1's
# exact matches) down to one hit per Work before paginating, so this bounds
# the expensive ANN query rather than the number of Works actually returned.
_SEMANTIC_CANDIDATE_POOL = 200

# How many Tier 1 (exact-match) candidates search_works_for_jurisdiction pulls
# before Work-deduplication -- large enough that no realistic TEXT query (q is
# not None) is ever actually truncated. This is NOT true for q=None (the
# "browse everything in the jurisdiction" case, including this endpoint's
# default): as the corpus grows, that request can genuinely exceed this cap,
# silently truncating `total` and deep pagination. Known limitation, not fixed
# here -- a real fix needs a SQL-side GROUP BY work_id rather than Python-side
# grouping over a capped candidate list. Revisit once there's a real corpus
# to size this against.
_TIER1_CANDIDATE_POOL = 10_000

# Edge types that ever imply shared Work membership -- must match the same
# three types the ingestion pipeline's work_assignment.py already treats as
# Work-linking signals. REFERENCES/BASED_ON_LAW never belong here.
_WORK_STRUCTURE_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY, EdgeType.ADOPTED_FROM)
# The subset that forms an edition lineage chain (same-issuer succession),
# as opposed to a national adoption.
_EDITION_CHAIN_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY)


def _escape_like(term: str) -> str:
    """
    Neutralise LIKE metacharacters in a caller-supplied search term.

    Not an injection concern -- the term is bound as a parameter either way --
    but an unescaped "%" matches the whole catalogue in a single request, and
    someone searching for a literal "100%" would otherwise get wildcard
    behaviour they never asked for. The backslash goes first, or it would
    escape the escapes added after it.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _require_active_delivery(session: Session, delivery_id: uuid.UUID) -> None:
    """
    Guard every artifact-creating write path.

    A withdrawn delivery must not gain new artifacts, and re-running an
    ingestion for it must not resurrect what `revoke_delivery` locked —
    `classify()` in particular writes `revoked_at=None` on every call.
    """
    delivery = session.get(DeliveryORM, delivery_id)
    if delivery is None or delivery.withdrawn_at is not None:
        raise WithdrawnDeliveryError(delivery_id)


def _source_to_domain(orm: SourceORM) -> Source:
    return Source(
        id=orm.id,
        publisher=orm.publisher,
        retrieval_path=orm.retrieval_path,
        legal_basis_category=orm.legal_basis_category,
        jurisdiction=orm.jurisdiction,
        reviewed_at=orm.reviewed_at,
        responsible_person=orm.responsible_person,
        commercial_catalog=orm.commercial_catalog,
        contract_reference=orm.contract_reference,
        tdm_opt_out_checked_at=orm.tdm_opt_out_checked_at,
        tdm_opt_out_result=orm.tdm_opt_out_result,
    )


class PostgresSourceRepository:
    def __init__(self, session: Session):
        self._session = session

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
    ) -> Source:
        orm = SourceORM(
            id=uuid.uuid4(),
            publisher=publisher,
            retrieval_path=retrieval_path,
            legal_basis_category=legal_basis_category,
            jurisdiction=jurisdiction,
            reviewed_at=reviewed_at,
            responsible_person=responsible_person,
            commercial_catalog=commercial_catalog,
            contract_reference=contract_reference,
            tdm_opt_out_checked_at=tdm_opt_out_checked_at,
            tdm_opt_out_result=tdm_opt_out_result,
        )
        self._session.add(orm)
        self._session.flush()
        return _source_to_domain(orm)

    def get_source(self, source_id: uuid.UUID) -> Source | None:
        orm = self._session.get(SourceORM, source_id)
        return _source_to_domain(orm) if orm else None

    def find_by_publisher(self, publisher: str) -> Source | None:
        """
        Look a registry entry up by its natural key.

        `publisher` is deliberately not unique in the schema — one publisher may
        legitimately be registered more than once (different retrieval paths,
        different legal bases). This returns the oldest matching row by id so
        repeated pipeline runs resolve to the same registry entry instead of
        picking a different one each time.
        """
        orm = self._session.execute(
            select(SourceORM)
            .where(SourceORM.publisher == publisher)
            .order_by(SourceORM.id)
            .limit(1)
        ).scalar_one_or_none()
        return _source_to_domain(orm) if orm else None


def _delivery_to_domain(orm: DeliveryORM) -> Delivery:
    return Delivery(
        id=orm.id,
        source_id=orm.source_id,
        content_hash=orm.content_hash,
        ingested_at=orm.ingested_at,
        withdrawn_at=orm.withdrawn_at,
    )


class PostgresDeliveryRepository:
    def __init__(self, session: Session):
        self._session = session

    def record_delivery(
        self, *, source_id: uuid.UUID, content_hash: str, ingested_at: datetime
    ) -> Delivery:
        existing = self._session.execute(
            select(DeliveryORM).where(
                DeliveryORM.source_id == source_id,
                DeliveryORM.content_hash == content_hash,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _delivery_to_domain(existing)

        orm = DeliveryORM(
            id=uuid.uuid4(),
            source_id=source_id,
            content_hash=content_hash,
            ingested_at=ingested_at,
            withdrawn_at=None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(DeliveryORM).where(
                    DeliveryORM.source_id == source_id,
                    DeliveryORM.content_hash == content_hash,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _delivery_to_domain(existing)
        return _delivery_to_domain(orm)

    def get_delivery(self, delivery_id: uuid.UUID) -> Delivery | None:
        orm = self._session.get(DeliveryORM, delivery_id)
        return _delivery_to_domain(orm) if orm else None

    def find_delivery(self, source_id: uuid.UUID, content_hash: str) -> Delivery | None:
        orm = self._session.execute(
            select(DeliveryORM).where(
                DeliveryORM.source_id == source_id,
                DeliveryORM.content_hash == content_hash,
            )
        ).scalar_one_or_none()
        return _delivery_to_domain(orm) if orm else None

    def revoke_delivery(self, delivery_id: uuid.UUID) -> None:
        orm = self._session.get(DeliveryORM, delivery_id)
        if orm is None or orm.withdrawn_at is not None:
            return

        now = datetime.now(orm.ingested_at.tzinfo)
        orm.withdrawn_at = now

        self._session.execute(
            sa.update(EdgeORM)
            .where(EdgeORM.delivery_id == delivery_id, EdgeORM.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self._session.execute(
            sa.update(RightsClassificationORM)
            .where(
                RightsClassificationORM.delivery_id == delivery_id,
                RightsClassificationORM.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        self._session.execute(
            sa.delete(DocumentDesignationORM).where(
                DocumentDesignationORM.delivery_id == delivery_id
            )
        )
        self._session.execute(
            sa.delete(DocumentTitleORM).where(DocumentTitleORM.delivery_id == delivery_id)
        )
        # Must run before the EmbeddingORM delete below: embedding.segment_id
        # has ON DELETE CASCADE, so deleting segments here first removes any
        # embedding attached to a deleted segment regardless of which
        # delivery created that embedding. The explicit EmbeddingORM delete
        # then only needs to catch embeddings whose own delivery_id is the
        # revoked one but whose segment belongs to a still-active delivery.
        self._session.execute(
            sa.delete(SegmentORM).where(SegmentORM.delivery_id == delivery_id)
        )
        self._session.execute(
            sa.delete(EmbeddingORM).where(EmbeddingORM.delivery_id == delivery_id)
        )
        self._session.execute(
            sa.delete(DocumentEmbeddingORM).where(
                DocumentEmbeddingORM.delivery_id == delivery_id
            )
        )
        self._session.execute(
            sa.update(IdentityResolutionCaseORM)
            .where(
                IdentityResolutionCaseORM.delivery_id == delivery_id,
                IdentityResolutionCaseORM.status == IdentityResolutionStatus.PENDING,
            )
            .values(
                status=IdentityResolutionStatus.REJECTED,
                resolved_by="system:delivery_revoked",
                resolved_at=now,
            )
        )
        self._session.flush()


def _document_to_domain(orm: DocumentORM) -> Document:
    return Document(
        id=orm.id,
        origin_issuer=orm.origin_issuer,
        origin_number=orm.origin_number,
        edition=orm.edition,
        part=orm.part,
        work_id=orm.work_id,
        created_via_delivery_id=orm.created_via_delivery_id,
        created_at=orm.created_at,
    )


def _designation_to_domain(orm: DocumentDesignationORM) -> DocumentDesignation:
    return DocumentDesignation(
        id=orm.id,
        document_id=orm.document_id,
        issuer=orm.issuer,
        designation=orm.designation,
        language=orm.language,
        edition=orm.edition,
        is_primary=orm.is_primary,
        delivery_id=orm.delivery_id,
    )


def _title_to_domain(orm: DocumentTitleORM) -> DocumentTitle:
    return DocumentTitle(
        id=orm.id,
        document_id=orm.document_id,
        language=orm.language,
        title=orm.title,
        delivery_id=orm.delivery_id,
    )


class PostgresDocumentRepository:
    def __init__(self, session: Session):
        self._session = session

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
        _require_active_delivery(self._session, delivery_id)
        if work_id is None:
            work = WorkORM(id=uuid.uuid4(), status=WorkStatus.ACTIVE, created_via=WorkCreatedVia.AUTO_MATCHED)
            self._session.add(work)
            self._session.flush()
            work_id = work.id
        orm = DocumentORM(
            id=uuid.uuid4(),
            origin_issuer=origin_issuer,
            origin_number=origin_number,
            edition=edition,
            part=part,
            work_id=work_id,
            created_via_delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _document_to_domain(orm)

    def get_document_unchecked(self, document_id: uuid.UUID) -> Document | None:
        orm = self._session.get(DocumentORM, document_id)
        return _document_to_domain(orm) if orm else None

    def list_documents_for_work_unchecked(self, work_id: uuid.UUID) -> list[Document]:
        """
        Every Document belonging to `work_id`, regardless of rights
        classification or jurisdiction. Internal/administrative use only
        (notify-watchers, Task 6) -- never callable from an HTTP endpoint.
        """
        rows = self._session.execute(
            select(DocumentORM).where(DocumentORM.work_id == work_id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]

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
    ) -> DocumentDesignation:
        _require_active_delivery(self._session, delivery_id)
        # The dedupe key includes document_id, even though
        # uq_designation_issuer_designation_edition scopes on (issuer,
        # designation, edition) rather than document_id. That constraint
        # deliberately still collapses to "one node worldwide" for a given
        # (issuer, designation) when edition is NULL on both sides -- e.g.
        # EUR-Lex, BAuA, and DGUV publications with no parseable issue date --
        # but distinct editions of the same designation are meant to coexist
        # as separate documents. Filtering the pre-check on (issuer,
        # designation) alone would silently hand back another document's row
        # (whether a same-edition duplicate or a different edition entirely);
        # with document_id in the key, a genuine collision instead reaches the
        # constraint and surfaces as an IntegrityError — an identity-resolution
        # error, which is what it is.
        existing = self._session.execute(
            select(DocumentDesignationORM).where(
                DocumentDesignationORM.document_id == document_id,
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _designation_to_domain(existing)

        orm = DocumentDesignationORM(
            id=uuid.uuid4(),
            document_id=document_id,
            issuer=issuer,
            designation=designation,
            language=language,
            edition=edition,
            is_primary=is_primary,
            delivery_id=delivery_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(DocumentDesignationORM).where(
                    DocumentDesignationORM.document_id == document_id,
                    DocumentDesignationORM.issuer == issuer,
                    DocumentDesignationORM.designation == designation,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _designation_to_domain(existing)
        return _designation_to_domain(orm)

    def add_title(
        self, *, document_id: uuid.UUID, language: str, title: str, delivery_id: uuid.UUID
    ) -> DocumentTitle:
        _require_active_delivery(self._session, delivery_id)
        existing = self._session.execute(
            select(DocumentTitleORM).where(
                DocumentTitleORM.document_id == document_id,
                DocumentTitleORM.language == language,
                DocumentTitleORM.title == title,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _title_to_domain(existing)

        orm = DocumentTitleORM(
            id=uuid.uuid4(),
            document_id=document_id,
            language=language,
            title=title,
            delivery_id=delivery_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(DocumentTitleORM).where(
                    DocumentTitleORM.document_id == document_id,
                    DocumentTitleORM.language == language,
                    DocumentTitleORM.title == title,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _title_to_domain(existing)
        return _title_to_domain(orm)

    def list_designations(self, document_id: uuid.UUID) -> list[DocumentDesignation]:
        # Ordered by the ingestion time of the delivery each row came from,
        # not by id: id is a random uuid4, so sorting on it is not sorting on
        # anything -- callers (e.g. "the primary designation" tie-breaking, or
        # document_embedding.build_document_embedding_text's "first title")
        # need a stable, meaningful order, and ingested_at is the one
        # deterministic signal every row carries via its delivery.
        rows = self._session.execute(
            select(DocumentDesignationORM)
            .join(DeliveryORM, DeliveryORM.id == DocumentDesignationORM.delivery_id)
            .where(DocumentDesignationORM.document_id == document_id)
            .order_by(DeliveryORM.ingested_at, DocumentDesignationORM.id)
        ).scalars()
        return [_designation_to_domain(row) for row in rows]

    def list_titles(self, document_id: uuid.UUID) -> list[DocumentTitle]:
        rows = self._session.execute(
            select(DocumentTitleORM)
            .join(DeliveryORM, DeliveryORM.id == DocumentTitleORM.delivery_id)
            .where(DocumentTitleORM.document_id == document_id)
            .order_by(DeliveryORM.ingested_at, DocumentTitleORM.id)
        ).scalars()
        return [_title_to_domain(row) for row in rows]

    def get_document_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> Document | None:
        orm = self._session.execute(
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentORM.id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None

    def list_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]:
        rows = self._session.execute(
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(DocumentORM.id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]

    def list_exportable_documents_for_jurisdiction(self, jurisdiction: str) -> list[Document]:
        rows = self._session.execute(
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_export_free.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(DocumentORM.id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]

    def find_by_designation(
        self, issuer: str, designation: str, edition: str | None = None
    ) -> Document | None:
        query = (
            select(DocumentORM)
            .join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
            )
        )
        if edition is not None:
            query = query.where(DocumentDesignationORM.edition == edition)
            orm = self._session.execute(query).scalar_one_or_none()
        else:
            # Without a specific edition, several DocumentDesignation rows can
            # now legitimately share (issuer, designation) -- one per edition
            # (see migration 0026). The caller gets the most recent one
            # deterministically, rather than an ambiguous match; a
            # single-edition designation (the common case today, and the
            # only case for EUR-Lex/BAuA) still returns its one match exactly
            # as before.
            #
            # DocumentORM.id is a secondary sort key purely for reproducible
            # tie-breaking, not semantic "newness" -- Postgres's now() is
            # transaction-scoped, so two documents created in the same
            # transaction (e.g. a bulk backfill) can get a byte-identical
            # created_at. Without a secondary key, ORDER BY created_at DESC
            # alone gives no guarantee which row comes back on a tie, and a
            # different, physically arbitrary row could be returned across
            # runs -- which matters here because downstream callers (e.g.
            # REPLACES-edge creation) build graph edges on this result.
            orm = self._session.execute(
                query.order_by(DocumentORM.created_at.desc(), DocumentORM.id.desc()).limit(1)
            ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None

    def find_previous_edition(
        self, issuer: str, designation: str, before_edition: str
    ) -> Document | None:
        # Unlike find_by_designation's edition-less fallback (which answers
        # "most recently INSERTED"), this answers "the greatest edition
        # value strictly less than before_edition" -- the actual predecessor
        # in edition order, regardless of ingestion order. Out-of-order
        # ingestion (e.g. a 2013 archive arriving after its 2022 successor
        # is already known) or same-transaction batches (where created_at
        # ties are common) must not produce an inverted or nondeterministic
        # REPLACES edge -- see the final-review finding this method fixes.
        #
        # ASSUMPTION this method relies on: `edition` strings are
        # lexicographically sortable in an order that matches their real
        # chronological order (a plain `<` comparison, below). This is true
        # today only because the sole producer of this field, the DGUV
        # adapter's _normalise_issue_date() (core/src/normly_core/pipeline/
        # adapters/dguv.py), always emits ISO-8601 `YYYY-MM-DD` strings,
        # where lexicographic and chronological order coincide. Neither
        # eur_lex.py nor baua.py ever sets `edition`. A future adapter that
        # sets `edition` in a different, non-ISO-8601-sortable format would
        # silently break this method's correctness -- no error would be
        # raised, `find_previous_edition` would simply return the wrong
        # document as "the predecessor." See also the matching note on
        # DocumentDesignation.edition in domain.py.
        orm = self._session.execute(
            select(DocumentORM)
            .join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
                DocumentDesignationORM.edition.is_not(None),
                DocumentDesignationORM.edition < before_edition,
            )
            .order_by(DocumentDesignationORM.edition.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None

    def search_documents_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Document], int]:
        base = (
            select(DocumentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == DocumentORM.id,
            )
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        )

        if q is not None or issuer is not None:
            # A document can have several designations, so this join can
            # multiply rows -- distinct() below dedupes by DocumentORM's
            # full column set (id is the primary key among them), which is
            # equivalent to per-document dedup here.
            base = base.join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            if q is not None:
                pattern = f"%{_escape_like(q)}%"
                base = base.where(
                    sa.or_(
                        DocumentDesignationORM.designation.ilike(pattern, escape="\\"),
                        DocumentORM.id.in_(
                            select(DocumentTitleORM.document_id).where(
                                DocumentTitleORM.title.ilike(pattern, escape="\\")
                            )
                        ),
                    )
                )
            if issuer is not None:
                base = base.where(DocumentDesignationORM.issuer == issuer)
            base = base.distinct()

        total = self._session.execute(
            select(sa.func.count()).select_from(base.subquery())
        ).scalar_one()

        rows = self._session.execute(
            base.order_by(DocumentORM.id).limit(limit).offset(offset)
        ).scalars()
        return [_document_to_domain(row) for row in rows], total

    def search_works_for_jurisdiction(
        self, jurisdiction: str, *, q: str | None = None, issuer: str | None = None,
        query_vector: list[float] | None = None, embedding_model_name: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[WorkSearchHit], int]:
        tier1_documents, _ = self.search_documents_for_jurisdiction(
            jurisdiction, q=q, issuer=issuer, limit=_TIER1_CANDIDATE_POOL, offset=0,
        )
        # search_documents_for_jurisdiction orders by DocumentORM.id (a random
        # uuid4) -- fine for that method's own contract, but meaningless as a
        # tie-break for "which edition of a Work represents it in search
        # results." Re-sort by created_at (newest first) here, locally, so
        # Work-deduplication below picks the most recently created document as
        # best_match, not an arbitrary one. Scoped to this method only --
        # does not change search_documents_for_jurisdiction itself or any of
        # its other callers/tests.
        tier1_documents = sorted(
            tier1_documents, key=lambda document: document.created_at, reverse=True
        )
        ordered_documents = list(tier1_documents)
        seen_document_ids = {document.id for document in ordered_documents}

        if query_vector is not None and embedding_model_name is not None:
            tier2_query = (
                select(DocumentORM)
                .join(
                    RightsClassificationORM,
                    RightsClassificationORM.document_id == DocumentORM.id,
                )
                .join(
                    DocumentEmbeddingORM,
                    DocumentEmbeddingORM.document_id == DocumentORM.id,
                )
                .where(
                    RightsClassificationORM.jurisdiction == jurisdiction,
                    RightsClassificationORM.may_process.is_(True),
                    RightsClassificationORM.revoked_at.is_(None),
                    DocumentEmbeddingORM.model_name == embedding_model_name,
                )
            )
            if issuer is not None:
                # Mirrors search_documents_for_jurisdiction's own issuer
                # handling. Unlike that method, no distinct() is needed here:
                # a document with several designations from the same issuer
                # can produce duplicate rows from this join, but the
                # "if row.id in seen_document_ids" check below already
                # collapses those back to a single entry -- and unlike Tier
                # 1's plain equality ORDER BY DocumentORM.id, this query
                # orders by a cosine-distance expression that isn't in the
                # select list, which Postgres's SELECT DISTINCT disallows.
                tier2_query = tier2_query.join(
                    DocumentDesignationORM,
                    DocumentDesignationORM.document_id == DocumentORM.id,
                ).where(DocumentDesignationORM.issuer == issuer)
            rows = self._session.execute(
                tier2_query.order_by(
                    DocumentEmbeddingORM.vector.cosine_distance(query_vector)
                ).limit(_SEMANTIC_CANDIDATE_POOL)
            ).scalars()
            for row in rows:
                if row.id in seen_document_ids:
                    continue
                seen_document_ids.add(row.id)
                ordered_documents.append(_document_to_domain(row))

        seen_work_ids: set[uuid.UUID] = set()
        grouped: list[Document] = []
        for document in ordered_documents:
            if document.work_id in seen_work_ids:
                continue
            seen_work_ids.add(document.work_id)
            grouped.append(document)

        total = len(grouped)
        page = grouped[offset:offset + limit]
        if not page:
            return [], total

        edition_counts = dict(
            self._session.execute(
                select(DocumentORM.work_id, sa.func.count())
                .join(
                    RightsClassificationORM,
                    RightsClassificationORM.document_id == DocumentORM.id,
                )
                .where(
                    DocumentORM.work_id.in_([document.work_id for document in page]),
                    RightsClassificationORM.jurisdiction == jurisdiction,
                    RightsClassificationORM.may_process.is_(True),
                    RightsClassificationORM.revoked_at.is_(None),
                )
                .group_by(DocumentORM.work_id)
            ).all()
        )
        return [
            WorkSearchHit(
                work_id=document.work_id, best_match=document,
                other_editions_count=edition_counts[document.work_id] - 1,
            )
            for document in page
        ], total


def _work_to_domain(orm: WorkORM) -> Work:
    return Work(
        id=orm.id,
        status=orm.status,
        merged_into_work_id=orm.merged_into_work_id,
        created_via=orm.created_via,
        created_at=orm.created_at,
    )


class PostgresWorkRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_work(self, *, created_via: WorkCreatedVia) -> Work:
        orm = WorkORM(id=uuid.uuid4(), status=WorkStatus.ACTIVE, created_via=created_via)
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _work_to_domain(orm)

    def get_work(self, work_id: uuid.UUID) -> Work | None:
        orm = self._session.get(WorkORM, work_id)
        if orm is None:
            return None
        if orm.status == WorkStatus.MERGED and orm.merged_into_work_id is not None:
            orm = self._session.get(WorkORM, orm.merged_into_work_id)
        return _work_to_domain(orm)


def _watchlist_to_domain(orm: WatchlistORM) -> Watchlist:
    return Watchlist(
        id=orm.id, account_id=orm.account_id, work_id=orm.work_id, created_at=orm.created_at,
    )


class PostgresWatchlistRepository:
    def __init__(self, session: Session):
        self._session = session

    def add_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> Watchlist:
        existing = self._existing(account_id, work_id)
        if existing is not None:
            return _watchlist_to_domain(existing)

        orm = WatchlistORM(id=uuid.uuid4(), account_id=account_id, work_id=work_id)
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._existing(account_id, work_id)
            if existing is None:
                raise
            return _watchlist_to_domain(existing)
        self._session.refresh(orm)
        return _watchlist_to_domain(orm)

    def remove_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> None:
        self._session.execute(
            sa.delete(WatchlistORM).where(
                WatchlistORM.account_id == account_id, WatchlistORM.work_id == work_id
            )
        )

    def list_watches_for_account(self, account_id: uuid.UUID) -> list[Watchlist]:
        rows = self._session.execute(
            select(WatchlistORM)
            .where(WatchlistORM.account_id == account_id)
            .order_by(WatchlistORM.created_at, WatchlistORM.id)
        ).scalars()
        return [_watchlist_to_domain(row) for row in rows]

    def list_all_watches(self) -> list[Watchlist]:
        rows = self._session.execute(
            select(WatchlistORM).order_by(WatchlistORM.id)
        ).scalars()
        return [_watchlist_to_domain(row) for row in rows]

    def _existing(self, account_id: uuid.UUID, work_id: uuid.UUID) -> WatchlistORM | None:
        return self._session.execute(
            select(WatchlistORM).where(
                WatchlistORM.account_id == account_id, WatchlistORM.work_id == work_id
            )
        ).scalar_one_or_none()


def _notification_to_domain(orm: NotificationORM) -> Notification:
    return Notification(
        id=orm.id, account_id=orm.account_id, work_id=orm.work_id,
        trigger_type=orm.trigger_type, trigger_edge_id=orm.trigger_edge_id,
        trigger_document_id=orm.trigger_document_id,
        trigger_jurisdiction=orm.trigger_jurisdiction,
        may_process=orm.may_process, may_index_fulltext=orm.may_index_fulltext,
        may_cite_passages=orm.may_cite_passages, may_export_free=orm.may_export_free,
        created_at=orm.created_at, read_at=orm.read_at, emailed_at=orm.emailed_at,
    )


class PostgresNotificationRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID | None,
        trigger_document_id: uuid.UUID | None,
        trigger_jurisdiction: str | None,
        may_process: bool | None,
        may_index_fulltext: bool | None,
        may_cite_passages: bool | None,
        may_export_free: bool | None,
        emailed_at: datetime | None,
    ) -> Notification:
        orm = NotificationORM(
            id=uuid.uuid4(), account_id=account_id, work_id=work_id, trigger_type=trigger_type,
            trigger_edge_id=trigger_edge_id, trigger_document_id=trigger_document_id,
            trigger_jurisdiction=trigger_jurisdiction, may_process=may_process,
            may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
            may_export_free=may_export_free, read_at=None, emailed_at=emailed_at,
            # Set client-side rather than relying on the column's
            # server_default=func.now(): Postgres freezes now() at
            # transaction start, so several notifications created inside one
            # transaction (e.g. multiple notify-watchers runs sharing a test
            # session) would otherwise all get an identical created_at and
            # make list_for_account's `ORDER BY created_at DESC, id DESC`
            # fall back to random UUID ordering for the tiebreak.
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _notification_to_domain(orm)

    def find_by_trigger_edge(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> Notification | None:
        orm = self._session.execute(
            select(NotificationORM).where(
                NotificationORM.account_id == account_id,
                NotificationORM.work_id == work_id,
                NotificationORM.trigger_type == trigger_type,
                NotificationORM.trigger_edge_id == trigger_edge_id,
            )
        ).scalar_one_or_none()
        return _notification_to_domain(orm) if orm else None

    def list_for_account(self, account_id: uuid.UUID) -> list[Notification]:
        rows = self._session.execute(
            select(NotificationORM)
            .where(NotificationORM.account_id == account_id)
            .order_by(NotificationORM.created_at.desc(), NotificationORM.id.desc())
        ).scalars()
        return [_notification_to_domain(row) for row in rows]

    def mark_read(
        self, notification_id: uuid.UUID, *, account_id: uuid.UUID, read_at: datetime
    ) -> bool:
        result = self._session.execute(
            sa.update(NotificationORM)
            .where(NotificationORM.id == notification_id, NotificationORM.account_id == account_id)
            .values(read_at=read_at)
        )
        return result.rowcount > 0

    def delete_read_before(self, cutoff: datetime) -> int:
        # Only read notifications are ever eligible -- an account that hasn't
        # logged in for months must not lose notifications it hasn't seen yet,
        # regardless of age. Mirrors PostgresRateLimitRepository's
        # delete_buckets_before opportunistic-cleanup idiom.
        result = self._session.execute(
            sa.delete(NotificationORM).where(
                NotificationORM.read_at.is_not(None),
                NotificationORM.created_at < cutoff,
            )
        )
        return result.rowcount


def _rights_to_domain(orm: RightsClassificationORM) -> RightsClassification:
    return RightsClassification(
        document_id=orm.document_id,
        jurisdiction=orm.jurisdiction,
        may_process=orm.may_process,
        may_index_fulltext=orm.may_index_fulltext,
        may_cite_passages=orm.may_cite_passages,
        may_export_free=orm.may_export_free,
        legal_basis_reference=orm.legal_basis_reference,
        classified_at=orm.classified_at,
        classified_by=orm.classified_by,
        delivery_id=orm.delivery_id,
        revoked_at=orm.revoked_at,
    )


class PostgresRightsRepository:
    def __init__(self, session: Session):
        self._session = session

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
    ) -> RightsClassification:
        _require_active_delivery(self._session, delivery_id)
        orm = RightsClassificationORM(
            document_id=document_id,
            jurisdiction=jurisdiction,
            may_process=may_process,
            may_index_fulltext=may_index_fulltext,
            may_cite_passages=may_cite_passages,
            may_export_free=may_export_free,
            legal_basis_reference=legal_basis_reference,
            classified_at=classified_at,
            classified_by=classified_by,
            delivery_id=delivery_id,
            revoked_at=None,
        )
        merged = self._session.merge(orm)
        self._session.flush()
        return _rights_to_domain(merged)

    def get_classification(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> RightsClassification | None:
        orm = self._session.get(RightsClassificationORM, (document_id, jurisdiction))
        return _rights_to_domain(orm) if orm else None

    def list_classifications_for_document_unchecked(
        self, document_id: uuid.UUID
    ) -> list[RightsClassification]:
        """
        Every classification row for `document_id`, one per jurisdiction ever
        classified, regardless of revoked_at. Internal/administrative use
        only (notify-watchers, Task 6) -- never callable from an HTTP
        endpoint.
        """
        rows = self._session.execute(
            select(RightsClassificationORM).where(
                RightsClassificationORM.document_id == document_id
            )
        ).scalars()
        return [_rights_to_domain(row) for row in rows]


def _rights_notification_baseline_to_domain(
    orm: RightsNotificationBaselineORM,
) -> RightsNotificationBaseline:
    return RightsNotificationBaseline(
        account_id=orm.account_id,
        work_id=orm.work_id,
        trigger_document_id=orm.trigger_document_id,
        trigger_jurisdiction=orm.trigger_jurisdiction,
        may_process=orm.may_process,
        may_index_fulltext=orm.may_index_fulltext,
        may_cite_passages=orm.may_cite_passages,
        may_export_free=orm.may_export_free,
        updated_at=orm.updated_at,
    )


class PostgresRightsNotificationBaselineRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_baseline(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_document_id: uuid.UUID,
        trigger_jurisdiction: str,
    ) -> RightsNotificationBaseline | None:
        orm = self._session.get(
            RightsNotificationBaselineORM,
            (account_id, work_id, trigger_document_id, trigger_jurisdiction),
        )
        return _rights_notification_baseline_to_domain(orm) if orm else None

    def upsert_baseline(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_document_id: uuid.UUID,
        trigger_jurisdiction: str,
        may_process: bool,
        may_index_fulltext: bool,
        may_cite_passages: bool,
        may_export_free: bool,
    ) -> RightsNotificationBaseline:
        orm = RightsNotificationBaselineORM(
            account_id=account_id,
            work_id=work_id,
            trigger_document_id=trigger_document_id,
            trigger_jurisdiction=trigger_jurisdiction,
            may_process=may_process,
            may_index_fulltext=may_index_fulltext,
            may_cite_passages=may_cite_passages,
            may_export_free=may_export_free,
        )
        merged = self._session.merge(orm)
        self._session.flush()
        return _rights_notification_baseline_to_domain(merged)


def _edge_to_domain(orm: EdgeORM) -> Edge:
    return Edge(
        id=orm.id,
        from_document_id=orm.from_document_id,
        to_document_id=orm.to_document_id,
        edge_type=orm.edge_type,
        jurisdiction=orm.jurisdiction,
        layer=orm.layer,
        delivery_id=orm.delivery_id,
        revoked_at=orm.revoked_at,
        created_at=orm.created_at,
    )


def _active_edge_query(
    from_document_id: uuid.UUID,
    to_document_id: uuid.UUID,
    edge_type: EdgeType,
    jurisdiction: str | None,
):
    """
    Select the one active edge the partial unique index
    ``uq_edge_active_from_to_type_jurisdiction`` allows for this tuple.

    The index keys on ``coalesce(jurisdiction, '')`` where ``revoked_at IS
    NULL``, so a NULL jurisdiction and an empty one are the same key here too.
    """
    return select(EdgeORM).where(
        EdgeORM.from_document_id == from_document_id,
        EdgeORM.to_document_id == to_document_id,
        EdgeORM.edge_type == edge_type,
        sa.func.coalesce(EdgeORM.jurisdiction, "") == (jurisdiction or ""),
        EdgeORM.revoked_at.is_(None),
    )


def _work_structure_entry_to_domain(
    document: DocumentORM, designation: str | None, status: str
) -> WorkStructureEntry:
    return WorkStructureEntry(
        document_id=document.id, origin_issuer=document.origin_issuer,
        origin_number=document.origin_number, edition=document.edition,
        designation=designation, status=status,
    )


class PostgresEdgeRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_edge(
        self,
        *,
        from_document_id: uuid.UUID,
        to_document_id: uuid.UUID,
        edge_type: EdgeType,
        jurisdiction: str | None,
        layer: Layer,
        delivery_id: uuid.UUID,
    ) -> Edge:
        _require_active_delivery(self._session, delivery_id)
        query = _active_edge_query(
            from_document_id, to_document_id, edge_type, jurisdiction
        )
        existing = self._session.execute(query).scalar_one_or_none()
        if existing is not None:
            return _edge_to_domain(existing)

        orm = EdgeORM(
            id=uuid.uuid4(),
            from_document_id=from_document_id,
            to_document_id=to_document_id,
            edge_type=edge_type,
            jurisdiction=jurisdiction,
            layer=layer,
            delivery_id=delivery_id,
            revoked_at=None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(query).scalar_one_or_none()
            if existing is None:
                raise
            return _edge_to_domain(existing)
        self._session.refresh(orm)
        return _edge_to_domain(orm)

    def list_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        # Outgoing edges, dual rights-gated, NO layer filter -- COMMERCIAL
        # edges are returned. Both endpoints must be readable in this
        # jurisdiction: gating the target alone would still reveal the
        # source's existence and its reference structure through a
        # jurisdiction the source is not readable in at all.
        #
        # Callers: pipeline/processing code only. Public HTTP endpoints must
        # use list_free_layer_edges_for_jurisdiction (adds layer == FREE) or,
        # for the bulk dump, list_exportable_edges_for_jurisdiction.
        source_rights = aliased(RightsClassificationORM, name="source_rights")
        target_rights = aliased(RightsClassificationORM, name="target_rights")
        rows = self._session.execute(
            select(EdgeORM)
            .join(source_rights, source_rights.document_id == EdgeORM.from_document_id)
            .join(target_rights, target_rights.document_id == EdgeORM.to_document_id)
            .where(
                EdgeORM.from_document_id == document_id,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                source_rights.jurisdiction == jurisdiction,
                source_rights.may_process.is_(True),
                source_rights.revoked_at.is_(None),
                target_rights.jurisdiction == jurisdiction,
                target_rights.may_process.is_(True),
                target_rights.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def list_incoming_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        # Mirror of list_edges_for_jurisdiction with the direction reversed:
        # returns edges where document_id is the *target* (to_document_id),
        # e.g. REPLACES/WITHDRAWN_BY edges a successor or withdrawal-notice
        # document points at document_id. Same dual rights-gating rationale
        # applies -- both endpoints must be readable in this jurisdiction --
        # and, like its outgoing sibling, NO layer filter: COMMERCIAL edges
        # are returned.
        #
        # Callers: pipeline/processing code only. The public validity endpoint
        # uses list_free_layer_incoming_edges_for_jurisdiction.
        source_rights = aliased(RightsClassificationORM, name="source_rights")
        target_rights = aliased(RightsClassificationORM, name="target_rights")
        rows = self._session.execute(
            select(EdgeORM)
            .join(source_rights, source_rights.document_id == EdgeORM.from_document_id)
            .join(target_rights, target_rights.document_id == EdgeORM.to_document_id)
            .where(
                EdgeORM.to_document_id == document_id,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                source_rights.jurisdiction == jurisdiction,
                source_rights.may_process.is_(True),
                source_rights.revoked_at.is_(None),
                target_rights.jurisdiction == jurisdiction,
                target_rights.may_process.is_(True),
                target_rights.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def list_incoming_edges_for_work_unchecked(
        self, document_ids: list[uuid.UUID], edge_types: tuple[EdgeType, ...]
    ) -> list[Edge]:
        """
        Incoming, unrevoked edges of the given types whose to_document_id is
        one of `document_ids` -- bounded to one Work's own documents, no
        rights-gating and no layer filter. Internal/administrative use only
        (notify-watchers, Task 6) -- never callable from an HTTP endpoint;
        every public read path keeps using the *_for_jurisdiction methods
        above.
        """
        if not document_ids:
            return []
        rows = self._session.execute(
            select(EdgeORM)
            .where(
                EdgeORM.to_document_id.in_(document_ids),
                EdgeORM.edge_type.in_(edge_types),
                EdgeORM.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def list_free_layer_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        # Exactly list_edges_for_jurisdiction plus `layer == Layer.FREE`.
        # Same outgoing direction, same dual may_process gating, same
        # ordering; no may_export_free condition.
        #
        # Caller: GET /v1/documents/{id}/edges. That endpoint is anonymous and
        # public, so a COMMERCIAL-layer edge (REQ-GRAPH-002 reserves
        # section-level references within licensed norms for the paid tier)
        # must not appear in it. It is deliberately not gated on
        # may_export_free: whether a document belongs in the bulk dump is a
        # different, narrower question than whether one of its relationships
        # is free-tier content.
        source_rights = aliased(RightsClassificationORM, name="source_rights")
        target_rights = aliased(RightsClassificationORM, name="target_rights")
        rows = self._session.execute(
            select(EdgeORM)
            .join(source_rights, source_rights.document_id == EdgeORM.from_document_id)
            .join(target_rights, target_rights.document_id == EdgeORM.to_document_id)
            .where(
                EdgeORM.from_document_id == document_id,
                EdgeORM.layer == Layer.FREE,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                source_rights.jurisdiction == jurisdiction,
                source_rights.may_process.is_(True),
                source_rights.revoked_at.is_(None),
                target_rights.jurisdiction == jurisdiction,
                target_rights.may_process.is_(True),
                target_rights.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def list_free_layer_incoming_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        # Exactly list_incoming_edges_for_jurisdiction plus
        # `layer == Layer.FREE`; the incoming-direction counterpart of
        # list_free_layer_edges_for_jurisdiction (see there for the rationale).
        #
        # Caller: GET /v1/documents/{id}/validity.
        source_rights = aliased(RightsClassificationORM, name="source_rights")
        target_rights = aliased(RightsClassificationORM, name="target_rights")
        rows = self._session.execute(
            select(EdgeORM)
            .join(source_rights, source_rights.document_id == EdgeORM.from_document_id)
            .join(target_rights, target_rights.document_id == EdgeORM.to_document_id)
            .where(
                EdgeORM.to_document_id == document_id,
                EdgeORM.layer == Layer.FREE,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                source_rights.jurisdiction == jurisdiction,
                source_rights.may_process.is_(True),
                source_rights.revoked_at.is_(None),
                target_rights.jurisdiction == jurisdiction,
                target_rights.may_process.is_(True),
                target_rights.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def list_exportable_edges_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Edge]:
        # The strictest of the four listings: list_edges_for_jurisdiction plus
        # `layer == Layer.FREE` plus may_export_free on BOTH endpoints. It is
        # the only one that consults may_export_free.
        #
        # Layer.COMMERCIAL edges (e.g. section-level references reserved for
        # the commercial layer) stay excluded here, as they do in
        # list_free_layer_edges_for_jurisdiction; the unfiltered
        # list_edges_for_jurisdiction still returns them for processing use.
        # Requiring may_export_free on BOTH aliases (not just the source)
        # keeps this method self-contained: any edge it returns has both
        # endpoints exportable, so a caller iterating only exportable
        # documents never ends up with a dangling to_document_id reference in
        # the export.
        #
        # Caller: GET /v1/export. Single-document endpoints must NOT use this
        # -- may_export_free would over-restrict them.
        source_rights = aliased(RightsClassificationORM, name="source_rights")
        target_rights = aliased(RightsClassificationORM, name="target_rights")
        rows = self._session.execute(
            select(EdgeORM)
            .join(source_rights, source_rights.document_id == EdgeORM.from_document_id)
            .join(target_rights, target_rights.document_id == EdgeORM.to_document_id)
            .where(
                EdgeORM.from_document_id == document_id,
                EdgeORM.layer == Layer.FREE,
                EdgeORM.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
                source_rights.jurisdiction == jurisdiction,
                source_rights.may_process.is_(True),
                source_rights.may_export_free.is_(True),
                source_rights.revoked_at.is_(None),
                target_rights.jurisdiction == jurisdiction,
                target_rights.may_process.is_(True),
                target_rights.may_export_free.is_(True),
                target_rights.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]

    def get_work_structure_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> WorkStructure | None:
        viewed = self._session.execute(
            select(DocumentORM)
            .join(RightsClassificationORM, RightsClassificationORM.document_id == DocumentORM.id)
            .where(
                DocumentORM.id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if viewed is None:
            return None

        work_documents = list(self._session.execute(
            select(DocumentORM)
            .join(RightsClassificationORM, RightsClassificationORM.document_id == DocumentORM.id)
            .where(
                DocumentORM.work_id == viewed.work_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(DocumentORM.edition, DocumentORM.id)
        ).scalars())
        document_ids = [d.id for d in work_documents]

        # `document_id` alone in its (visible) Work -- no other member to
        # form a chain or an adoption with, so both lists are empty rather
        # than a single-entry `editions` containing just itself.
        if len(work_documents) <= 1:
            return WorkStructure(work_id=viewed.work_id, editions=[], national_adoptions=[])

        # One-time, bounded traversal over THIS Work's own documents/edges
        # only -- not a pattern for wider application code (ADR-006 keeps
        # graph queries shallow); bounded by the Work grouping itself.
        # layer == FREE plus the jurisdiction OR-clause matches the same
        # filters list_free_layer_incoming_edges_for_jurisdiction already
        # applies to these same edge types for GET .../validity --
        # pre-existing behavior, kept consistent here rather than resolved
        # differently for a new endpoint.
        edges = list(self._session.execute(
            select(EdgeORM)
            .where(
                EdgeORM.edge_type.in_(_WORK_STRUCTURE_EDGE_TYPES),
                EdgeORM.from_document_id.in_(document_ids),
                EdgeORM.to_document_id.in_(document_ids),
                EdgeORM.revoked_at.is_(None),
                EdgeORM.layer == Layer.FREE,
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == jurisdiction),
            )
        ).scalars())

        parent = {d.id: d.id for d in work_documents}

        def find(x: uuid.UUID) -> uuid.UUID:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: uuid.UUID, b: uuid.UUID) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for edge in edges:
            if edge.edge_type in _EDITION_CHAIN_EDGE_TYPES:
                union(edge.from_document_id, edge.to_document_id)

        edition_root = find(document_id)
        edition_ids = {d.id for d in work_documents if find(d.id) == edition_root}
        # `document_id`'s only Work sibling(s) came in via ADOPTED_FROM, with
        # no REPLACES/WITHDRAWN_BY edge to form an edition chain -- same
        # rationale as the whole-Work case above, applied at the partition
        # level: no other member to form a chain with, so `editions` is
        # empty rather than a single-entry list containing just itself.
        if len(edition_ids) <= 1:
            edition_ids = set()

        replaced_ids = {e.to_document_id for e in edges if e.edge_type == EdgeType.REPLACES}
        withdrawn_ids = {e.to_document_id for e in edges if e.edge_type == EdgeType.WITHDRAWN_BY}

        def status_for(doc_id: uuid.UUID) -> str:
            if doc_id in replaced_ids:
                return "replaced"
            if doc_id in withdrawn_ids:
                return "withdrawn"
            return "valid"

        designations_by_document = dict(self._session.execute(
            select(DocumentDesignationORM.document_id, DocumentDesignationORM.designation)
            .where(
                DocumentDesignationORM.document_id.in_(document_ids),
                DocumentDesignationORM.is_primary.is_(True),
            )
        ).all())

        editions = [
            _work_structure_entry_to_domain(
                d, designations_by_document.get(d.id), status_for(d.id)
            )
            for d in work_documents if d.id in edition_ids
        ]
        national_adoptions = [
            _work_structure_entry_to_domain(
                d, designations_by_document.get(d.id), status_for(d.id)
            )
            for d in work_documents if d.id not in edition_ids
        ]

        return WorkStructure(
            work_id=viewed.work_id, editions=editions, national_adoptions=national_adoptions,
        )


def _segment_to_domain(orm: SegmentORM) -> Segment:
    return Segment(
        id=orm.id,
        document_id=orm.document_id,
        delivery_id=orm.delivery_id,
        sequence_number=orm.sequence_number,
        heading=orm.heading,
        text=orm.text,
        language=orm.language,
        created_at=orm.created_at,
    )


class PostgresSegmentRepository:
    def __init__(self, session: Session):
        self._session = session

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
        _require_active_delivery(self._session, delivery_id)

        # The dedupe key is delivery-scoped, matching
        # uq_segment_document_delivery_sequence: re-running one delivery must
        # not duplicate its segments, but a *second* delivery of the same
        # document — an amended text — owns its own segment rows. Keyed on
        # (document_id, sequence_number) alone, the second delivery would be
        # handed the first one's stale text, and revoking the first delivery
        # would delete a segment the second one believes it owns.
        query = select(SegmentORM).where(
            SegmentORM.document_id == document_id,
            SegmentORM.delivery_id == delivery_id,
            SegmentORM.sequence_number == sequence_number,
        )
        existing = self._session.execute(query).scalar_one_or_none()
        if existing is not None:
            return _segment_to_domain(existing), False

        orm = SegmentORM(
            id=uuid.uuid4(),
            document_id=document_id,
            delivery_id=delivery_id,
            sequence_number=sequence_number,
            heading=heading,
            text=text,
            language=language,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(query).scalar_one_or_none()
            if existing is None:
                raise
            return _segment_to_domain(existing), False
        return _segment_to_domain(orm), True

    def list_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]:
        # The read gate must ask the same question the write gate asked: the
        # pipeline only creates segments when `may_index_fulltext` is true.
        # Classification is updated in place, so a document whose rights are
        # later tightened would otherwise keep serving full-text segments
        # written while they were still permitted.
        rows = self._session.execute(
            select(SegmentORM)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == SegmentORM.document_id,
            )
            .where(
                SegmentORM.document_id == document_id,
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(SegmentORM.sequence_number)
        ).scalars()
        return [_segment_to_domain(row) for row in rows]

    def find_similar_segments_for_jurisdiction(
        self, query_vector: list[float], jurisdiction: str, model_name: str, limit: int = 5,
    ) -> list[Segment]:
        # Same read gate as list_segments_for_jurisdiction (may_process AND
        # may_index_fulltext AND not revoked) -- similarity search is a
        # different sort order over the same visible set, not a second rights
        # check. model_name is required, not defaulted: mixing vectors from
        # two different embedding models in one ORDER BY would compare
        # distances that live in unrelated vector spaces and return
        # meaningless nonsense silently.
        rows = self._session.execute(
            select(SegmentORM)
            .join(EmbeddingORM, EmbeddingORM.segment_id == SegmentORM.id)
            .join(
                RightsClassificationORM,
                RightsClassificationORM.document_id == SegmentORM.document_id,
            )
            .where(
                RightsClassificationORM.jurisdiction == jurisdiction,
                RightsClassificationORM.may_process.is_(True),
                RightsClassificationORM.may_index_fulltext.is_(True),
                RightsClassificationORM.revoked_at.is_(None),
                EmbeddingORM.model_name == model_name,
            )
            .order_by(EmbeddingORM.vector.cosine_distance(query_vector))
            .limit(limit)
        ).scalars()
        return [_segment_to_domain(row) for row in rows]


def _embedding_to_domain(orm: EmbeddingORM) -> Embedding:
    return Embedding(
        id=orm.id,
        segment_id=orm.segment_id,
        delivery_id=orm.delivery_id,
        model_name=orm.model_name,
        vector=list(orm.vector),
        created_at=orm.created_at,
    )


class PostgresEmbeddingRepository:
    def __init__(self, session: Session):
        self._session = session

    def add_embedding(
        self,
        *,
        segment_id: uuid.UUID,
        delivery_id: uuid.UUID,
        model_name: str,
        vector: list[float],
    ) -> tuple[Embedding, bool]:
        _require_active_delivery(self._session, delivery_id)

        existing = self._session.execute(
            select(EmbeddingORM).where(
                EmbeddingORM.segment_id == segment_id,
                EmbeddingORM.model_name == model_name,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _embedding_to_domain(existing), False

        orm = EmbeddingORM(
            id=uuid.uuid4(),
            segment_id=segment_id,
            delivery_id=delivery_id,
            model_name=model_name,
            vector=vector,
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._session.execute(
                select(EmbeddingORM).where(
                    EmbeddingORM.segment_id == segment_id,
                    EmbeddingORM.model_name == model_name,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _embedding_to_domain(existing), False
        return _embedding_to_domain(orm), True

    def get_embedding_unchecked(
        self, segment_id: uuid.UUID, model_name: str
    ) -> Embedding | None:
        """
        Fetch one embedding without any rights gate.

        Deliberately not part of the `EmbeddingRepository` Protocol: it takes no
        jurisdiction and joins no classification, so it is a pipeline and
        administrative method (proving an embedding was removed with its
        delivery, say), never a content-serving read.
        """
        orm = self._session.execute(
            select(EmbeddingORM).where(
                EmbeddingORM.segment_id == segment_id,
                EmbeddingORM.model_name == model_name,
            )
        ).scalar_one_or_none()
        return _embedding_to_domain(orm) if orm else None


def _document_embedding_to_domain(orm: DocumentEmbeddingORM) -> DocumentEmbedding:
    return DocumentEmbedding(
        id=orm.id,
        document_id=orm.document_id,
        model_name=orm.model_name,
        vector=list(orm.vector),
        delivery_id=orm.delivery_id,
        created_at=orm.created_at,
    )


class PostgresDocumentEmbeddingRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_document_embedding(
        self, *, document_id: uuid.UUID, delivery_id: uuid.UUID, model_name: str,
        vector: list[float],
    ) -> DocumentEmbedding:
        _require_active_delivery(self._session, delivery_id)
        stmt = (
            pg_insert(DocumentEmbeddingORM)
            .values(
                id=uuid.uuid4(), document_id=document_id, delivery_id=delivery_id,
                model_name=model_name, vector=vector,
            )
            .on_conflict_do_update(
                index_elements=[DocumentEmbeddingORM.document_id, DocumentEmbeddingORM.model_name],
                set_={"vector": vector, "delivery_id": delivery_id},
            )
            .returning(DocumentEmbeddingORM)
        )
        orm = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return _document_embedding_to_domain(orm)

    def list_documents_without_embedding(self, model_name: str) -> list[Document]:
        rows = self._session.execute(
            select(DocumentORM)
            .where(
                ~sa.exists(
                    select(DocumentEmbeddingORM.id).where(
                        DocumentEmbeddingORM.document_id == DocumentORM.id,
                        DocumentEmbeddingORM.model_name == model_name,
                    )
                )
            )
            .order_by(DocumentORM.id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]


def _identity_case_to_domain(orm: IdentityResolutionCaseORM) -> IdentityResolutionCase:
    return IdentityResolutionCase(
        id=orm.id,
        delivery_id=orm.delivery_id,
        case_type=orm.case_type,
        raw_designation=orm.raw_designation,
        raw_issuer=orm.raw_issuer,
        reason=orm.reason,
        status=orm.status,
        resolved_document_id=orm.resolved_document_id,
        source_work_id=orm.source_work_id,
        target_work_id=orm.target_work_id,
        resolved_at=orm.resolved_at,
        resolved_by=orm.resolved_by,
        created_at=orm.created_at,
    )


class PostgresIdentityResolutionRepository:
    def __init__(self, session: Session):
        self._session = session

    def enqueue_case(
        self,
        *,
        delivery_id: uuid.UUID,
        raw_designation: str,
        raw_issuer: str | None,
        reason: str,
    ) -> IdentityResolutionCase:
        _require_active_delivery(self._session, delivery_id)
        orm = IdentityResolutionCaseORM(
            id=uuid.uuid4(),
            delivery_id=delivery_id,
            raw_designation=raw_designation,
            raw_issuer=raw_issuer,
            reason=reason,
            status=IdentityResolutionStatus.PENDING,
        )
        self._session.add(orm)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def enqueue_work_merge_case(
        self, *, delivery_id: uuid.UUID, source_work_id: uuid.UUID,
        target_work_id: uuid.UUID, reason: str,
    ) -> IdentityResolutionCase:
        _require_active_delivery(self._session, delivery_id)
        orm = IdentityResolutionCaseORM(
            id=uuid.uuid4(),
            delivery_id=delivery_id,
            case_type=IdentityResolutionCaseType.WORK_MERGE,
            raw_designation=None,
            raw_issuer=None,
            reason=reason,
            status=IdentityResolutionStatus.PENDING,
            source_work_id=source_work_id,
            target_work_id=target_work_id,
        )
        self._session.add(orm)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def list_pending_cases(self) -> list[IdentityResolutionCase]:
        rows = self._session.execute(
            select(IdentityResolutionCaseORM)
            .where(IdentityResolutionCaseORM.status == IdentityResolutionStatus.PENDING)
            .order_by(IdentityResolutionCaseORM.created_at)
        ).scalars()
        return [_identity_case_to_domain(row) for row in rows]

    def resolve_case(
        self, case_id: uuid.UUID, *, resolved_document_id: uuid.UUID, resolved_by: str
    ) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        orm.status = IdentityResolutionStatus.RESOLVED
        orm.resolved_document_id = resolved_document_id
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def resolve_work_merge_case(
        self, case_id: uuid.UUID, *, resolved_by: str
    ) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        source_work = self._session.get(WorkORM, orm.source_work_id)
        target_work = self._session.get(WorkORM, orm.target_work_id)
        if orm.source_work_id == orm.target_work_id or target_work.status != WorkStatus.ACTIVE:
            raise ContradictoryWorkMergeError(orm.source_work_id, orm.target_work_id)

        self._session.execute(
            sa.update(DocumentORM)
            .where(DocumentORM.work_id == orm.source_work_id)
            .values(work_id=orm.target_work_id)
        )
        source_work.status = WorkStatus.MERGED
        source_work.merged_into_work_id = orm.target_work_id

        # Keep every merge chain exactly one hop deep: any other Work that
        # was already pointing at the source (from an earlier merge into it)
        # must now point at the new target instead, or get_work()'s
        # single-hop redirect would land on a Work that is itself retired.
        self._session.execute(
            sa.update(WorkORM)
            .where(WorkORM.merged_into_work_id == orm.source_work_id)
            .values(merged_into_work_id=orm.target_work_id)
        )

        orm.status = IdentityResolutionStatus.RESOLVED
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)

    def reject_case(self, case_id: uuid.UUID, *, resolved_by: str) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        orm.status = IdentityResolutionStatus.REJECTED
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)


def _account_to_domain(orm: AccountORM) -> Account:
    return Account(
        id=orm.id, email=orm.email, password_hash=orm.password_hash,
        email_verified_at=orm.email_verified_at, created_at=orm.created_at,
        first_name=orm.first_name, last_name=orm.last_name,
        avatar_image=orm.avatar_image, avatar_content_type=orm.avatar_content_type,
        notification_preference=orm.notification_preference,
    )


class PostgresAccountRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_account(self, *, email: str, password_hash: str | None) -> Account:
        orm = AccountORM(id=uuid.uuid4(), email=email, password_hash=password_hash)
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegisteredError(email) from exc
        return _account_to_domain(orm)

    def get_account_by_id(self, account_id: uuid.UUID) -> Account | None:
        orm = self._session.get(AccountORM, account_id)
        return _account_to_domain(orm) if orm else None

    def get_account_by_email(self, email: str) -> Account | None:
        orm = self._session.execute(
            select(AccountORM).where(AccountORM.email == email)
        ).scalar_one_or_none()
        return _account_to_domain(orm) if orm else None

    def mark_email_verified(self, account_id: uuid.UUID, verified_at: datetime) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(email_verified_at=verified_at)
        )

    def set_password_hash(self, account_id: uuid.UUID, password_hash: str) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(password_hash=password_hash)
        )

    def update_email(self, account_id: uuid.UUID, new_email: str) -> None:
        # The caller (the email-change confirm flow) already checks that
        # new_email is free before calling this, but that check-then-act is
        # only advisory -- two confirm requests racing for the same
        # newly-freed address can both pass the check. The savepoint here
        # mirrors create_account: it surfaces uq_account_email as a clean,
        # catchable IntegrityError instead of aborting the whole session.
        try:
            with self._session.begin_nested():
                self._session.execute(
                    sa.update(AccountORM)
                    .where(AccountORM.id == account_id)
                    .values(email=new_email)
                )
                self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegisteredError(new_email) from exc

    def update_profile_names(
        self, account_id: uuid.UUID, *, first_name: str | None, last_name: str | None
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(first_name=first_name, last_name=last_name)
        )

    def update_notification_preference(
        self, account_id: uuid.UUID, *, preference: NotificationPreference
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(notification_preference=preference)
        )

    def set_avatar(
        self, account_id: uuid.UUID, *, avatar_image: bytes, avatar_content_type: str
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(avatar_image=avatar_image, avatar_content_type=avatar_content_type)
        )

    def clear_avatar(self, account_id: uuid.UUID) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(avatar_image=None, avatar_content_type=None)
        )

    def delete_account(self, account_id: uuid.UUID) -> None:
        # Explicit, ordered deletes rather than relying on database-level
        # CASCADE: none of the foreign keys into `account` declare ON DELETE
        # CASCADE (they default to RESTRICT/NO ACTION), and changing that
        # default now would also silently affect every other code path that
        # might ever delete an account row. Children before parents,
        # respecting every FK in this dependency chain.
        session_ids = self._session.execute(
            select(ChatSessionORM.id).where(ChatSessionORM.account_id == account_id)
        ).scalars().all()
        if session_ids:
            message_ids = self._session.execute(
                select(ChatMessageORM.id).where(ChatMessageORM.session_id.in_(session_ids))
            ).scalars().all()
            if message_ids:
                self._session.execute(
                    sa.delete(ChatMessageCitationORM).where(
                        ChatMessageCitationORM.message_id.in_(message_ids)
                    )
                )
            self._session.execute(
                sa.delete(ChatMessageORM).where(ChatMessageORM.session_id.in_(session_ids))
            )
            self._session.execute(
                sa.delete(ChatSessionORM).where(ChatSessionORM.account_id == account_id)
            )
        self._session.execute(
            sa.delete(AccountTokenORM).where(AccountTokenORM.account_id == account_id)
        )
        self._session.execute(
            sa.delete(AccountSessionORM).where(AccountSessionORM.account_id == account_id)
        )
        self._session.execute(
            sa.delete(AccountGoogleIdentityORM).where(
                AccountGoogleIdentityORM.account_id == account_id
            )
        )
        self._session.execute(
            sa.delete(NotificationORM).where(NotificationORM.account_id == account_id)
        )
        self._session.execute(
            sa.delete(RightsNotificationBaselineORM).where(
                RightsNotificationBaselineORM.account_id == account_id
            )
        )
        self._session.execute(
            sa.delete(WatchlistORM).where(WatchlistORM.account_id == account_id)
        )
        self._session.execute(sa.delete(AccountORM).where(AccountORM.id == account_id))


class PostgresAccountGoogleIdentityRepository:
    def __init__(self, session: Session):
        self._session = session

    def link_google_identity(
        self, *, account_id: uuid.UUID, google_subject_id: str
    ) -> AccountGoogleIdentity:
        # Two constraints can collide here: account_id is the primary key
        # (one Google identity per account), and google_subject_id is unique
        # (one account per Google identity). The insert therefore runs inside
        # a savepoint, the same as create_account -- an unguarded
        # IntegrityError would not merely raise, it would leave the whole
        # session unusable for the rest of the request.
        existing = self._session.get(AccountGoogleIdentityORM, account_id)
        if existing is not None:
            if existing.google_subject_id == google_subject_id:
                # Exactly the requested link already exists: idempotent, same
                # convention as record_delivery and add_designation.
                return AccountGoogleIdentity(
                    account_id=existing.account_id,
                    google_subject_id=existing.google_subject_id,
                )
            # A different subject for this account. Checked here rather than
            # left to the constraint: adding a second instance under a primary
            # key the identity map already holds makes SQLAlchemy warn and
            # discard the pending row, so the database never sees the insert
            # and no IntegrityError is raised to catch.
            raise GoogleIdentityAlreadyLinkedError(account_id, google_subject_id)

        orm = AccountGoogleIdentityORM(
            account_id=account_id, google_subject_id=google_subject_id
        )
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError as exc:
            # The subject is already linked to a DIFFERENT account, or a
            # concurrent request won the race. Silently returning the existing
            # row would attach the caller to an identity they did not present,
            # so it surfaces as a named error instead.
            raise GoogleIdentityAlreadyLinkedError(account_id, google_subject_id) from exc
        return AccountGoogleIdentity(
            account_id=orm.account_id, google_subject_id=orm.google_subject_id
        )

    def get_account_by_google_subject(self, google_subject_id: str) -> Account | None:
        orm = self._session.execute(
            select(AccountORM)
            .join(
                AccountGoogleIdentityORM,
                AccountGoogleIdentityORM.account_id == AccountORM.id,
            )
            .where(AccountGoogleIdentityORM.google_subject_id == google_subject_id)
        ).scalar_one_or_none()
        return _account_to_domain(orm) if orm else None

    def has_google_identity(self, account_id: uuid.UUID) -> bool:
        return self._session.get(AccountGoogleIdentityORM, account_id) is not None


def _account_session_to_domain(orm: AccountSessionORM) -> AccountSession:
    return AccountSession(
        id=orm.id, account_id=orm.account_id, session_token=orm.session_token,
        created_at=orm.created_at, expires_at=orm.expires_at,
    )


class PostgresAccountSessionRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_session(
        self, *, account_id: uuid.UUID, session_token: str, created_at: datetime,
        expires_at: datetime,
    ) -> AccountSession:
        orm = AccountSessionORM(
            id=uuid.uuid4(), account_id=account_id, session_token=session_token,
            created_at=created_at, expires_at=expires_at,
        )
        self._session.add(orm)
        self._session.flush()
        return _account_session_to_domain(orm)

    def get_session_by_token(self, session_token: str) -> AccountSession | None:
        orm = self._session.execute(
            select(AccountSessionORM).where(
                AccountSessionORM.session_token == session_token,
                AccountSessionORM.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()
        return _account_session_to_domain(orm) if orm else None

    def extend_session(self, session_id: uuid.UUID, new_expires_at: datetime) -> None:
        self._session.execute(
            sa.update(AccountSessionORM)
            .where(AccountSessionORM.id == session_id)
            .values(expires_at=new_expires_at)
        )

    def revoke_session(self, session_token: str) -> None:
        self._session.execute(
            sa.delete(AccountSessionORM).where(
                AccountSessionORM.session_token == session_token
            )
        )

    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[AccountSession]:
        rows = self._session.execute(
            select(AccountSessionORM)
            .where(AccountSessionORM.account_id == account_id)
            .order_by(AccountSessionORM.created_at.desc())
        ).scalars()
        return [_account_session_to_domain(row) for row in rows]

    def revoke_session_by_id(self, session_id: uuid.UUID, account_id: uuid.UUID) -> bool:
        # Scoped by account_id in the WHERE clause, not just session_id --
        # this is what prevents one account from revoking another's session
        # by guessing/enumerating IDs. rowcount is 0 both when the id doesn't
        # exist and when it belongs to someone else; the caller cannot tell
        # those apart, which is exactly the point.
        result = self._session.execute(
            sa.delete(AccountSessionORM).where(
                AccountSessionORM.id == session_id,
                AccountSessionORM.account_id == account_id,
            )
        )
        return result.rowcount > 0


def _account_token_to_domain(orm: AccountTokenORM) -> AccountToken:
    return AccountToken(
        id=orm.id, account_id=orm.account_id, purpose=orm.purpose, token=orm.token,
        created_at=orm.created_at, expires_at=orm.expires_at, used_at=orm.used_at,
        email=orm.email,
    )


class PostgresAccountTokenRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_token(
        self, *, account_id: uuid.UUID | None = None, email: str | None = None,
        purpose: AccountTokenPurpose, token: str, created_at: datetime,
        expires_at: datetime,
    ) -> AccountToken:
        if (account_id is None) == (email is None):
            # Mirrors ck_account_token_account_or_email. Catching it here keeps
            # the caller's session usable: an IntegrityError from the check
            # constraint would abort the surrounding transaction, and this is a
            # programming error at the call site, never user input.
            raise ValueError(
                "create_token needs exactly one of account_id and email, "
                f"got account_id={account_id!r} and email={email!r}"
            )
        orm = AccountTokenORM(
            id=uuid.uuid4(), account_id=account_id, email=email, purpose=purpose,
            token=token, created_at=created_at, expires_at=expires_at, used_at=None,
        )
        self._session.add(orm)
        self._session.flush()
        return _account_token_to_domain(orm)

    def consume_token(
        self, token: str, purpose: AccountTokenPurpose
    ) -> AccountToken | None:
        now = datetime.now(timezone.utc)
        result = self._session.execute(
            sa.update(AccountTokenORM)
            .where(
                AccountTokenORM.token == token,
                AccountTokenORM.purpose == purpose,
                AccountTokenORM.used_at.is_(None),
                AccountTokenORM.expires_at > now,
            )
            .values(used_at=now)
            .returning(AccountTokenORM)
        )
        orm = result.scalar_one_or_none()
        return _account_token_to_domain(orm) if orm else None


def _oauth_state_to_domain(orm: OAuthStateORM) -> OAuthState:
    return OAuthState(
        id=orm.id, state=orm.state, created_at=orm.created_at,
        expires_at=orm.expires_at, used_at=orm.used_at,
    )


class PostgresOAuthStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_state(
        self, *, state: str, created_at: datetime, expires_at: datetime,
    ) -> OAuthState:
        orm = OAuthStateORM(
            id=uuid.uuid4(), state=state, created_at=created_at,
            expires_at=expires_at, used_at=None,
        )
        self._session.add(orm)
        self._session.flush()
        return _oauth_state_to_domain(orm)

    def consume_state(self, state: str) -> OAuthState | None:
        now = datetime.now(timezone.utc)
        result = self._session.execute(
            sa.update(OAuthStateORM)
            .where(
                OAuthStateORM.state == state,
                OAuthStateORM.used_at.is_(None),
                OAuthStateORM.expires_at > now,
            )
            .values(used_at=now)
            .returning(OAuthStateORM)
        )
        orm = result.scalar_one_or_none()
        return _oauth_state_to_domain(orm) if orm else None

    def delete_states_before(self, cutoff: datetime) -> None:
        # Without this the table grows one row per abandoned OAuth attempt
        # forever. Mirrors PostgresRateLimitRepository.delete_buckets_before's
        # opportunistic-cleanup idiom: called from create_state's own request
        # path (see google.py), no scheduled job needed.
        self._session.execute(
            sa.delete(OAuthStateORM).where(OAuthStateORM.created_at < cutoff)
        )
        self._session.flush()


def _chat_session_to_domain(orm: ChatSessionORM) -> ChatSession:
    return ChatSession(
        id=orm.id, session_token=orm.session_token, account_id=orm.account_id,
        jurisdiction=orm.jurisdiction, language=orm.language, created_at=orm.created_at,
    )


def _chat_message_to_domain(orm: ChatMessageORM) -> ChatMessage:
    return ChatMessage(
        id=orm.id, session_id=orm.session_id, role=orm.role, content=orm.content,
        answer_type=orm.answer_type, created_at=orm.created_at,
    )


def _chat_message_citation_to_domain(orm: ChatMessageCitationORM) -> ChatMessageCitation:
    return ChatMessageCitation(
        id=orm.id, message_id=orm.message_id, document_id=orm.document_id,
        segment_id=orm.segment_id,
    )


class PostgresChatRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_session(
        self, *, session_token: str, jurisdiction: str, language: str,
        created_at: datetime, account_id: uuid.UUID | None = None,
    ) -> ChatSession:
        orm = ChatSessionORM(
            id=uuid.uuid4(), session_token=session_token, account_id=account_id,
            jurisdiction=jurisdiction, language=language, created_at=created_at,
        )
        self._session.add(orm)
        self._session.flush()
        return _chat_session_to_domain(orm)

    def get_session_by_token(self, session_token: str) -> ChatSession | None:
        orm = self._session.execute(
            select(ChatSessionORM).where(ChatSessionORM.session_token == session_token)
        ).scalar_one_or_none()
        return _chat_session_to_domain(orm) if orm else None

    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[ChatSession]:
        rows = self._session.execute(
            select(ChatSessionORM)
            .where(ChatSessionORM.account_id == account_id)
            .order_by(ChatSessionORM.created_at.desc())
        ).scalars()
        return [_chat_session_to_domain(row) for row in rows]

    def link_account(self, session_id: uuid.UUID, account_id: uuid.UUID) -> None:
        self._session.execute(
            sa.update(ChatSessionORM)
            .where(ChatSessionORM.id == session_id)
            .values(account_id=account_id)
        )

    def create_message(
        self, *, session_id: uuid.UUID, role: ChatMessageRole, content: str,
        answer_type: ChatAnswerType | None, created_at: datetime,
    ) -> ChatMessage:
        orm = ChatMessageORM(
            id=uuid.uuid4(), session_id=session_id, role=role, content=content,
            answer_type=answer_type, created_at=created_at,
        )
        self._session.add(orm)
        self._session.flush()
        return _chat_message_to_domain(orm)

    def list_messages_for_session(self, session_id: uuid.UUID) -> list[ChatMessage]:
        rows = self._session.execute(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at)
        ).scalars()
        return [_chat_message_to_domain(row) for row in rows]

    def add_citation(
        self, *, message_id: uuid.UUID, document_id: uuid.UUID,
        segment_id: uuid.UUID | None,
    ) -> ChatMessageCitation:
        orm = ChatMessageCitationORM(
            id=uuid.uuid4(), message_id=message_id, document_id=document_id,
            segment_id=segment_id,
        )
        self._session.add(orm)
        self._session.flush()
        return _chat_message_citation_to_domain(orm)


class PostgresRateLimitRepository:
    def __init__(self, session: Session):
        self._session = session

    def record_and_check(self, *, key: str, window_start: datetime, limit: int) -> bool:
        # INSERT ... ON CONFLICT DO UPDATE is atomic under concurrent requests
        # for the same key -- two simultaneous requests in the same window
        # both reliably see their own increment, unlike a read-then-write
        # pattern from Python.
        stmt = (
            pg_insert(RateLimitBucketORM)
            .values(key=key, window_start=window_start, request_count=1)
            .on_conflict_do_update(
                index_elements=["key", "window_start"],
                set_={"request_count": RateLimitBucketORM.request_count + 1},
            )
            .returning(RateLimitBucketORM.request_count)
        )
        count = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return count <= limit

    def delete_buckets_before(self, cutoff: datetime) -> None:
        # Without this the table grows one row per (key, minute) forever, and
        # each key embeds a caller address -- so unbounded growth is also
        # indefinite retention of an identifier. Callers run it opportunistically
        # alongside record_and_check, which keeps the table bounded without a
        # scheduled job.
        self._session.execute(
            sa.delete(RateLimitBucketORM).where(RateLimitBucketORM.window_start < cutoff)
        )
        self._session.flush()
