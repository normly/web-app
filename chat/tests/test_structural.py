# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

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
        QuestionType.STRUCTURAL_VALIDITY, "Wie sicher sind Werkstätten?", "DE", "de", api_client,
    )
    assert result.is_fallback is True
    assert api_client.calls == []


def test_document_not_found_returns_a_fallback():
    api_client = _FakeApiClient(document=None)
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "DE", "de",
        api_client,
    )
    assert result.is_fallback is True
    assert api_client.calls == [("search_document", "DIN", "DIN EN ISO 9001", "DE")]


def test_validity_question_composes_an_answer_from_the_validity_endpoint():
    document = {"id": "11111111-1111-1111-1111-111111111111"}
    api_client = _FakeApiClient(document=document, validity={"status": "valid"})
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "DE", "de",
        api_client,
    )
    assert result.is_fallback is False
    # The raw API status value ("valid") never reaches the user-facing
    # sentence; it is rendered as German prose instead.
    assert result.text == "DIN EN ISO 9001 ist noch gültig."
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None},
    ]


def test_reference_question_composes_an_answer_from_the_edges_endpoint():
    document = {"id": "22222222-2222-2222-2222-222222222222"}
    edges = [
        {
            "edge_type": "references", "from_document_id": document["id"],
            "to_document_id": "33333333-3333-3333-3333-333333333333",
            "jurisdiction": "DE", "layer": "free",
        },
    ]
    api_client = _FakeApiClient(
        document=document,
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=edges,
    )
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Worauf verweist DIN EN ISO 9001?", "DE", "de",
        api_client,
    )
    assert result.is_fallback is False
    assert "verweist auf" in result.text
    assert "33333333-3333-3333-3333-333333333333" in result.text
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None},
    ]


def test_reference_question_with_no_edges_and_no_validity_data_returns_a_fallback():
    document = {"id": "44444444-4444-4444-4444-444444444444"}
    api_client = _FakeApiClient(
        document=document,
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=[],
    )
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "DE", "de", api_client,
    )
    assert result.is_fallback is True


def test_replacement_question_answers_from_validity_when_no_outgoing_edges_exist():
    """
    REPLACES/WITHDRAWN_BY edges point FROM the successor TO the superseded
    document, so the superseded document's OUTGOING edges are empty -- which is
    exactly the document a "Was ersetzt X?" question names. Before the fix this
    always fell back even though the graph knew the answer; the validity
    endpoint reports the same relationship from the correct direction.
    """
    document = {"id": "55555555-5555-5555-5555-555555555555"}
    successor_id = "66666666-6666-6666-6666-666666666666"
    api_client = _FakeApiClient(
        document=document,
        validity={
            "status": "replaced", "replaced_by": [successor_id], "withdrawn_reference": None,
        },
        edges=[],
    )
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "DE", "de", api_client,
    )
    assert result.is_fallback is False
    assert "ersetzt" in result.text
    assert successor_id in result.text
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None},
    ]


def test_withdrawal_question_answers_from_the_withdrawn_reference():
    document = {"id": "77777777-7777-7777-7777-777777777777"}
    notice_id = "88888888-8888-8888-8888-888888888888"
    api_client = _FakeApiClient(
        document=document,
        validity={
            "status": "withdrawn", "replaced_by": [], "withdrawn_reference": notice_id,
        },
        edges=[],
    )
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "DE", "de", api_client,
    )
    assert result.is_fallback is False
    assert "zurückgezogen" in result.text
    assert notice_id in result.text


def test_an_english_validity_request_produces_english_text():
    document = {"id": "99999999-9999-9999-9999-999999999999"}
    api_client = _FakeApiClient(document=document, validity={"status": "replaced"})
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "Is DIN EN ISO 9001 still valid?", "DE", "en",
        api_client,
    )
    assert result.is_fallback is False
    assert result.text == "DIN EN ISO 9001 has been replaced."


def test_an_english_reference_request_produces_english_text():
    document = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
    successor_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    target_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    api_client = _FakeApiClient(
        document=document,
        validity={
            "status": "replaced", "replaced_by": [successor_id], "withdrawn_reference": None,
        },
        edges=[
            {
                "edge_type": "references", "from_document_id": document["id"],
                "to_document_id": target_id, "jurisdiction": "DE", "layer": "free",
            },
        ],
    )
    result = build_structural_answer(
        QuestionType.STRUCTURAL_REFERENCE, "What replaces DIN EN ISO 9001?", "DE", "en",
        api_client,
    )
    assert result.is_fallback is False
    assert f"DIN EN ISO 9001 has been replaced by: {successor_id}." in result.text
    assert f"DIN EN ISO 9001 references: {target_id}." in result.text
    # No German prose leaked into an English answer.
    assert "ersetzt" not in result.text and "verweist" not in result.text


def test_an_english_fallback_is_in_english():
    api_client = _FakeApiClient()
    result = build_structural_answer(
        QuestionType.STRUCTURAL_VALIDITY, "How safe are workshops?", "DE", "en", api_client,
    )
    assert result.is_fallback is True
    assert result.text.startswith("I cannot")
