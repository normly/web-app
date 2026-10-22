# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import httpx

from normly_chat.llm_result import LlmResult, estimate_input_tokens, reported_tokens


class OllamaClient:
    """
    Thin httpx wrapper over Ollama's REST API -- direct HTTP calls rather
    than a heavier client library, same reasoning as HttpxGoogleOAuthClient
    in accounts/: the surface used here is one endpoint, not enough to
    justify an extra dependency.
    """

    def __init__(
        self, base_url: str, model: str, *, max_output_tokens: int, timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout
        self._transport = transport

    def complete(self, messages: list[dict]) -> LlmResult:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
            response = http.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model, "messages": messages, "stream": False,
                    "options": {"num_predict": self._max_output_tokens},
                },
            )
        response.raise_for_status()
        body = response.json()
        return LlmResult(
            text=body["message"]["content"],
            input_tokens=reported_tokens(
                body.get("prompt_eval_count"), estimate_input_tokens(messages),
            ),
            output_tokens=reported_tokens(body.get("eval_count"), self._max_output_tokens),
            truncated=body.get("done_reason") == "length",
        )
