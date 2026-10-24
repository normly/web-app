# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json

import httpx
import pytest

from normly_chat.llm_client import OpenAiCompatibleClient, build_llm_client_from_env
from normly_chat.llm_result import LlmResult, estimate_input_tokens
from normly_chat.ollama_client import OllamaClient


def _transport(handler):
    return httpx.MockTransport(handler)


def test_openai_compatible_client_posts_chat_completions_and_returns_a_result():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{
                "message": {"role": "assistant", "content": "Antwort"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1/", "google/gemma-4-31B-it", "secret-token",
        max_output_tokens=512, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "Frage"}])

    assert result == LlmResult(text="Antwort", input_tokens=120, output_tokens=30, truncated=False)
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["body"]["model"] == "google/gemma-4-31B-it"
    assert seen["body"]["messages"] == [{"role": "user", "content": "Frage"}]
    assert seen["body"]["stream"] is False
    assert seen["body"]["max_tokens"] == 512


def test_openai_compatible_client_flags_a_length_cut_answer_as_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Halbe Antw"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 512},
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    assert client.complete([{"role": "user", "content": "x"}]).truncated is True


def test_openai_compatible_client_books_conservatively_when_usage_is_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "x" * 30}])

    assert result.input_tokens == 10
    assert result.output_tokens == 512


def test_openai_compatible_client_books_conservatively_when_usage_fields_are_null():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": None, "completion_tokens": None},
        })

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "x" * 30}])

    assert result.input_tokens == 10
    assert result.output_tokens == 512


def test_estimate_input_tokens_rounds_up_a_third_of_all_characters():
    assert estimate_input_tokens([
        {"role": "system", "content": "abcd"}, {"role": "user", "content": "ef"},
    ]) == 2


def test_build_from_env_passes_the_output_cap_to_the_client():
    client = build_llm_client_from_env({
        "NORMLY_LLM_PROVIDER": "openai-compatible",
        "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
        "NORMLY_LLM_MODEL": "m",
        "NORMLY_LLM_API_KEY": "t",
    }, max_output_tokens=256)
    assert client._max_output_tokens == 256


def test_ollama_client_sends_num_predict_and_maps_its_counters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "message": {"role": "assistant", "content": "Antwort"},
            "done_reason": "stop", "prompt_eval_count": 80, "eval_count": 20,
        })

    client = OllamaClient(
        "http://ollama:11434", "gemma4:e4b", max_output_tokens=300, transport=_transport(handler),
    )
    result = client.complete([{"role": "user", "content": "Frage"}])

    assert result == LlmResult(text="Antwort", input_tokens=80, output_tokens=20, truncated=False)
    assert seen["body"]["options"] == {"num_predict": 300}


def test_ollama_client_flags_done_reason_length_as_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "message": {"content": "Halb"}, "done_reason": "length",
            "prompt_eval_count": 5, "eval_count": 300,
        })

    client = OllamaClient("http://ollama:11434", "m", max_output_tokens=300, transport=_transport(handler))
    assert client.complete([{"role": "user", "content": "x"}]).truncated is True


def test_ollama_client_books_conservatively_when_its_counters_are_null():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "message": {"content": "Antwort"}, "done_reason": "stop",
            "prompt_eval_count": None, "eval_count": None,
        })

    client = OllamaClient("http://ollama:11434", "m", max_output_tokens=300, transport=_transport(handler))
    result = client.complete([{"role": "user", "content": "x" * 30}])

    assert result.input_tokens == 10
    assert result.output_tokens == 300


def test_openai_compatible_client_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = OpenAiCompatibleClient(
        "https://llm.example/v1", "m", "t", max_output_tokens=512, transport=_transport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.complete([{"role": "user", "content": "x"}])


def test_build_from_env_defaults_to_ollama():
    client = build_llm_client_from_env({
        "NORMLY_LLM_BASE_URL": "http://ollama:11434", "NORMLY_LLM_MODEL": "gemma3:4b",
    }, max_output_tokens=256)
    assert isinstance(client, OllamaClient)


def test_build_from_env_selects_openai_compatible_with_api_key():
    client = build_llm_client_from_env({
        "NORMLY_LLM_PROVIDER": "openai-compatible",
        "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
        "NORMLY_LLM_MODEL": "google/gemma-4-31B-it",
        "NORMLY_LLM_API_KEY": "t",
    }, max_output_tokens=256)
    assert isinstance(client, OpenAiCompatibleClient)


def test_build_from_env_requires_api_key_for_openai_compatible():
    with pytest.raises(KeyError, match="NORMLY_LLM_API_KEY"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "openai-compatible",
            "NORMLY_LLM_BASE_URL": "https://llm.example/v1",
            "NORMLY_LLM_MODEL": "m",
        }, max_output_tokens=256)


def test_build_from_env_rejects_unknown_provider():
    with pytest.raises(ValueError, match="NORMLY_LLM_PROVIDER"):
        build_llm_client_from_env({
            "NORMLY_LLM_PROVIDER": "anthropic",
            "NORMLY_LLM_BASE_URL": "x", "NORMLY_LLM_MODEL": "m",
        }, max_output_tokens=256)
