# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create account, account_session, account_google_identity, account_token tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("password_hash", sa.String, nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_account_email"),
    )
    op.create_table(
        "account_session",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("session_token", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_token", name="uq_account_session_token"),
    )
    op.create_index(
        "ix_account_session_account_id", "account_session", ["account_id"]
    )
    op.create_table(
        "account_google_identity",
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True
        ),
        sa.Column("google_subject_id", sa.String, nullable=False),
        sa.UniqueConstraint(
            "google_subject_id", name="uq_account_google_identity_subject"
        ),
    )
    op.create_table(
        "account_token",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column(
            "purpose",
            sa.Enum(
                "password_reset", "email_verification", "magic_link",
                name="account_token_purpose", native_enum=False, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("token", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_account_token_token"),
    )
    op.create_index("ix_account_token_account_id", "account_token", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_account_token_account_id", table_name="account_token")
    op.drop_table("account_token")
    op.drop_table("account_google_identity")
    op.drop_index("ix_account_session_account_id", table_name="account_session")
    op.drop_table("account_session")
    op.drop_table("account")
