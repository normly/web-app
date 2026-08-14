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
        # Both endpoints must be readable in this jurisdiction. Gating the
        # target alone would still reveal the source's existence and its
        # reference structure through a jurisdiction the source is not
        # readable in at all.
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
    ) -> Segment:
        _require_active_delivery(self._session, delivery_id)

        existing = self._session.execute(
            select(SegmentORM).where(
                SegmentORM.document_id == document_id,
                SegmentORM.sequence_number == sequence_number,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _segment_to_domain(existing)

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
            existing = self._session.execute(
                select(SegmentORM).where(
                    SegmentORM.document_id == document_id,
                    SegmentORM.sequence_number == sequence_number,
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return _segment_to_domain(existing)
        return _segment_to_domain(orm)

    def list_segments_for_jurisdiction(
        self, document_id: uuid.UUID, jurisdiction: str
    ) -> list[Segment]:
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
                RightsClassificationORM.revoked_at.is_(None),
            )
            .order_by(SegmentORM.sequence_number)
        ).scalars()
        return [_segment_to_domain(row) for row in rows]
