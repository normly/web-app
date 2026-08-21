# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import httpx


class OllamaClient:
    """
    Thin httpx wrapper over Ollama's REST API -- direct HTTP calls rather
    than a heavier client library, same reasoning as HttpxGoogleOAuthClient
    in accounts/: the surface used here is one endpoint, not enough to
    justify an extra dependency.
    """

    def __init__(self, base_url: str, model: str, *, timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def chat(self, messages: list[dict]) -> str:
        with httpx.Client(timeout=self._timeout) as http:
            response = http.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": messages, "stream": False},
            )
        response.raise_for_status()
        return response.json()["message"]["content"]
