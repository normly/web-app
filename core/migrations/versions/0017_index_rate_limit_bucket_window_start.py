# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""index rate_limit_bucket.window_start

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-29

The retention cleanup (delete_buckets_before) filters purely on window_start
and runs on every request; without an index it forces a full table scan
each time, found and deferred as a known Minor issue during the
reference-graph-search-and-browse final review.
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_rate_limit_bucket_window_start", "rate_limit_bucket", ["window_start"]
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_bucket_window_start", table_name="rate_limit_bucket")
