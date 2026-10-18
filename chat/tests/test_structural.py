# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_chat.citation_labels import CitationResolver
from normly_chat.classify import QuestionType
from normly_chat.structural import build_structural_answer


class _FakeApiClient:
    def __init__(self, *, document=None, validity=None, edges=None, documents=None):
        self._document = document
        self._validity = validity
        self._edges = edges
        self._documents = documents or {}
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

    def get_document(self, document_id, jurisdiction):
        return self._documents.get(document_id)


class _NoSegments:
    def list_segment_headings_for_jurisdiction(self, segment_ids, jurisdiction):
        return {}


def _answer(question_type, message, language, api_client):
    labels = CitationResolver(api_client, _NoSegments(), "DE")
    return build_structural_answer(question_type, message, "DE", language, api_client, labels)


def _doc(designation):
    return {
        "origin_issuer": "X", "origin_number": "0",
        "designations": [{"designation": designation, "is_primary": True}],
    }


def test_no_designation_found_returns_a_fallback():
    api_client = _FakeApiClient()
    result = _answer(QuestionType.STRUCTURAL_VALIDITY, "Wie sicher sind Werkstätten?", "de", api_client)
    assert result.is_fallback is True
    assert api_client.calls == []


def test_document_not_found_returns_a_fallback():
    api_client = _FakeApiClient(document=None)
    result = _answer(QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "de", api_client)
    assert result.is_fallback is True
    assert api_client.calls == [("search_document", "DIN", "DIN EN ISO 9001", "DE")]


def test_validity_question_composes_an_answer_from_the_validity_endpoint():
    document = {"id": "11111111-1111-1111-1111-111111111111"}
    api_client = _FakeApiClient(document=document, validity={"status": "valid"})
    result = _answer(QuestionType.STRUCTURAL_VALIDITY, "Ist DIN EN ISO 9001 noch gültig?", "de", api_client)
    assert result.is_fallback is False
    # The raw API status value ("valid") never reaches the user-facing
    # sentence; it is rendered as German prose instead.
    assert result.text == "DIN EN ISO 9001 ist noch gültig."
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None, "paragraph_index": 0},
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
        documents={uuid.UUID("33333333-3333-3333-3333-333333333333"): _doc("DIN EN ISO 12100")},
    )
    result = _answer(QuestionType.STRUCTURAL_REFERENCE, "Worauf verweist DIN EN ISO 9001?", "de", api_client)
    assert result.is_fallback is False
    assert "verweist auf" in result.text
    assert result.paragraphs == ["DIN EN ISO 9001 verweist auf: DIN EN ISO 12100."]
    assert "DIN EN ISO 12100" in result.text
    assert "33333333-3333-3333-3333-333333333333" not in result.text
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
         "segment_id": None, "paragraph_index": 0},
    ]


def test_reference_question_with_no_edges_and_no_validity_data_returns_a_fallback():
    document = {"id": "44444444-4444-4444-4444-444444444444"}
    api_client = _FakeApiClient(
        document=document,
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=[],
    )
    result = _answer(QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "de", api_client)
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
        documents={uuid.UUID(successor_id): _doc("DIN EN ISO 9001:2015")},
    )
    result = _answer(QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "de", api_client)
    assert result.is_fallback is False
    assert "ersetzt" in result.text
    assert "DIN EN ISO 9001:2015" in result.text
    assert successor_id not in result.text
    assert result.citations == [
        {"document_id": uuid.UUID(document["id"]), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(successor_id), "segment_id": None, "paragraph_index": 0},
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
        documents={uuid.UUID(notice_id): _doc("DIN-Mitteilungen 2015-09")},
    )
    result = _answer(QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "de", api_client)
    assert result.is_fallback is False
    assert "zurückgezogen" in result.text
    assert "DIN-Mitteilungen 2015-09" in result.text
    assert notice_id not in result.text


def test_an_english_validity_request_produces_english_text():
    document = {"id": "99999999-9999-9999-9999-999999999999"}
    api_client = _FakeApiClient(document=document, validity={"status": "replaced"})
    result = _answer(QuestionType.STRUCTURAL_VALIDITY, "Is DIN EN ISO 9001 still valid?", "en", api_client)
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
        documents={
            uuid.UUID(successor_id): _doc("DIN EN ISO 9001:2015"),
            uuid.UUID(target_id): _doc("DIN EN ISO 12100"),
        },
    )
    result = _answer(QuestionType.STRUCTURAL_REFERENCE, "What replaces DIN EN ISO 9001?", "en", api_client)
    assert result.is_fallback is False
    assert result.paragraphs == [
        "DIN EN ISO 9001 has been replaced by: DIN EN ISO 9001:2015.",
        "DIN EN ISO 9001 references: DIN EN ISO 12100.",
    ]
    assert successor_id not in result.text and target_id not in result.text
    # No German prose leaked into an English answer.
    assert "ersetzt" not in result.text and "verweist" not in result.text


def test_an_english_fallback_is_in_english():
    api_client = _FakeApiClient()
    result = _answer(QuestionType.STRUCTURAL_VALIDITY, "How safe are workshops?", "en", api_client)
    assert result.is_fallback is True
    assert result.text.startswith("I cannot")


SOURCE = "22222222-2222-2222-2222-222222222222"
TARGET = "33333333-3333-3333-3333-333333333333"
SUCCESSOR = "44444444-4444-4444-4444-444444444444"
WITHDRAWER = "55555555-5555-5555-5555-555555555555"


def test_successor_and_withdrawal_are_named_in_english():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "replaced", "replaced_by": [SUCCESSOR],
                  "withdrawn_reference": WITHDRAWER},
        edges=[],
        documents={
            uuid.UUID(SUCCESSOR): _doc("DIN EN ISO 9001:2015"),
            uuid.UUID(WITHDRAWER): _doc("DIN-Mitteilungen 2015-09"),
        },
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "What replaces DIN EN ISO 9001?", "en", api_client,
    )

    assert result.paragraphs == [
        "DIN EN ISO 9001 has been replaced by: DIN EN ISO 9001:2015.",
        "DIN EN ISO 9001 has been withdrawn by: DIN-Mitteilungen 2015-09.",
    ]
    assert result.citations == [
        {"document_id": uuid.UUID(SOURCE), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(SUCCESSOR), "segment_id": None, "paragraph_index": 0},
        {"document_id": uuid.UUID(SOURCE), "segment_id": None, "paragraph_index": 1},
        {"document_id": uuid.UUID(WITHDRAWER), "segment_id": None, "paragraph_index": 1},
    ]


def test_an_unresolvable_target_drops_its_sentence_and_never_shows_an_id():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "valid", "replaced_by": [], "withdrawn_reference": None},
        edges=[
            {"edge_type": "references", "from_document_id": SOURCE,
             "to_document_id": TARGET, "jurisdiction": "DE", "layer": "free"},
            {"edge_type": "based_on_law", "from_document_id": SOURCE,
             "to_document_id": SUCCESSOR, "jurisdiction": "DE", "layer": "free"},
        ],
        documents={uuid.UUID(SUCCESSOR): _doc("ArbSchG")},
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "Worauf verweist DIN EN ISO 9001?", "de", api_client,
    )

    assert result.paragraphs == ["DIN EN ISO 9001 beruht auf: ArbSchG."]
    assert TARGET not in result.text


def test_only_unresolvable_targets_give_the_fallback():
    api_client = _FakeApiClient(
        document={"id": SOURCE},
        validity={"status": "replaced", "replaced_by": [SUCCESSOR], "withdrawn_reference": None},
        edges=[],
    )

    result = _answer(
        QuestionType.STRUCTURAL_REFERENCE, "Was ersetzt DIN EN ISO 9001?", "de", api_client,
    )

    assert result.is_fallback is True
    assert result.citations == []
