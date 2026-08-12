# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from normly_core.graph.domain import LegalBasisCategory, TdmOptOutResult


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
        sa.Enum(LegalBasisCategory, name="legal_basis_category", native_enum=False)
    )
    jurisdiction: Mapped[str]
    reviewed_at: Mapped[date]
    responsible_person: Mapped[str]
    commercial_catalog: Mapped[bool] = mapped_column(default=False)
    contract_reference: Mapped[str | None]
    tdm_opt_out_checked_at: Mapped[date | None]
    tdm_opt_out_result: Mapped[TdmOptOutResult | None] = mapped_column(
        sa.Enum(TdmOptOutResult, name="tdm_opt_out_result", native_enum=False)
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
    ingested_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]

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
