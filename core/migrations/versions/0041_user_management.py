# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""user management: roles, publishers, invitations, admin audit log

Exactly one role per account; a publisher account is bound to one publisher
(the contract partner). Invitations bind a role only when their link is used.
The audit log keeps IDs only and survives account deletion (issue #60).

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

_ROLES = "('user', 'publisher', 'administrator')"
_BLOCK_REASONS = "('bulk_retrieval', 'abuse', 'terms_violation', 'other')"
_ADMIN_ACTIONS = (
    "('invitation_created', 'invitation_resent', 'invitation_withdrawn', "
    "'invitation_accepted', 'role_changed', 'publisher_changed', 'account_blocked', "
    "'account_unblocked', 'account_removed', 'publisher_created', "
    "'administrator_granted_cli')"
)


def upgrade() -> None:
    op.create_table(
        "publisher",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_publisher_name_lower", "publisher", [sa.text("lower(name)")], unique=True
    )

    op.add_column(
        "account",
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
    )
    op.add_column(
        "account",
        sa.Column(
            "publisher_id", UUID(as_uuid=True),
            sa.ForeignKey("publisher.id", name="fk_account_publisher_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("account", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("account", sa.Column("block_reason", sa.String(20), nullable=True))
    op.create_check_constraint("ck_account_role", "account", f"role IN {_ROLES}")
    op.create_check_constraint(
        "ck_account_block_reason", "account", f"block_reason IN {_BLOCK_REASONS}"
    )
    op.create_check_constraint(
        "ck_account_publisher_binding", "account",
        "(role = 'publisher') = (publisher_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_account_block", "account", "(blocked_at IS NULL) = (block_reason IS NULL)"
    )

    op.create_table(
        "account_invitation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "publisher_id", UUID(as_uuid=True),
            sa.ForeignKey("publisher.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("token", sa.String, nullable=False),
        sa.Column(
            "invited_by", UUID(as_uuid=True),
            sa.ForeignKey("account.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token", name="uq_account_invitation_token"),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_account_invitation_role"),
        sa.CheckConstraint("locale IN ('de', 'en')", name="ck_account_invitation_locale"),
        sa.CheckConstraint(
            "(role = 'publisher') = (publisher_id IS NOT NULL)",
            name="ck_account_invitation_publisher_binding",
        ),
    )
    op.create_index(
        "uq_account_invitation_email_lower", "account_invitation",
        [sa.text("lower(email)")], unique=True,
    )
    op.create_index("ix_account_invitation_expires_at", "account_invitation", ["expires_at"])

    op.create_table(
        "admin_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        # No foreign keys: entries must outlive the accounts they name.
        sa.Column("actor_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_invitation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_publisher_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(f"action IN {_ADMIN_ACTIONS}", name="ck_admin_audit_log_action"),
    )
    op.create_index("ix_admin_audit_log_occurred_at", "admin_audit_log", ["occurred_at"])
    op.create_index(
        "ix_admin_audit_log_target_account_id", "admin_audit_log", ["target_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_target_account_id", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_occurred_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_index("ix_account_invitation_expires_at", table_name="account_invitation")
    op.drop_index("uq_account_invitation_email_lower", table_name="account_invitation")
    op.drop_table("account_invitation")
    op.drop_constraint("ck_account_block", "account", type_="check")
    op.drop_constraint("ck_account_publisher_binding", "account", type_="check")
    op.drop_constraint("ck_account_block_reason", "account", type_="check")
    op.drop_constraint("ck_account_role", "account", type_="check")
    op.drop_column("account", "block_reason")
    op.drop_column("account", "blocked_at")
    op.drop_column("account", "publisher_id")
    op.drop_column("account", "role")
    op.drop_index("uq_publisher_name_lower", table_name="publisher")
    op.drop_table("publisher")
