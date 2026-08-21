# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime
from enum import Enum

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from normly_core.graph.domain import (
    AccountTokenPurpose,
    EdgeType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    Layer,
    TdmOptOutResult,
)


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    """
    Persist an enum member's ``.value``, not its ``.name``.

    Without ``values_callable`` SQLAlchemy stores the Python member name
    (``REPLACES``), while the migrations declare the lowercase values
    (``replaces``). Any future member whose name and value differ in length
    would then silently truncate or violate the CHECK constraint.
    """
    return [member.value for member in enum_cls]


class Base(DeclarativeBase):
    pass


class SourceORM(Base):
    __tablename__ = "source"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publisher: Mapped[str]
    retrieval_path: Mapped[str]
    legal_basis_category: Mapped[LegalBasisCategory] = mapped_column(
        sa.Enum(
            LegalBasisCategory,
            name="legal_basis_category",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    jurisdiction: Mapped[str]
    reviewed_at: Mapped[date]
    responsible_person: Mapped[str]
    commercial_catalog: Mapped[bool] = mapped_column(default=False)
    contract_reference: Mapped[str | None]
    tdm_opt_out_checked_at: Mapped[date | None]
    tdm_opt_out_result: Mapped[TdmOptOutResult | None] = mapped_column(
        sa.Enum(
            TdmOptOutResult,
            name="tdm_opt_out_result",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )

    __table_args__ = (
        sa.CheckConstraint(
            "NOT (legal_basis_category = 'D' AND commercial_catalog)",
            name="ck_source_no_category_d_commercial_catalog",
        ),
        sa.CheckConstraint(
            "legal_basis_category != 'C' OR contract_reference IS NOT NULL",
            name="ck_source_category_c_requires_contract",
        ),
    )


class DeliveryORM(Base):
    __tablename__ = "delivery"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("source.id"), nullable=False
    )
    content_hash: Mapped[str]
    ingested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("source_id", "content_hash", name="uq_delivery_source_hash"),
    )


class DocumentORM(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origin_issuer: Mapped[str]
    origin_number: Mapped[str]
    edition: Mapped[str]
    part: Mapped[str | None]
    created_via_delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class DocumentDesignationORM(Base):
    __tablename__ = "document_designation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    issuer: Mapped[str]
    designation: Mapped[str]
    language: Mapped[str]
    edition: Mapped[str | None]
    is_primary: Mapped[bool] = mapped_column(default=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("issuer", "designation", name="uq_designation_issuer_designation"),
    )


class DocumentTitleORM(Base):
    __tablename__ = "document_title"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    language: Mapped[str]
    title: Mapped[str]
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("document_id", "language", "title", name="uq_title_document_language_title"),
    )


class RightsClassificationORM(Base):
    __tablename__ = "rights_classification"

    # Primary key is (document_id, jurisdiction): a document has at most one
    # active classification per jurisdiction, and classify() upserts via
    # session.merge(). So only one delivery can ever back a document's
    # readability in a given jurisdiction at a time — a second delivery
    # cannot independently keep a document readable there once the first
    # delivery's classification is revoked.
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True
    )
    jurisdiction: Mapped[str] = mapped_column(primary_key=True)
    may_process: Mapped[bool]
    may_index_fulltext: Mapped[bool]
    may_cite_passages: Mapped[bool]
    may_export_free: Mapped[bool]
    legal_basis_reference: Mapped[str]
    classified_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    classified_by: Mapped[str]
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class EdgeORM(Base):
    __tablename__ = "edge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    to_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    edge_type: Mapped[EdgeType] = mapped_column(
        sa.Enum(
            EdgeType,
            name="edge_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    jurisdiction: Mapped[str | None]
    layer: Mapped[Layer] = mapped_column(
        sa.Enum(
            Layer,
            name="layer",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.Index(
            "uq_edge_active_from_to_type_jurisdiction",
            "from_document_id",
            "to_document_id",
            "edge_type",
            sa.text("coalesce(jurisdiction, '')"),
            unique=True,
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
    )


class SegmentORM(Base):
    __tablename__ = "segment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    sequence_number: Mapped[int]
    heading: Mapped[str | None]
    text: Mapped[str]
    language: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        # Delivery-scoped on purpose: a segment belongs to the delivery that
        # produced it. Without `delivery_id` in the key, a second delivery of
        # the same document would collide with the first delivery's segments
        # and be handed back their stale text.
        sa.UniqueConstraint(
            "document_id",
            "delivery_id",
            "sequence_number",
            name="uq_segment_document_delivery_sequence",
        ),
    )


class EmbeddingORM(Base):
    __tablename__ = "embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("segment.id", ondelete="CASCADE"), nullable=False
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    model_name: Mapped[str]
    vector: Mapped[list[float]] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("segment_id", "model_name", name="uq_embedding_segment_model"),
    )


class IdentityResolutionCaseORM(Base):
    __tablename__ = "identity_resolution_case"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    raw_designation: Mapped[str]
    raw_issuer: Mapped[str | None]
    reason: Mapped[str]
    status: Mapped[IdentityResolutionStatus] = mapped_column(
        sa.Enum(
            IdentityResolutionStatus,
            name="identity_resolution_status",
            native_enum=False,
            values_callable=_enum_values,
            create_constraint=True,
        ),
        default=IdentityResolutionStatus.PENDING,
    )
    resolved_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolved_by: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class AccountORM(Base):
    __tablename__ = "account"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str]
    password_hash: Mapped[str | None]
    email_verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (sa.UniqueConstraint("email", name="uq_account_email"),)


class AccountSessionORM(Base):
    __tablename__ = "account_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
    )
    session_token: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("session_token", name="uq_account_session_token"),
    )


class AccountGoogleIdentityORM(Base):
    __tablename__ = "account_google_identity"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True
    )
    google_subject_id: Mapped[str]

    __table_args__ = (
        sa.UniqueConstraint(
            "google_subject_id", name="uq_account_google_identity_subject"
        ),
    )


class AccountTokenORM(Base):
    __tablename__ = "account_token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=True
    )
    email: Mapped[str | None]
    purpose: Mapped[AccountTokenPurpose] = mapped_column(
        sa.Enum(
            AccountTokenPurpose, name="account_token_purpose", native_enum=False,
            values_callable=_enum_values, create_constraint=True,
        )
    )
    token: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("token", name="uq_account_token_token"),
        sa.CheckConstraint(
            "(account_id IS NULL) != (email IS NULL)",
            name="ck_account_token_account_or_email",
        ),
    )
