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
    ChatAnswerType,
    ChatMessageRole,
    EdgeType,
    IdentityResolutionCaseType,
    IdentityResolutionStatus,
    LegalBasisCategory,
    Layer,
    NotificationPreference,
    NotificationTriggerType,
    TdmOptOutResult,
    WorkCreatedVia,
    WorkStatus,
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
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
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
        sa.UniqueConstraint(
            "issuer",
            "designation",
            "edition",
            name="uq_designation_issuer_designation_edition",
            postgresql_nulls_not_distinct=True,
        ),
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


class WorkORM(Base):
    __tablename__ = "work"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[WorkStatus] = mapped_column(
        sa.Enum(
            WorkStatus,
            name="work_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        default=WorkStatus.ACTIVE,
    )
    merged_into_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
    )
    created_via: Mapped[WorkCreatedVia] = mapped_column(
        sa.Enum(
            WorkCreatedVia,
            name="work_created_via",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
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


class DocumentEmbeddingORM(Base):
    __tablename__ = "document_embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str]
    vector: Mapped[list[float]] = mapped_column(Vector(1024))
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "document_id", "model_name", name="uq_document_embedding_document_model"
        ),
    )


class IdentityResolutionCaseORM(Base):
    __tablename__ = "identity_resolution_case"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("delivery.id"), nullable=False
    )
    case_type: Mapped[IdentityResolutionCaseType] = mapped_column(
        sa.Enum(
            IdentityResolutionCaseType,
            name="identity_resolution_case_type",
            native_enum=False,
            values_callable=_enum_values,
            create_constraint=True,
        ),
        default=IdentityResolutionCaseType.NEW_DOCUMENT,
    )
    raw_designation: Mapped[str | None]
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
    source_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
    )
    target_work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id")
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
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    avatar_image: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    avatar_content_type: Mapped[str | None]
    notification_preference: Mapped[NotificationPreference] = mapped_column(
        sa.Enum(
            NotificationPreference,
            name="notification_preference",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=NotificationPreference.NONE,
        server_default=NotificationPreference.NONE.value,
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


class OAuthStateORM(Base):
    __tablename__ = "oauth_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    state: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("state", name="uq_oauth_state_state"),
    )


class WatchlistORM(Base):
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("account_id", "work_id", name="uq_watchlist_account_work"),
    )


class NotificationORM(Base):
    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
    trigger_type: Mapped[NotificationTriggerType] = mapped_column(
        sa.Enum(
            NotificationTriggerType,
            name="notification_trigger_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    trigger_edge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("edge.id")
    )
    trigger_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id")
    )
    trigger_jurisdiction: Mapped[str | None]
    may_process: Mapped[bool | None]
    may_index_fulltext: Mapped[bool | None]
    may_cite_passages: Mapped[bool | None]
    may_export_free: Mapped[bool | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "account_id", "work_id", "trigger_type", "trigger_edge_id",
            name="uq_notification_account_work_trigger_edge",
        ),
        # The retention cleanup (delete_read_before) filters on created_at,
        # via the cleanup-notifications command. Matches the index the
        # 0030 migration already creates -- this just keeps the ORM's own
        # metadata in agreement with it so a future autogenerate diff
        # doesn't propose dropping it. Same pattern as
        # RateLimitBucketORM.__table_args__'s ix_rate_limit_bucket_window_start.
        sa.Index("ix_notification_created_at", "created_at"),
    )


class RightsNotificationBaselineORM(Base):
    __tablename__ = "rights_notification_baseline"

    # Pure internal bookkeeping for the notify-watchers RIGHTS_CHANGE
    # detector: the last-known rights state an account's watch has already
    # been diffed against, keyed by the same tuple that identifies a
    # RIGHTS_CHANGE notification. Deliberately NOT the Notification table --
    # a row here is never shown to a user, never emailed, and never joined
    # into anything user-facing. Same upsert-via-merge shape as
    # RightsClassificationORM: one row per key tuple, no separate surrogate
    # id.
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True
    )
    trigger_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), primary_key=True
    )
    trigger_jurisdiction: Mapped[str] = mapped_column(primary_key=True)
    may_process: Mapped[bool]
    may_index_fulltext: Mapped[bool]
    may_cite_passages: Mapped[bool]
    may_export_free: Mapped[bool]
    # SQLAlchemy's session.merge() + flush() only emits an UPDATE when at
    # least one column value actually differs from what's stored -- if every
    # merged value equals the existing row, no UPDATE runs and onupdate never
    # fires. So this reflects "the last time the rights values actually
    # changed", not "the last time upsert_baseline was called". Both current
    # callers in notifications/detection.py already rely on that: one path is
    # a first-time insert, the other only calls upsert_baseline after a real
    # difference was detected.
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )


class NotifiedEdgeORM(Base):
    __tablename__ = "notified_edge"

    # Pure internal bookkeeping for the notify-watchers NEW_EDITION/
    # NATIONAL_ADOPTION dedup check: has this edge already produced a
    # notification for this account/work? Deliberately NOT the Notification
    # table -- a row here is never shown to a user, never emailed, and
    # never joined into anything user-facing, so cleanup-notifications'
    # deletion of read Notification rows can never cause notify-watchers to
    # treat an already-seen edge as new again. Same shape as
    # RightsNotificationBaselineORM, but keyed by edge instead of by
    # document/jurisdiction, and covering the two edge-triggered types
    # instead of RIGHTS_CHANGE.
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True
    )
    trigger_type: Mapped[NotificationTriggerType] = mapped_column(
        sa.Enum(
            NotificationTriggerType,
            name="notification_trigger_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        primary_key=True,
    )
    trigger_edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("edge.id"), primary_key=True
    )
    notified_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class ChatSessionORM(Base):
    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_token: Mapped[str]
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=True
    )
    jurisdiction: Mapped[str]
    language: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("session_token", name="uq_chat_session_token"),
    )


class ChatMessageORM(Base):
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("chat_session.id"), nullable=False
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        sa.Enum(
            ChatMessageRole, name="chat_message_role", native_enum=False,
            values_callable=_enum_values, create_constraint=True,
        )
    )
    content: Mapped[str]
    answer_type: Mapped[ChatAnswerType | None] = mapped_column(
        sa.Enum(
            ChatAnswerType, name="chat_answer_type", native_enum=False,
            values_callable=_enum_values, create_constraint=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class ChatMessageCitationORM(Base):
    __tablename__ = "chat_message_citation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("chat_message.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("segment.id"), nullable=True
    )


class RateLimitBucketORM(Base):
    __tablename__ = "rate_limit_bucket"

    key: Mapped[str] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), primary_key=True
    )
    request_count: Mapped[int] = mapped_column(default=0)

    # The retention cleanup (delete_buckets_before) filters purely on
    # window_start and runs on every request; without this index that
    # filter forces a full table scan each time.
    __table_args__ = (sa.Index("ix_rate_limit_bucket_window_start", "window_start"),)
