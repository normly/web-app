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

    class _TwoCallOllama:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return "Beim Schweißen muss eine Schutzbrille getragen werden."
            return "ja"

    ollama = _TwoCallOllama()
    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is False
    assert result.citations == [
        {"document_id": segment.document_id, "segment_id": segment.id, "paragraph_index": None},
    ]


def test_a_verbatim_repeating_answer_is_rejected():
    long_text = " ".join(f"wort{i}" for i in range(20))
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), long_text)
    ollama = _FakeOllamaClient(long_text)  # repeats the segment verbatim
    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is True


def test_a_verbatim_answer_spanning_a_segment_boundary_is_rejected():
    # The LLM is shown the segments joined into one context block, so a
    # verbatim run copied across the join between segment A's tail and
    # segment B's head is just as much plagiarism as copying from a single
    # segment -- even though neither segment's own text contains the full
    # run on its own.
    document_id = uuid.uuid4()
    segment_a = _FakeSegment(
        uuid.uuid4(), document_id,
        "In deutschen Werkstätten gilt laut Vorschrift dass Schutzbrillen sind beim",
    )
    segment_b = _FakeSegment(
        uuid.uuid4(), document_id,
        "Schweißen stets Pflicht um die Augen zuverlässig vor Funkenflug zu schützen im Betrieb.",
    )
    straddling_answer = (
        "gilt laut Vorschrift dass Schutzbrillen sind beim "
        "Schweißen stets Pflicht um die Augen zuverlässig vor"
    )
    ollama = _FakeOllamaClient(straddling_answer)
    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment_a, segment_b]), ollama,
    )
    assert result.is_fallback is True


def test_an_unfaithful_answer_is_rejected_without_a_verbatim_match():
    # The Ollama fake needs to answer differently on its two calls: the first
    # is the actual synthesis generation, the second is the faithfulness
    # check being asked "is this answer supported by the context?".
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _TwoCallOllama:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return "Beim Schweißen muss außerdem ein Feuerlöscher mitgeführt werden."
            return "nein: der Feuerlöscher wird im Kontext nicht erwähnt"

    ollama = _TwoCallOllama()
    result = build_synthesis_answer(
        "Was ist beim Schweißen vorgeschrieben?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is True
    assert ollama.calls == 2
    assert result.ollama_calls == 2


def test_a_faithful_answer_still_passes_the_second_check():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _TwoCallOllama:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return "Beim Schweißen muss eine Schutzbrille getragen werden."
            return "ja"

    ollama = _TwoCallOllama()
    result = build_synthesis_answer(
        "Was ist beim Schweißen vorgeschrieben?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is False
    assert ollama.calls == 2


def test_faithfulness_check_is_skipped_after_a_verbatim_rejection():
    # A clear verbatim hit must not pay for a second, now-pointless model
    # call -- the answer is already rejected.
    long_text = " ".join(f"wort{i}" for i in range(20))
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), long_text)
    ollama = _FakeOllamaClient(long_text)
    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), ollama,
    )
    assert result.is_fallback is True
    assert ollama.calls == 1
    assert result.ollama_calls == 1


def _two_call_llm(answer):
    class _Llm:
        def __init__(self):
            self.calls = 0
            self.messages = []

        def chat(self, messages):
            self.calls += 1
            self.messages.append(messages)
            return answer if self.calls == 1 else "ja"

    return _Llm()


def test_markers_become_paragraph_citations_and_are_stripped():
    first = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")
    second = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Helfer tragen ebenfalls Schutzbrillen.")
    llm = _two_call_llm(
        "Beim Schweißen muss eine Schutzbrille getragen werden [1].\n\n"
        "Auch helfende Personen brauchen eine [2]."
    )

    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([first, second]), llm,
    )

    assert result.is_fallback is False
    assert result.paragraphs == [
        "Beim Schweißen muss eine Schutzbrille getragen werden.",
        "Auch helfende Personen brauchen eine.",
    ]
    assert result.text == "\n\n".join(result.paragraphs)
    assert result.citations == [
        {"document_id": first.document_id, "segment_id": first.id, "paragraph_index": 0},
        {"document_id": second.document_id, "segment_id": second.id, "paragraph_index": 1},
    ]
    system_prompt = llm.messages[0][0]["content"]
    assert "[1] Schutzbrillen sind beim Schweißen Pflicht." in system_prompt
    assert "[2] Helfer tragen ebenfalls Schutzbrillen." in system_prompt
    # The faithfulness check sees the stripped answer, not the markers.
    assert "[1]" not in llm.messages[1][1]["content"]


def test_an_answer_without_valid_markers_cites_every_segment_for_the_whole_answer():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")
    llm = _two_call_llm("Beim Schweißen muss eine Schutzbrille getragen werden [9].")

    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert result.paragraphs == ["Beim Schweißen muss eine Schutzbrille getragen werden."]
    assert result.citations == [
        {"document_id": segment.document_id, "segment_id": segment.id, "paragraph_index": None},
    ]


def test_the_english_prompt_asks_for_markers_in_english():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Goggles are mandatory when welding.")
    llm = _two_call_llm("Wear goggles when welding [1].")

    build_synthesis_answer(
        "What protection?", "DE", "en", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert "for example [1] or [2][3]" in llm.messages[0][0]["content"]


def test_an_answer_of_only_markers_is_a_fallback():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Text.")
    llm = _two_call_llm("[1]")

    result = build_synthesis_answer(
        "Frage", "DE", "de", _FakeEmbeddingModel(), _FakeSegmentRepo([segment]), llm,
    )

    assert result.is_fallback is True
    assert result.paragraphs == ["Dazu finde ich in den verfügbaren Quellen keine ausreichende Grundlage."]


from normly_chat.metered_llm_client import LlmOutputTruncated


def test_a_truncated_answer_falls_back_without_a_faithfulness_call():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _TruncatingLlm:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            raise LlmOutputTruncated()

    llm = _TruncatingLlm()
    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), llm,
    )

    assert result.is_fallback is True
    assert llm.calls == 1


def test_a_truncated_faithfulness_verdict_counts_as_not_faithful():
    segment = _FakeSegment(uuid.uuid4(), uuid.uuid4(), "Schutzbrillen sind beim Schweißen Pflicht.")

    class _SecondCallTruncates:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return "Beim Schweißen muss eine Schutzbrille getragen werden."
            raise LlmOutputTruncated()

    result = build_synthesis_answer(
        "Welche Schutzausrüstung beim Schweißen?", "DE", "de", _FakeEmbeddingModel(),
        _FakeSegmentRepo([segment]), _SecondCallTruncates(),
    )

    assert result.is_fallback is True
