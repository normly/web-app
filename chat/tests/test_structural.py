# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.classify import QuestionType
from normly_chat.structural import build_structural_answer


class _FakeApiClient:
    def __init__(self, *, document=None, validity=None, edges=None):
        self._document = document
        self._validity = validity
        self._edges = edges
        self.calls = []

    def search_document(self, issuer, designation, jurisdiction):
        self.calls.append(("search_document", issuer, designation, jurisdiction))
        return self._document

    def get_validity(self, document_id, jurisdiction):
        self.calls.append(("get_validity", document_id, jurisdiction))
        return self._validity

    def get_edges(self, document_id, jurisdiction):
        self.calls.append(("get_edges", document_id, jurisdiction))
        return self._edges


def test_no_designation_found_returns_a_fallback():
    api_client = _FakeApiClient()
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Wie sicher sind Werkstätten?", "DE", api_client,
    )
    assert result.is_fallback is True
    assert api_client.calls == []


def test_document_not_found_returns_a_fallback():
    api_client = _FakeApiClient(document=None)
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "DE", api_client,
    )
    assert result.is_fallback is True
    assert api_client.calls == [("search_document", "DIN", "DIN EN ISO 9001", "DE")]


def test_validity_question_composes_an_answer_from_the_validity_endpoint():
    document = {"id": "11111111-1111-1111-1111-111111111111"}
    api_client = _FakeApiClient(document=document, validity={"status": "valid"})
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "DE", api_client,
    )
    assert result.is_fallback is False
    assert "gültig" in result.text.lower() or "valid" in result.text.lower()
    assert result.citations == [{"document_id": document["id"], "segment_id": None}]


def test_reference_question_composes_an_answer_from_the_edges_endpoint():
    document = {"id": "22222222-2222-2222-2222-222222222222"}
    edges = [
        {
            "edge_type": "replaces", "from_document_id": document["id"],
            "to_document_id": "33333333-3333-3333-3333-333333333333",
            "jurisdiction": "DE", "layer": "free",
        },
    ]
    api_client = _FakeApiClient(document=document, edges=edges)
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "DE", api_client,
    )
    assert result.is_fallback is False
    assert result.citations == [{"document_id": document["id"], "segment_id": None}]


def test_reference_question_with_no_edges_returns_a_fallback():
    document = {"id": "44444444-4444-4444-4444-444444444444"}
    api_client = _FakeApiClient(document=document, edges=[])
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "DE", api_client,
    )
    assert result.is_fallback is True
