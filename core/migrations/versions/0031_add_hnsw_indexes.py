# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add HNSW indexes on document_embedding.vector and embedding.vector

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-10
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_document_embedding_vector_hnsw ON document_embedding "
        "USING hnsw (vector vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_embedding_vector_hnsw ON embedding "
        "USING hnsw (vector vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_embedding_vector_hnsw")
    op.execute("DROP INDEX ix_document_embedding_vector_hnsw")
