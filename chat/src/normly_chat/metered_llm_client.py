# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The only LLM client synthesis and title code ever receive: every call is
booked to the request's cost pool before its text is used.
"""

from __future__ import annotations

from normly_chat.llm_client import LlmClient


class LlmOutputTruncated(Exception):
    """The provider stopped at the output cap; the text is incomplete."""


class MeteredLlmClient:
    def __init__(self, inner: LlmClient, guard, pool: str):
        self._inner = inner
        self._guard = guard
        self._pool = pool

    def chat(self, messages: list[dict]) -> str:
        result = self._inner.complete(messages)
        # Booked first: a cut-off answer cost its tokens all the same.
        self._guard.book(pool=self._pool, result=result)
        if result.truncated:
            raise LlmOutputTruncated()
        return result.text
