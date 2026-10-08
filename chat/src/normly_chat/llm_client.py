# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
LLM client selection.

Two providers behind one tiny interface: Ollama for local development and
self-hosting, and any OpenAI-compatible `/chat/completions` endpoint for
production -- concretely STACKIT AI Model Serving (ADR-022). Both are thin
httpx wrappers; no vendor SDK, same reasoning as OllamaClient.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol

import httpx

from normly_chat.ollama_client import OllamaClient

PROVIDER_ENV_VAR = "NORMLY_LLM_PROVIDER"
BASE_URL_ENV_VAR = "NORMLY_LLM_BASE_URL"
MODEL_ENV_VAR = "NORMLY_LLM_MODEL"
API_KEY_ENV_VAR = "NORMLY_LLM_API_KEY"

PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI_COMPATIBLE = "openai-compatible"


class LlmClient(Protocol):
    def chat(self, messages: list[dict]) -> str: ...


class OpenAiCompatibleClient:
    """POST {base_url}/chat/completions with a bearer token; returns the first choice."""

    def __init__(
        self, base_url: str, model: str, api_key: str, *,
        timeout: float = 120.0, transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    def chat(self, messages: list[dict]) -> str:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
            response = http.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "stream": False},
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def build_llm_client_from_env(environ: Mapping[str, str] = os.environ) -> LlmClient:
    provider = environ.get(PROVIDER_ENV_VAR, PROVIDER_OLLAMA)
    base_url = environ[BASE_URL_ENV_VAR]
    model = environ[MODEL_ENV_VAR]
    if provider == PROVIDER_OLLAMA:
        return OllamaClient(base_url=base_url, model=model)
    if provider == PROVIDER_OPENAI_COMPATIBLE:
        return OpenAiCompatibleClient(base_url, model, environ[API_KEY_ENV_VAR])
    raise ValueError(
        f"{PROVIDER_ENV_VAR} must be {PROVIDER_OLLAMA!r} or {PROVIDER_OPENAI_COMPATIBLE!r}, "
        f"got {provider!r}"
    )
