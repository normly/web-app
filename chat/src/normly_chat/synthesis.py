# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass, field

from normly_core.pipeline.embeddings import MODEL_NAME as _EMBEDDING_MODEL_NAME

from normly_chat.markers import number_context, parse_marked_answer

_FALLBACK_TEXT = {
    "de": "Dazu finde ich in den verfügbaren Quellen keine ausreichende Grundlage.",
    "en": "I don't find sufficient grounding in the available sources for that.",
}

_VERBATIM_OVERLAP_WORDS = 15


@dataclass(frozen=True)
class SynthesisAnswer:
    paragraphs: list[str]
    citations: list[dict] = field(default_factory=list)
    is_fallback: bool = False
    ollama_calls: int = 0

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


def _fallback(language: str, ollama_calls: int = 0) -> SynthesisAnswer:
    return SynthesisAnswer(
        paragraphs=[_FALLBACK_TEXT[language]], citations=[], is_fallback=True,
        ollama_calls=ollama_calls,
    )


def _has_verbatim_overlap(answer: str, context: str) -> bool:
    answer_words = answer.split()
    context_words = context.split()
    context_joined = " ".join(context_words)
    for window_start in range(len(answer_words) - _VERBATIM_OVERLAP_WORDS + 1):
        window = answer_words[window_start:window_start + _VERBATIM_OVERLAP_WORDS]
        window_text = " ".join(window)
        if window_text and window_text in context_joined:
            return True
    return False


_SYSTEM_PROMPT = {
    "de": (
        "Du beantwortest Fragen ausschließlich auf Grundlage der folgenden nummerierten "
        "Kontextabschnitte. Paraphrasiere, gib den Kontext nicht wortwörtlich wieder. "
        "Antworte auf Deutsch. Trenne Absätze durch eine Leerzeile und belege jeden Absatz "
        "mit den Nummern der Abschnitte, auf die er sich stützt, zum Beispiel [1] oder [2][3]."
    ),
    "en": (
        "You answer questions using only the following numbered context passages. "
        "Paraphrase, do not reproduce the context verbatim. Answer in English. "
        "Separate paragraphs with a blank line and back every paragraph with the numbers "
        "of the passages it relies on, for example [1] or [2][3]."
    ),
}

_FAITHFULNESS_PROMPT = {
    "de": (
        "Ist die folgende Antwort ausschließlich durch den gegebenen Kontext gedeckt, "
        "ohne Behauptungen hinzuzufügen, die dort nicht stehen? "
        "Antworte mit dem ersten Wort 'ja' oder 'nein'."
    ),
}
# German-only by design (see the design spec): the faithfulness check always
# runs its prompt in German regardless of the answer's language, so there is
# no English entry to keep in sync.
_AFFIRMATIVE_ANSWERS = {"de": "ja"}


def _is_faithful(answer_text: str, context: str, llm_client) -> bool:
    check_response = llm_client.chat([
        {
            "role": "system",
            "content": f"{_FAITHFULNESS_PROMPT['de']}\n\nKontext:\n{context}",
        },
        {"role": "user", "content": answer_text},
    ])
    first_word = check_response.strip().lower().split()[0] if check_response.strip() else ""
    return first_word.startswith(_AFFIRMATIVE_ANSWERS["de"])


def build_synthesis_answer(
    message: str, jurisdiction: str, language: str, embedding_model, segment_repo, llm_client,
) -> SynthesisAnswer:
    query_vector = embedding_model.embed_query(message)
    segments = segment_repo.find_similar_segments_for_jurisdiction(
        query_vector, jurisdiction, _EMBEDDING_MODEL_NAME,
    )
    if not segments:
        return _fallback(language)

    # The checks compare against the plain passages; only the model sees the
    # numbers it needs to set markers.
    context = "\n\n".join(segment.text for segment in segments)
    numbered_context = number_context([segment.text for segment in segments])
    messages = [
        {"role": "system", "content": f"{_SYSTEM_PROMPT[language]}\n\nKontext:\n{numbered_context}"},
        {"role": "user", "content": message},
    ]
    raw_answer = llm_client.chat(messages)
    ollama_calls = 1

    paragraphs = parse_marked_answer(raw_answer, len(segments))
    if not paragraphs:
        return _fallback(language, ollama_calls=ollama_calls)
    answer_text = "\n\n".join(paragraph.text for paragraph in paragraphs)

    if _has_verbatim_overlap(answer_text, context):
        return _fallback(language, ollama_calls=ollama_calls)

    if not _is_faithful(answer_text, context, llm_client):
        ollama_calls += 1
        return _fallback(language, ollama_calls=ollama_calls)
    ollama_calls += 1

    if any(paragraph.sources for paragraph in paragraphs):
        citations = [
            {
                "document_id": segments[source].document_id,
                "segment_id": segments[source].id,
                "paragraph_index": index,
            }
            for index, paragraph in enumerate(paragraphs)
            for source in paragraph.sources
        ]
    else:
        # No usable marker at all: the answer still never stands without a
        # source, so every passage it was built from backs the whole answer.
        citations = [
            {"document_id": segment.document_id, "segment_id": segment.id, "paragraph_index": None}
            for segment in segments
        ]
    return SynthesisAnswer(
        paragraphs=[paragraph.text for paragraph in paragraphs],
        citations=citations, ollama_calls=ollama_calls,
    )
