# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from normly_core.graph.domain import DocumentDesignation, DocumentTitle


def build_document_embedding_text(
    designations: list[DocumentDesignation], titles: list[DocumentTitle]
) -> str | None:
    """
    "<primary designation> — <first title>" for the search embedding, or just
    the designation if no title exists yet, or None if there is no primary
    designation to embed at all (nothing indexed until one exists).

    DocumentTitle has no `is_primary` flag (unlike DocumentDesignation) --
    the first title in insertion order wins. Deliberate simplification:
    multi-title documents are rare today, and a real "best title" concept is
    not something this sub-project introduces.
    """
    primary_designation = next((d for d in designations if d.is_primary), None)
    if primary_designation is None:
        return None
    if not titles:
        return primary_designation.designation
    return f"{primary_designation.designation} — {titles[0].title}"
