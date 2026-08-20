# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""scope the segment unique constraint to the delivery

A segment belongs to the delivery that produced it. Keyed on
(document_id, sequence_number) alone, a second delivery re-ingesting the same
document — an amended text, say — would collide with the first delivery's
segment and silently keep the stale text, and revoking the first delivery would
delete a segment the second one believes it owns.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-20
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_segment_document_sequence", "segment", type_="unique")
    op.create_unique_constraint(
        "uq_segment_document_delivery_sequence",
        "segment",
        ["document_id", "delivery_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_segment_document_delivery_sequence", "segment", type_="unique"
    )
    op.create_unique_constraint(
        "uq_segment_document_sequence", "segment", ["document_id", "sequence_number"]
    )
