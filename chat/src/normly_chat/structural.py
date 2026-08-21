# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass, field

from normly_chat.classify import QuestionType, extract_designation

_FALLBACK_TEXT_DE = (
    "Dazu kann ich anhand des Referenzgraphen keine belastbare Aussage treffen."
)


@dataclass(frozen=True)
class StructuralAnswer:
    text: str
    citations: list[dict] = field(default_factory=list)
    is_fallback: bool = False


def _fallback() -> StructuralAnswer:
    return StructuralAnswer(text=_FALLBACK_TEXT_DE, citations=[], is_fallback=True)


def build_structural_answer(
    question_type: QuestionType, message: str, jurisdiction: str, api_client,
) -> StructuralAnswer:
    found = extract_designation(message)
    if found is None:
        return _fallback()
    issuer, designation = found

    document = api_client.search_document(issuer, designation, jurisdiction)
    if document is None:
        return _fallback()

    document_id = document["id"]
    citations = [{"document_id": document_id, "segment_id": None}]

    if question_type == QuestionType.STRUCTURAL_VALIDITY:
        validity = api_client.get_validity(document_id, jurisdiction)
        if validity is None:
            return _fallback()
        status = validity.get("status", "unbekannt")
        return StructuralAnswer(
            text=f"{designation} hat den Gültigkeitsstatus: {status}.",
            citations=citations,
        )

    edges = api_client.get_edges(document_id, jurisdiction)
    if not edges:
        return _fallback()
    lines = [f"{designation} steht in folgender Beziehung: {e['edge_type']}." for e in edges]
    return StructuralAnswer(text=" ".join(lines), citations=citations)
