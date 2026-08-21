# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import re
from enum import Enum


class QuestionType(str, Enum):
    STRUCTURAL_VALIDITY = "structural_validity"
    STRUCTURAL_REFERENCE = "structural_reference"
    SYNTHESIS = "synthesis"


_VALIDITY_PATTERN = re.compile(
    r"\bgültig\b|\bin kraft\b|\baktuell\b|\bvalid\b|\bin force\b", re.IGNORECASE
)
_REFERENCE_PATTERN = re.compile(
    r"\bersetzt\b|\bverweis\b|\bverweist\b|\breplaces\b|\breferences?\b", re.IGNORECASE
)


def classify(message: str) -> QuestionType:
    # A structural classification needs the trigger pattern AND a recognizable
    # designation in the text (the design spec's rule). Words like "aktuell"
    # and "gültig" are ordinary German and appear in plain synthesis questions
    # ("Welche Schutzausrüstung ist beim Schweißen aktuell vorgeschrieben?");
    # without a designation the structural path has nothing to look up and
    # could only ever produce a fallback, so those belong in retrieval.
    if extract_designation(message) is None:
        return QuestionType.SYNTHESIS
    if _VALIDITY_PATTERN.search(message):
        return QuestionType.STRUCTURAL_VALIDITY
    if _REFERENCE_PATTERN.search(message):
        return QuestionType.STRUCTURAL_REFERENCE
    return QuestionType.SYNTHESIS


# Standards-style designations (DIN/CEN/ISO conventions) are stored WITH the
# issuer text baked into the designation string itself ("DIN EN ISO 9001"),
# longest-prefix-first so "DIN EN ISO" is preferred over the shorter "DIN".
_STANDARDS_ISSUERS = ("DIN EN ISO", "DIN EN", "DIN", "CEN EN ISO", "CEN EN", "CEN", "ISO")
_STANDARDS_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(i) for i in _STANDARDS_ISSUERS) + r")\s+([0-9][\w./:-]*)"
)

# EU legal-act designations are the bare "YYYY/NN/EC"-style number, stored
# WITHOUT an "EU" prefix in the designation itself -- a different shape from
# the standards convention above, not a bug: it mirrors how the EUR-Lex
# ingestion adapter actually records them (raw_issuer="EU",
# raw_designation=the bare number).
_EU_PATTERN = re.compile(r"\bEU\b\s+(\d{4}/\d+(?:/[A-Z]+)?)", re.IGNORECASE)


def extract_designation(message: str) -> tuple[str, str] | None:
    standards_match = _STANDARDS_PATTERN.search(message)
    if standards_match:
        issuer = standards_match.group(1).split()[0]
        designation = f"{standards_match.group(1)} {standards_match.group(2)}"
        return issuer, designation

    eu_match = _EU_PATTERN.search(message)
    if eu_match:
        return "EU", eu_match.group(1)

    return None
