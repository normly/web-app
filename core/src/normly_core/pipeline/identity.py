# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from dataclasses import dataclass

from normly_core.graph.domain import DocumentRepository
from normly_core.pipeline.domain import IdentityResolution, RawRecord


class UnparseableDesignationError(Exception):
    def __init__(self, raw: str):
        self.raw = raw
        super().__init__(f"cannot parse designation: {raw!r}")


@dataclass(frozen=True)
class ParsedDesignation:
    number: str
    edition: str | None


def parse_designation(raw: str) -> ParsedDesignation:
    stripped = raw.strip()
    if not stripped:
        raise UnparseableDesignationError(raw)
    if ":" in stripped:
        number_part, edition = stripped.rsplit(":", 1)
        number_part = number_part.strip()
        edition = edition.strip()
        if not number_part:
            raise UnparseableDesignationError(raw)
        return ParsedDesignation(number=number_part, edition=edition or None)
    return ParsedDesignation(number=stripped, edition=None)


def resolve(record: RawRecord, document_repo: DocumentRepository) -> IdentityResolution:
    try:
        parse_designation(record.raw_designation)
    except UnparseableDesignationError:
        return IdentityResolution(
            document_id=None, is_new=False, is_ambiguous=True,
            reason="unparseable_designation",
        )

    if record.raw_issuer is not None:
        if record.edition is not None:
            exact = document_repo.find_by_designation(
                record.raw_issuer, record.raw_designation, edition=record.edition
            )
            if exact is not None:
                return IdentityResolution(
                    document_id=exact.id, is_new=False, is_ambiguous=False, reason=None
                )
            # Same designation, but not this exact edition -- check whether an
            # earlier edition exists at all, to distinguish "new edition of a
            # known Regelwerk" from "genuinely first appearance."
            previous = document_repo.find_by_designation(
                record.raw_issuer, record.raw_designation
            )
            return IdentityResolution(
                document_id=None, is_new=True, is_ambiguous=False, reason=None,
                previous_edition_document_id=previous.id if previous else None,
            )

        existing = document_repo.find_by_designation(record.raw_issuer, record.raw_designation)
        if existing is not None:
            return IdentityResolution(
                document_id=existing.id, is_new=False, is_ambiguous=False, reason=None
            )

    return IdentityResolution(document_id=None, is_new=True, is_ambiguous=False, reason=None)
