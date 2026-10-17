# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Source markers in synthesis answers.

The model sees the context passages numbered ([1], [2], ...) and backs each
paragraph with the numbers it relies on. This module numbers the context and
turns a marked answer into clean paragraphs with their sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "[1]", "[1][3]", "[1, 3]"; the whitespace in front goes with the marker so
# "Pflicht [1]." becomes "Pflicht.".
_MARKER = re.compile(r"\s*\[(\d+(?:\s*,\s*\d+)*)\]")
_BLANK_LINE = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class MarkedParagraph:
    text: str
    sources: list[int] = field(default_factory=list)


def number_context(texts: list[str]) -> str:
    return "\n\n".join(f"[{number}] {text}" for number, text in enumerate(texts, start=1))


def split_paragraphs(text: str) -> list[str]:
    return [block.strip() for block in _BLANK_LINE.split(text.strip()) if block.strip()]


def parse_marked_answer(answer: str, source_count: int) -> list[MarkedParagraph]:
    paragraphs: list[MarkedParagraph] = []
    for block in split_paragraphs(answer):
        sources: list[int] = []
        for match in _MARKER.finditer(block):
            for number in match.group(1).split(","):
                index = int(number) - 1
                if 0 <= index < source_count and index not in sources:
                    sources.append(index)
        text = _MARKER.sub("", block).strip()
        if text:
            paragraphs.append(MarkedParagraph(text, sources))
        elif paragraphs:
            # A line holding only markers backs the paragraph above it.
            previous = paragraphs[-1]
            merged = previous.sources + [s for s in sources if s not in previous.sources]
            paragraphs[-1] = MarkedParagraph(previous.text, merged)
    return paragraphs
