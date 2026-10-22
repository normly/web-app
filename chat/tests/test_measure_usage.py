# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.llm_result import LlmResult
from normly_chat.measure_usage import RecordingLlmClient, summarize


class _Provider:
    def complete(self, messages):
        return LlmResult(text="ja", input_tokens=100, output_tokens=40, truncated=False)


def test_the_recording_client_keeps_every_result():
    client = RecordingLlmClient(_Provider())
    assert client.chat([]) == "ja"
    assert client.results == [LlmResult("ja", 100, 40, False)]


def test_summarize_reports_maxima_and_the_mean_per_answer():
    rows = [
        [LlmResult("a", 1000, 300, False), LlmResult("ja", 1200, 2, False)],
        [LlmResult("a", 800, 100, True)],
    ]
    assert summarize(rows) == {
        "max_output_tokens": 300, "max_answer_total": 2502,
        "mean_answer_total": 1701, "truncated": 1,
    }
