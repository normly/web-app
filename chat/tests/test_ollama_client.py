# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os

import pytest

from normly_chat.ollama_client import OllamaClient

pytestmark = pytest.mark.skipif(
    "NORMLY_TEST_OLLAMA_BASE_URL" not in os.environ,
    reason="requires a running Ollama server; set NORMLY_TEST_OLLAMA_BASE_URL",
)


@pytest.fixture()
def ollama_client():
    return OllamaClient(
        base_url=os.environ["NORMLY_TEST_OLLAMA_BASE_URL"],
        model=os.environ.get("NORMLY_TEST_OLLAMA_MODEL", "llama3.1:8b-instruct-q4_0"),
    )


def test_chat_returns_a_non_empty_string(ollama_client):
    answer = ollama_client.chat(
        [{"role": "user", "content": "Antworte nur mit dem Wort: Test"}]
    )
    assert isinstance(answer, str)
    assert len(answer) > 0
