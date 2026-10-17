# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import httpx

from normly_chat.titles import fallback_title, generate_title


def test_a_short_question_is_its_own_fallback_title():
    assert fallback_title("  Ist DIN EN ISO 9001\n noch gültig?  ") == "Ist DIN EN ISO 9001 noch gültig?"


def test_a_long_question_is_cut_at_a_word_boundary():
    question = (
        "Welche Anforderungen stellt DIN EN ISO 13849-1 an die Bewertung "
        "des Performance Level einer Sicherheitsfunktion?"
    )
    title = fallback_title(question)
    assert title == "Welche Anforderungen stellt DIN EN ISO 13849-1 an die…"
    assert len(title) <= 61


class _Llm:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        if self._error:
            raise self._error
        return self._response


def test_generate_title_cleans_the_model_output():
    llm = _Llm('„Performance Level bewerten“.\nZweite Zeile')
    assert generate_title(llm, "Frage", "de") == "Performance Level bewerten"
    assert "drei bis sechs Wörtern" in llm.messages[0]["content"]
    assert llm.messages[1] == {"role": "user", "content": "Frage"}


def test_generate_title_uses_the_session_language():
    llm = _Llm("Welding goggles")
    assert generate_title(llm, "Question", "en") == "Welding goggles"
    assert "three to six words" in llm.messages[0]["content"]


def test_generate_title_returns_none_on_failure_or_empty_output():
    assert generate_title(_Llm(error=httpx.ConnectError("down")), "Frage", "de") is None
    assert generate_title(_Llm(error=KeyError("choices")), "Frage", "de") is None
    assert generate_title(_Llm("   "), "Frage", "de") is None


def test_generate_title_caps_an_overlong_answer():
    title = generate_title(_Llm(" ".join(["Wort"] * 30)), "Frage", "de")
    assert len(title.split()) == 8
