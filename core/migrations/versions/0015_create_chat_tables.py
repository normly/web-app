# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create chat_session, chat_message, chat_message_citation

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_ROLE_VALUES = ("user", "assistant")
_ANSWER_TYPE_VALUES = ("structural", "synthesis", "fallback")


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_token", sa.String, nullable=False),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id"), nullable=True,
        ),
        sa.Column("jurisdiction", sa.String, nullable=False),
        sa.Column("language", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("session_token", name="uq_chat_session_token"),
    )

    op.create_table(
        "chat_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_session.id"), nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum(
                *_ROLE_VALUES, name="chat_message_role", native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "answer_type",
            sa.Enum(
                *_ANSWER_TYPE_VALUES, name="chat_answer_type", native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_message_session_id", "chat_message", ["session_id"])

    op.create_table(
        "chat_message_citation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_message.id"), nullable=False,
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document.id"), nullable=False,
        ),
        sa.Column(
            "segment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segment.id"), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_message_citation")
    op.drop_index("ix_chat_message_session_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_table("chat_session")
