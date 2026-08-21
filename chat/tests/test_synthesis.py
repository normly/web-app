# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_chat.synthesis import build_synthesis_answer


class _FakeSegment:
    def __init__(self, id, document_id, text):
        self.id = id
        self.document_id = document_id
        self.text = text


class _FakeSegmentRepo:
    def __init__(self, segments):
        self._segments = segments

    def find_similar_segments_for_jurisdiction(self, vector, jurisdiction, model_name, limit=5):
        return self._segments


class _FakeEmbeddingModel:
    def embed_query(self, text):
        return [0.1] * 1024


class _FakeOllamaClient:
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return self._response


def test_no_segments_returns_a_fallback_without_calling_ollama():
    result = build_synthesis_answer(
        "Frage ohne Treffer", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([]), _FakeOllamaClient("sollte nie aufgerufen werden"),
    )
    assert result.is_fallback is True
    assert result.ollama_calls == 0


def test_a_normal_paraphrase_is_accepted():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")
    ollama = _FakeOllamaClient("Beim Schweißen muss eine Schutzbrille getragen werden.")
    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is False
    assert result.citations == [{"document_id": segment.document_id, "segment_id": segment.id}]


def test_a_verbatim_repeating_answer_is_rejected():
    long_text = " ".join(f"wort{i}" for i in range(20))
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), long_text)
    ollama = _FakeOllamaClient(long_text)  # repeats the segment verbatim
    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is True
