# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pdfplumber

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.domain import (
    RawRecord,
    RawReference,
    RawSection,
    RightsRule,
)

# Column indices in the Commission's "Summary list of harmonised standards" table,
# 0-based, verified against the real fixture PDF's `pdfplumber` table extraction:
# ['Legislation reference (A)', 'ESO (B)', 'Reference number of the standard (C)',
# 'Title of the standard (D)', 'Type (E)', ...]. The header row's ESO cell is
# literally "ESO\n(B)" (pdfplumber keeps the embedded line break before the
# column-letter annotation), so header rows are filtered by prefix, not equality.
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3


class EurLexAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID, legislation_reference: str):
        self.directory = directory
        self.source_id = source_id
        self.legislation_reference = legislation_reference

    def fetch(self) -> Iterable[RawRecord]:
        pdf_path = self.directory / "eur_lex_machinery_summary.pdf"
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        now = datetime.now(timezone.utc)

        yield RawRecord(
            source_id=self.source_id,
            content_hash=f"{content_hash}:legal-act",
            raw_designation=self.legislation_reference,
            raw_issuer="EU",
            raw_title=None,
            full_text=None,
            fetched_at=now,
        )

        with pdfplumber.open(pdf_path) as pdf:
            seen_designations: set[str] = set()
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        if row is None or len(row) <= _COLUMN_TITLE:
                            continue
                        eso = (row[_COLUMN_ESO] or "").strip()
                        designation = (row[_COLUMN_STANDARD_REFERENCE] or "").strip()
                        title = (row[_COLUMN_TITLE] or "").strip()
                        if not eso or not designation or eso.startswith("ESO"):
                            continue
                        if designation in seen_designations:
                            continue
                        seen_designations.add(designation)
                        yield RawRecord(
                            source_id=self.source_id,
                            content_hash=f"{content_hash}:{designation}",
                            raw_designation=designation,
                            raw_issuer=eso,
                            raw_title=title or None,
                            full_text=None,
                            raw_references=[
                                RawReference(
                                    target_issuer="EU",
                                    target_designation=self.legislation_reference,
                                    edge_type=EdgeType.BASED_ON_LAW,
                                )
                            ],
                            fetched_at=now,
                        )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        return []

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: the
        # Commission's summary list carries no standard full text, so every
        # record it yields is classifiable and never returns "cannot classify".
        if record.raw_designation == self.legislation_reference:
            return RightsRule(
                jurisdiction="EU", may_process=True, may_index_fulltext=False,
                may_cite_passages=False, may_export_free=True,
                legal_basis_reference="§ 5 UrhG / amtliches Werk (Rechtsakt)",
            )
        return RightsRule(
            jurisdiction="EU", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True,
            legal_basis_reference="Kategorie A — Kommissions-Zusammenfassung, kein Normvolltext",
        )
