# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
The source registry the pipeline ingests from.

Every source needs a registry entry with a legal-basis category before a single
byte of it may be processed ("Jede Quelle braucht einen Registereintrag mit
Kategorie"). This module is where that entry is declared for the adapters the
CLI ships with, and `resolve_source` is what turns the declaration into the
`Source` row every delivery's lineage points at.

Resolution is keyed on the publisher, not on a hardcoded UUID: a second run
finds the row the first run wrote instead of creating a duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from normly_core.graph.domain import LegalBasisCategory, Source, SourceRepository


@dataclass(frozen=True)
class SourceRegistryEntry:
    publisher: str
    retrieval_path: str
    legal_basis_category: LegalBasisCategory
    jurisdiction: str
    reviewed_at: date
    responsible_person: str


SOURCE_REGISTRY: dict[str, SourceRegistryEntry] = {
    "eur-lex": SourceRegistryEntry(
        publisher="EUR-Lex",
        retrieval_path="https://single-market-economy.ec.europa.eu",
        # Commission summary lists of harmonised standards are amtliche Werke:
        # the list itself is published by the Union, no standard full text is
        # part of it.
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    ),
    "dguv": SourceRegistryEntry(
        publisher="DGUV",
        retrieval_path="https://www.dguv.de/publikationen",
        # DGUV-Vorschriften are amtliche Werke under § 5 UrhG.
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="DE",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    ),
}


def resolve_source(repository: SourceRepository, key: str) -> Source:
    """
    Return the registry's `Source` row for `key`, creating it on first use.

    Idempotent: a second call resolves to the same row.

    The insert is not guarded by a unique constraint on `source.publisher`,
    because a publisher may legitimately hold several registry entries (see
    `find_by_publisher`). Two ingestion runs racing on a publisher's very first
    registration could therefore both insert; the pipeline is run sequentially,
    and a duplicate registry entry is a review finding, not data loss.
    """
    try:
        entry = SOURCE_REGISTRY[key]
    except KeyError:
        raise ValueError(f"unknown source: {key!r}") from None

    existing = repository.find_by_publisher(entry.publisher)
    if existing is not None:
        return existing

    return repository.create_source(
        publisher=entry.publisher,
        retrieval_path=entry.retrieval_path,
        legal_basis_category=entry.legal_basis_category,
        jurisdiction=entry.jurisdiction,
        reviewed_at=entry.reviewed_at,
        responsible_person=entry.responsible_person,
    )
