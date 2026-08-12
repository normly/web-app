# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create source table

Revision ID: 0001
Revises: 27683efa072a
Create Date: 2026-08-11

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = "27683efa072a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("publisher", sa.String, nullable=False),
        sa.Column("retrieval_path", sa.String, nullable=False),
        sa.Column(
            "legal_basis_category",
            sa.Enum("A", "B", "C", "D", name="legal_basis_category", native_enum=False),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String, nullable=False),
        sa.Column("reviewed_at", sa.Date, nullable=False),
        sa.Column("responsible_person", sa.String, nullable=False),
        sa.Column(
            "commercial_catalog", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("contract_reference", sa.String, nullable=True),
        sa.Column("tdm_opt_out_checked_at", sa.Date, nullable=True),
        sa.Column(
            "tdm_opt_out_result",
            sa.Enum(
                "none_found",
                "opt_out_present",
                name="tdm_opt_out_result",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "NOT (legal_basis_category = 'D' AND commercial_catalog)",
            name="ck_source_no_category_d_commercial_catalog",
        ),
        sa.CheckConstraint(
            "legal_basis_category != 'C' OR contract_reference IS NOT NULL",
            name="ck_source_category_c_requires_contract",
        ),
    )


def downgrade() -> None:
    op.drop_table("source")
