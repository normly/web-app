# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""What one model call produced and what it cost."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Rough characters-per-token ratio for German and English text. Only used
# when a provider omits its usage figures; a low ratio over-counts, which is
# the safe direction for a budget.
_CHARS_PER_TOKEN = 3


@dataclass(frozen=True)
class LlmResult:
    text: str
    input_tokens: int
    output_tokens: int
    # The provider stopped because the output cap was reached.
    truncated: bool


def estimate_input_tokens(messages: list[dict]) -> int:
    characters = sum(len(message.get("content") or "") for message in messages)
    return math.ceil(characters / _CHARS_PER_TOKEN)


def reported_tokens(value: object, fallback: int) -> int:
    """A provider's token count, or the fallback when it is absent or null."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return fallback
