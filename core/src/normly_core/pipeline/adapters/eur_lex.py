# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.graph.domain import EdgeType
from normly_core.pipeline.docling_extraction import (
    DocumentExtractionError,
    extract_document,
    report_skipped_source,
)
from normly_core.pipeline.domain import (
    RawRecord,
    RawReference,
    RawSection,
    RightsRule,
)

# Column indices in the Commission's "Summary list of harmonised standards"
# table, 0-based -- verified against the real fixture PDF's Docling table
# extraction (`table.data.grid`): ['Legislation reference (A)', 'ESO (B)',
# 'Reference number of the standard (C)', 'Title of the standard (D)',
# 'Type (E)', ...]. Same column layout Docling produces as pdfplumber did.
# Unlike pdfplumber, Docling's header cells carry no embedded line break
# ("ESO (B)", not pdfplumber's "ESO\n(B)") -- the prefix filter below still
# works correctly either way, so it's kept rather than narrowed to an exact
# match.
_COLUMN_ESO = 1
_COLUMN_STANDARD_REFERENCE = 2
_COLUMN_TITLE = 3

# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of Commission summary lists.
_FILE_PATTERN = "eur_lex_*.pdf"


class EurLexAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID, legislation_reference: str):
        self.directory = directory
        self.source_id = source_id
        self.legislation_reference = legislation_reference

    def fetch(self) -> Iterable[RawRecord]:
        for pdf_path in sorted(self.directory.glob(_FILE_PATTERN)):
            # One unreadable file must cost only that file. Without this, the
            # error would surface in the runner's `for record in fetch()` line,
            # outside its per-record guard, aborting the run and losing every
            # file behind this one -- see report_skipped_source().
            try:
                yield from self._fetch_file(pdf_path)
            except DocumentExtractionError as error:
                report_skipped_source(pdf_path, error)

    def _fetch_file(self, pdf_path: Path) -> Iterable[RawRecord]:
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        now = datetime.now(timezone.utc)

        # Extract before yielding anything: a file that cannot be read must
        # yield no records at all, not a legal-act record whose standards
        # never followed.
        document = extract_document(pdf_path)

        yield RawRecord(
            source_id=self.source_id,
            content_hash=f"{content_hash}:legal-act",
            raw_designation=self.legislation_reference,
            raw_issuer="EU",
            raw_title=None,
            full_text=None,
            # The Commission publishes this summary list in English.
            language="en",
            fetched_at=now,
        )

        seen_designations: set[str] = set()
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_TITLE:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                title_cell = row[_COLUMN_TITLE]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                title = (title_cell.text if title_cell else "").strip()
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
                    language="en",
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
