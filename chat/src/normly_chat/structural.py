# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from normly_chat.classify import QuestionType, extract_designation

_FALLBACK_TEXT = {
    "de": "Dazu kann ich anhand des Referenzgraphen keine belastbare Aussage treffen.",
    "en": "I cannot give a reliable answer to that from the reference graph.",
}

# api/'s validity endpoint reports one of "valid" / "replaced" / "withdrawn".
# Those raw values are an API contract, not user-facing prose -- they get a
# natural phrase per language here rather than being interpolated verbatim
# into a German sentence.
_STATUS_PHRASE = {
    "de": {
        "valid": "ist noch gültig",
        "replaced": "wurde ersetzt",
        "withdrawn": "wurde zurückgezogen",
    },
    "en": {
        "valid": "is still valid",
        "replaced": "has been replaced",
        "withdrawn": "has been withdrawn",
    },
}
_UNKNOWN_STATUS_PHRASE = {
    "de": "hat einen unbekannten Gültigkeitsstatus",
    "en": "has an unknown validity status",
}

# Same for EdgeType's raw values ("references", "based_on_law", ...).
_EDGE_PHRASE = {
    "de": {
        "references": "verweist auf",
        "replaces": "ersetzt",
        "withdrawn_by": "wurde zurückgezogen durch",
        "based_on_law": "beruht auf",
        "adopted_from": "wurde übernommen von",
    },
    "en": {
        "references": "references",
        "replaces": "replaces",
        "withdrawn_by": "was withdrawn by",
        "based_on_law": "is based on",
        "adopted_from": "was adopted from",
    },
}
_UNKNOWN_EDGE_PHRASE = {
    "de": "steht in Beziehung zu",
    "en": "is related to",
}

_REPLACED_BY_SENTENCE = {
    "de": "{designation} wurde ersetzt durch: {targets}.",
    "en": "{designation} has been replaced by: {targets}.",
}
_WITHDRAWN_BY_SENTENCE = {
    "de": "{designation} wurde zurückgezogen durch: {reference}.",
    "en": "{designation} has been withdrawn by: {reference}.",
}


@dataclass(frozen=True)
class StructuralAnswer:
    text: str
    citations: list[dict] = field(default_factory=list)
    is_fallback: bool = False


def _fallback(language: str) -> StructuralAnswer:
    return StructuralAnswer(text=_FALLBACK_TEXT[language], citations=[], is_fallback=True)


def build_structural_answer(
    question_type: QuestionType, message: str, jurisdiction: str, language: str, api_client,
) -> StructuralAnswer:
    found = extract_designation(message)
    if found is None:
        return _fallback(language)
    issuer, designation = found

    document = api_client.search_document(issuer, designation, jurisdiction)
    if document is None:
        return _fallback(language)

    # The API speaks JSON, so ids arrive as strings; ChatMessageCitation and
    # CitationResponse both declare uuid.UUID, so the conversion belongs here
    # rather than at each consumer.
    document_id = uuid.UUID(document["id"])
    citations = [{"document_id": document_id, "segment_id": None}]

    if question_type == QuestionType.STRUCTURAL_VALIDITY:
        validity = api_client.get_validity(document_id, jurisdiction)
        if validity is None:
            return _fallback(language)
        status = validity.get("status")
        phrase = _STATUS_PHRASE[language].get(status, _UNKNOWN_STATUS_PHRASE[language])
        return StructuralAnswer(text=f"{designation} {phrase}.", citations=citations)

    # A replacement question ("Was ersetzt DIN EN ISO 9001?") asks about the
    # OLD document, but REPLACES/WITHDRAWN_BY edges point FROM the successor TO
    # it -- so the outgoing-edge listing get_edges() returns is empty for
    # exactly the document the question names. The validity endpoint already
    # resolves that direction correctly (it queries incoming edges), so its
    # replaced_by / withdrawn_reference fields are the direction-safe source
    # for this question shape. Outgoing edges (genuine REFERENCES-style ones)
    # point the same way the question does and are still reported alongside.
    validity = api_client.get_validity(document_id, jurisdiction)
    edges = api_client.get_edges(document_id, jurisdiction)

    sentences: list[str] = []
    if validity is not None:
        replaced_by = validity.get("replaced_by") or []
        if replaced_by:
            sentences.append(
                _REPLACED_BY_SENTENCE[language].format(
                    designation=designation,
                    targets=", ".join(str(target) for target in replaced_by),
                )
            )
        withdrawn_reference = validity.get("withdrawn_reference")
        if withdrawn_reference:
            sentences.append(
                _WITHDRAWN_BY_SENTENCE[language].format(
                    designation=designation, reference=withdrawn_reference,
                )
            )

    for edge in edges or []:
        phrase = _EDGE_PHRASE[language].get(
            edge.get("edge_type"), _UNKNOWN_EDGE_PHRASE[language]
        )
        sentences.append(f"{designation} {phrase}: {edge['to_document_id']}.")

    if not sentences:
        return _fallback(language)
    return StructuralAnswer(text=" ".join(sentences), citations=citations)
