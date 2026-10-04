# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json

import httpx
import pytest

from normly_chat.llm_client import OpenAiCompatibleClient, build_llm_client_from_env
from normly_chat.ollama_client import OllamaClient


def _transport(handler):
    return httpx.MockTransport(handler)


def test_openai_compatible_client_posts_chat_completions_and_returns_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "Antwort"}}],
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1/", "google/gemma-4-31B-it", "secret-token",
        transport=_transport(handler),
    )
    answer = client.chat([{"role": "user", "content": "Frage"}])

    assert answer == "Antwort"
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["body"]["model"] == "google/gemma-4-31B-it"
    assert seen["body"]["messages"] == [{"role": "user", "content": "Frage"}]
    assert seen["body"]["stream"] is False


def test_openai_compatible_client_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = OpenAiCompatibleClient("https://llm.example/v1", "m", "t", transport=_transport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.chat([{"role": "user", "content": "x"}])


def test_build_from_env_defaults_to_ollama():
    client = build_llm_client_from_env({
        "NORMLY_LLM_BASE_URL": "http://ollama:11434", "NORMLY_LLM_MODEL": "gemma3:4b",
    })
    assert isinstance(client, OllamaClient)


def test_build_from_env_selects_openai_compatible_with_api_key():
    client = build_llm_client_from_env({
        "NORMLY_LLM_PROVIDER": "openai-compatible",
        "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
        "NORMLY_LLM_MODEL": "google/gemma-4-31B-it",
        "NORMLY_LLM_API_KEY": "t",
    })
    assert isinstance(client, OpenAiCompatibleClient)


def test_build_from_env_requires_api_key_for_openai_compatible():
    with pytest.raises(KeyError, match="NORMLY_LLM_API_KEY"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "openai-compatible",
            "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
            "NORMLY_LLM_MODEL": "m",
        })


def test_build_from_env_rejects_unknown_provider():
    with pytest.raises(ValueError, match="NORMLY_LLM_PROVIDER"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "anthropic",
            "NORMLY_LLM_BASE_URL": "x", "NORMLY_LLM_MODEL": "m",
        })
