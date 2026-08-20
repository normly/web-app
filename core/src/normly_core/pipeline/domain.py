# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Protocol

from normly_core.graph.domain import EdgeType


@dataclass(frozen=True)
class RawReference:
    target_issuer: str
    target_designation: str
    edge_type: EdgeType


@dataclass(frozen=True)
class RawSection:
    sequence_number: int
    heading: str | None
    text: str


@dataclass(frozen=True)
class RawRecord:
    source_id: uuid.UUID
    content_hash: str
    raw_designation: str
    raw_issuer: str | None
    raw_title: str | None
    full_text: str | None
    raw_references: list[RawReference] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RightsRule:
    jurisdiction: str
    may_process: bool
    may_index_fulltext: bool
    may_cite_passages: bool
    may_export_free: bool
    legal_basis_reference: str


@dataclass(frozen=True)
class IdentityResolution:
    document_id: uuid.UUID | None
    is_new: bool
    is_ambiguous: bool
    reason: str | None


class SourceAdapter(Protocol):
    source_id: uuid.UUID

    def fetch(self) -> Iterable[RawRecord]: ...
    def extract_structure(self, record: RawRecord) -> list[RawSection]: ...

    def classify_rights(self, record: RawRecord) -> RightsRule | None:
        """
        Classify what may be done with this record, or return `None`.

        `None` means "cannot classify", not "nothing is allowed by default" —
        the runner then writes no artifact at all and hands the record to
        review. A missing classification means "do not process", never
        "provisionally permitted", so an adapter must never invent a permissive
        rule to satisfy the signature.
        """
        ...
