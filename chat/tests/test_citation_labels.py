# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import pytest

from normly_chat.citation_labels import CitationResolver, document_label, section_from_heading


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("4.5.4 Performance Level", "4.5.4"),
        ("4.5.4. Performance Level", "4.5.4"),
        ("5 Anforderungen", "5"),
        ("§ 1 Geltungsbereich", "§ 1"),
        ("§ 12a Übergangsvorschrift", "§ 12a"),
        ("Anhang A", None),
        ("Vorwort", None),
        ("", None),
        (None, None),
    ],
)
def test_section_from_heading(heading, expected):
    assert section_from_heading(heading) == expected


def test_document_label_prefers_the_primary_designation():
    document = {
        "origin_issuer": "ISO", "origin_number": "13849-1",
        "designations": [
            {"designation": "BS EN ISO 13849-1", "is_primary": False},
            {"designation": "DIN EN ISO 13849-1", "is_primary": True},
        ],
    }
    assert document_label(document) == "DIN EN ISO 13849-1"


def test_document_label_falls_back_to_any_designation_then_to_the_origin():
    assert document_label({
        "origin_issuer": "ISO", "origin_number": "1",
        "designations": [{"designation": "EN 1", "is_primary": False}],
    }) == "EN 1"
    assert document_label(
        {"origin_issuer": "ISO", "origin_number": "9001", "designations": []}
    ) == "ISO 9001"


class _FakeApiClient:
    def __init__(self, documents):
        self._documents = documents
        self.calls = []

    def get_document(self, document_id, jurisdiction):
        self.calls.append((document_id, jurisdiction))
        return self._documents.get(document_id)


class _FakeSegmentRepo:
    def __init__(self, headings):
        self._headings = headings
        self.calls = []

    def list_segment_headings_for_jurisdiction(self, segment_ids, jurisdiction):
        self.calls.append((list(segment_ids), jurisdiction))
        return {s: self._headings[s] for s in segment_ids if s in self._headings}


def test_resolve_adds_labels_fetches_each_document_once_and_drops_unknown_documents():
    known, unknown = uuid.uuid4(), uuid.uuid4()
    segment = uuid.uuid4()
    api_client = _FakeApiClient({
        known: {
            "origin_issuer": "DGUV", "origin_number": "Vorschrift 1",
            "designations": [{"designation": "DGUV Vorschrift 1", "is_primary": True}],
        },
    })
    segment_repo = _FakeSegmentRepo({segment: "§ 2 Pflichten des Unternehmers"})
    resolver = CitationResolver(api_client, segment_repo, "DE")

    resolved = resolver.resolve([
        {"document_id": known, "segment_id": segment, "paragraph_index": 0},
        {"document_id": known, "segment_id": None, "paragraph_index": None},
        {"document_id": unknown, "segment_id": None, "paragraph_index": 1},
    ])

    assert resolved == [
        {"document_id": known, "segment_id": segment, "paragraph_index": 0,
         "designation": "DGUV Vorschrift 1", "section": "§ 2"},
        {"document_id": known, "segment_id": None, "paragraph_index": None,
         "designation": "DGUV Vorschrift 1", "section": None},
    ]
    assert api_client.calls == [(known, "DE"), (unknown, "DE")]
    assert segment_repo.calls == [([segment], "DE")]


def test_resolve_without_segments_does_not_query_headings():
    document_id = uuid.uuid4()
    segment_repo = _FakeSegmentRepo({})
    resolver = CitationResolver(
        _FakeApiClient({document_id: {
            "origin_issuer": "ISO", "origin_number": "1", "designations": [],
        }}),
        segment_repo, "DE",
    )

    resolver.resolve([{"document_id": document_id, "segment_id": None, "paragraph_index": 0}])

    assert segment_repo.calls == []


def test_label_returns_none_for_an_unknown_document():
    resolver = CitationResolver(_FakeApiClient({}), _FakeSegmentRepo({}), "DE")
    assert resolver.label(uuid.uuid4()) is None
