# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Labels for citation chips: which norm, which section.

Labels are derived on every read, never stored, so a reopened chat shows the
current state of the knowledge base instead of a stale snapshot.
"""

from __future__ import annotations

import re
import uuid

# "4.5.4 Performance Level" -> "4.5.4", "§ 1 Geltungsbereich" -> "§ 1".
# A trailing dot after a number ("4.5.4. Title") is not part of the section.
_SECTION_PATTERN = re.compile(r"^\s*(§\s*\d+[a-z]?|\d+(?:\.\d+)*)\.?(?=\s|$)")


def section_from_heading(heading: str | None) -> str | None:
    if not heading:
        return None
    match = _SECTION_PATTERN.match(heading)
    return match.group(1) if match else None


def document_label(document: dict) -> str:
    designations = document.get("designations") or []
    for designation in designations:
        if designation.get("is_primary"):
            return designation["designation"]
    if designations:
        return designations[0]["designation"]
    return f"{document['origin_issuer']} {document['origin_number']}"


class CitationResolver:
    """
    Resolves chip labels for one jurisdiction, fetching each document from
    api/ at most once. A document api/ does not return (not visible, retired)
    yields no label, and its citations are dropped.
    """

    def __init__(self, api_client, segment_repo, jurisdiction: str):
        self._api_client = api_client
        self._segment_repo = segment_repo
        self._jurisdiction = jurisdiction
        self._documents: dict[uuid.UUID, dict | None] = {}

    def label(self, document_id: uuid.UUID) -> str | None:
        if document_id not in self._documents:
            self._documents[document_id] = self._api_client.get_document(
                document_id, self._jurisdiction
            )
        document = self._documents[document_id]
        return document_label(document) if document is not None else None

    def resolve(self, citations: list[dict]) -> list[dict]:
        segment_ids = [c["segment_id"] for c in citations if c.get("segment_id") is not None]
        headings = (
            self._segment_repo.list_segment_headings_for_jurisdiction(
                segment_ids, self._jurisdiction
            )
            if segment_ids else {}
        )
        resolved = []
        for citation in citations:
            label = self.label(citation["document_id"])
            if label is None:
                continue
            resolved.append({
                **citation,
                "designation": label,
                "section": section_from_heading(headings.get(citation.get("segment_id"))),
            })
        return resolved
