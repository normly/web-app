# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""scope the designation unique constraint to the edition

A designation identifies one edition of a Regelwerk, not the Regelwerk as a
whole -- keyed on (issuer, designation) alone, a genuinely new edition
sharing its predecessor's exact designation string (e.g. a DGUV Vorschrift
reissued under the same "DGUV Vorschrift N" number) could never be recorded
as its own DocumentDesignation row, forcing identity resolution to treat it
as an update to the predecessor's own Document instead of a new edition.

The constraint is created with NULLS NOT DISTINCT: `edition` is nullable
(most deliveries don't carry an edition string), and a plain 3-column unique
constraint treats every NULL as distinct from every other NULL, which would
silently drop the "one designation, one node worldwide" guarantee for the
common case where edition is unset -- two different documents could then
both claim the same (issuer, designation) with edition=NULL. NULLS NOT
DISTINCT keeps NULL-edition designations colliding as before, while letting
rows with different known editions coexist.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-08
"""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_designation_issuer_designation", "document_designation", type_="unique")
    op.create_unique_constraint(
        "uq_designation_issuer_designation_edition",
        "document_designation",
        ["issuer", "designation", "edition"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_designation_issuer_designation_edition", "document_designation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_designation_issuer_designation", "document_designation", ["issuer", "designation"]
    )
