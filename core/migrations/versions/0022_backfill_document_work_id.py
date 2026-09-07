# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""backfill document.work_id via union-find over replaces/withdrawn_by/adopted_from edges

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-06
"""

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_WORK_LINKING_EDGE_TYPES = ("replaces", "withdrawn_by", "adopted_from")

document_table = sa.table(
    "document", sa.column("id", UUID(as_uuid=True)), sa.column("work_id", UUID(as_uuid=True))
)
edge_table = sa.table(
    "edge",
    sa.column("from_document_id", UUID(as_uuid=True)),
    sa.column("to_document_id", UUID(as_uuid=True)),
    sa.column("edge_type", sa.String),
)
work_table = sa.table(
    "work",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("status", sa.String),
    sa.column("created_via", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    connection = op.get_bind()

    # Idempotency guard: only documents still missing a work_id are grouped.
    # A second run of this migration finds nothing left to do and changes
    # nothing.
    unassigned_ids = [
        row.id
        for row in connection.execute(
            sa.select(document_table.c.id).where(document_table.c.work_id.is_(None))
        )
    ]
    if not unassigned_ids:
        return

    parent: dict[uuid.UUID, uuid.UUID] = {doc_id: doc_id for doc_id in unassigned_ids}

    def find(x: uuid.UUID) -> uuid.UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: uuid.UUID, b: uuid.UUID) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # One-time whole-graph traversal for this backfill only -- not a
    # pattern for application code, which stays at 1-3 hops per ADR-006.
    edges = connection.execute(
        sa.select(edge_table.c.from_document_id, edge_table.c.to_document_id).where(
            edge_table.c.edge_type.in_(_WORK_LINKING_EDGE_TYPES),
            edge_table.c.from_document_id.in_(unassigned_ids),
            edge_table.c.to_document_id.in_(unassigned_ids),
        )
    )
    for from_id, to_id in edges:
        union(from_id, to_id)

    groups: dict[uuid.UUID, list[uuid.UUID]] = {}
    for doc_id in unassigned_ids:
        groups.setdefault(find(doc_id), []).append(doc_id)

    now = datetime.now(timezone.utc)
    for members in groups.values():
        work_id = uuid.uuid4()
        connection.execute(
            work_table.insert().values(
                id=work_id, status="active", created_via="auto_matched", created_at=now,
            )
        )
        connection.execute(
            document_table.update()
            .where(document_table.c.id.in_(members))
            .values(work_id=work_id)
        )


def downgrade() -> None:
    # No data to reverse here: 0021's downgrade drops the work_id column and
    # 0020's downgrade drops the work table, which together undo everything
    # this migration wrote. Splitting the undo across those two migrations
    # (rather than deleting rows here first) avoids foreign-key ordering
    # hazards between this migration and whatever downstream rows may by
    # then reference a Work this backfill created.
    pass
