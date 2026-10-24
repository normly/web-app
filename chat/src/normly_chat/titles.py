# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Chat session titles: a short model summary of the first question, with the
truncated question itself as the fallback.
"""

from __future__ import annotations

import httpx

from normly_chat.metered_llm_client import LlmOutputTruncated

_FALLBACK_MAX_CHARS = 60
_MAX_TITLE_WORDS = 8
_QUOTES = "\"'„“”‚‘’«»"

_TITLE_PROMPT = {
    "de": (
        "Fasse die folgende Frage als Titel mit drei bis sechs Wörtern zusammen. "
        "Antworte nur mit dem Titel, ohne Anführungszeichen und ohne Punkt am Ende."
    ),
    "en": (
        "Summarise the following question as a title of three to six words. "
        "Answer with the title only, without quotation marks and without a final full stop."
    ),
}


def fallback_title(question: str) -> str:
    text = " ".join(question.split())
    if len(text) <= _FALLBACK_MAX_CHARS:
        return text
    cut = text[:_FALLBACK_MAX_CHARS]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(" ,.;:") + "…"


def generate_title(llm_client, question: str, language: str) -> str | None:
    prompt = _TITLE_PROMPT.get(language, _TITLE_PROMPT["en"])
    try:
        raw = llm_client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ])
    except (httpx.HTTPError, KeyError, IndexError, ValueError, LlmOutputTruncated):
        # The title is a convenience: a failed model call must not fail the
        # request, the caller falls back to the truncated question.
        return None
    lines = (raw or "").strip().splitlines()
    if not lines:
        return None
    title = lines[0].strip().strip(_QUOTES).rstrip(".").strip().strip(_QUOTES).strip()
    words = title.split()
    if not words:
        return None
    return " ".join(words[:_MAX_TITLE_WORDS])
