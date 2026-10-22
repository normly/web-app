# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_chat.llm_result import LlmResult
from normly_chat.metered_llm_client import LlmOutputTruncated, MeteredLlmClient


class _Provider:
    def __init__(self, result):
        self._result = result

    def complete(self, messages):
        return self._result


class _RecordingGuard:
    def __init__(self):
        self.booked = []

    def book(self, *, pool, result):
        self.booked.append((pool, result))


def test_chat_returns_the_text_and_books_the_usage_to_the_pool():
    result = LlmResult(text="Antwort", input_tokens=10, output_tokens=5, truncated=False)
    guard = _RecordingGuard()

    text = MeteredLlmClient(_Provider(result), guard, "anonymous").chat([{"role": "user", "content": "x"}])

    assert text == "Antwort"
    assert guard.booked == [("anonymous", result)]


def test_a_truncated_answer_is_booked_and_then_raised():
    result = LlmResult(text="Halb", input_tokens=10, output_tokens=100, truncated=True)
    guard = _RecordingGuard()

    with pytest.raises(LlmOutputTruncated):
        MeteredLlmClient(_Provider(result), guard, "registered").chat([])

    assert guard.booked == [("registered", result)]
