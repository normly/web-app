# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from normly_core.graph.domain import (
    Delivery,
    Document,
    DocumentDesignation,
    DocumentTitle,
    Edge,
    EdgeType,
    Embedding,
    IdentityResolutionCase,
    IdentityResolutionStatus,
    LegalBasisCategory,
    Layer,
    RightsClassification,
    Segment,
    Source,
    TdmOptOutResult,
    WithdrawnDeliveryError,
)
from normly_core.graph.postgres.orm import (
    DeliveryORM,
    DocumentORM,
    DocumentDesignationORM,
    DocumentTitleORM,
    EdgeORM,
    EmbeddingORM,
    IdentityResolutionCaseORM,
    RightsClassificationORM,
    SegmentORM,
    SourceORM,
)


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
    ) -> Document:
        _require_active_delivery(self._session, delivery_id)
        orm = DocumentORM(
            id=uuid.uuid4(),
            origin_issuer=origin_issuer,
            origin_number=origin_number,
            edition=edition,
            part=part,
            created_via_delivery_id=delivery_id,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _document_to_domain(orm)

    def get_document_unchecked(self, document_id: uuid.UUID) -> Document | None:
        orm = self._session.get(DocumentORM, document_id)
        return _document_to_domain(orm) if orm else None

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
        # uq_designation_issuer_designation is global. The constraint stays
        # global on purpose: a designation identifies exactly one node
        # worldwide ("ein Regelwerk = ein Knoten"). Filtering the pre-check on
        # (issuer, designation) alone silently handed back another document's
        # row; with document_id in the key the collision instead reaches the
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
        rows = self._session.execute(
            select(DocumentDesignationORM)
            .where(DocumentDesignationORM.document_id == document_id)
            .order_by(DocumentDesignationORM.id)
        ).scalars()
        return [_designation_to_domain(row) for row in rows]

    def list_titles(self, document_id: uuid.UUID) -> list[DocumentTitle]:
        rows = self._session.execute(
            select(DocumentTitleORM)
            .where(DocumentTitleORM.document_id == document_id)
            .order_by(DocumentTitleORM.id)
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

    def find_by_designation(self, issuer: str, designation: str) -> Document | None:
        orm = self._session.execute(
            select(DocumentORM)
            .join(
                DocumentDesignationORM,
                DocumentDesignationORM.document_id == DocumentORM.id,
            )
            .where(
                DocumentDesignationORM.issuer == issuer,
                DocumentDesignationORM.designation == designation,
            )
        ).scalar_one_or_none()
        return _document_to_domain(orm) if orm else None


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


def _identity_case_to_domain(orm: IdentityResolutionCaseORM) -> IdentityResolutionCase:
    return IdentityResolutionCase(
        id=orm.id,
        delivery_id=orm.delivery_id,
        raw_designation=orm.raw_designation,
        raw_issuer=orm.raw_issuer,
        reason=orm.reason,
        status=orm.status,
        resolved_document_id=orm.resolved_document_id,
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

    def reject_case(self, case_id: uuid.UUID, *, resolved_by: str) -> IdentityResolutionCase:
        orm = self._session.get(IdentityResolutionCaseORM, case_id)
        orm.status = IdentityResolutionStatus.REJECTED
        orm.resolved_by = resolved_by
        orm.resolved_at = datetime.now(orm.created_at.tzinfo)
        self._session.flush()
        return _identity_case_to_domain(orm)
