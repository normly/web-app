# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add case_type and work-merge fields to identity_resolution_case

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "identity_resolution_case",
        sa.Column(
            "case_type",
            sa.Enum(
                "new_document", "work_merge",
                name="identity_resolution_case_type", native_enum=False, create_constraint=True,
            ),
            nullable=False,
            server_default="new_document",
        ),
    )
    # raw_designation is meaningless for a work_merge case (there is no raw
    # ingested string to show) -- loosened rather than filled with a
    # placeholder string a reviewer might mistake for real ingestion data.
    op.alter_column("identity_resolution_case", "raw_designation", nullable=True)
    op.add_column(
        "identity_resolution_case",
        sa.Column("source_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )
    op.add_column(
        "identity_resolution_case",
        sa.Column("target_work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("identity_resolution_case", "target_work_id")
    op.drop_column("identity_resolution_case", "source_work_id")
    op.execute(
        "UPDATE identity_resolution_case SET raw_designation = '' WHERE raw_designation IS NULL"
    )
    op.alter_column("identity_resolution_case", "raw_designation", nullable=False)
    op.drop_column("identity_resolution_case", "case_type")
