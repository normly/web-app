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
# "OJ reference for publication in OJ" -- a standard's own first-publication
# reference. "OJ reference for withdrawal from OJ" -- set once the standard
# is superseded, carrying the SAME OJ reference as whichever later row's own
# column 6 announced its successor (both are announced in one OJ notice).
# Verified against the real fixture PDF's Docling table extraction: EN ISO
# 12100-1/-2:2003 and EN ISO 14121-1:2007 each carry 'OJ C 110 -
# 08/04/2011' in column 11; EN ISO 12100:2010 (their consolidating
# successor) carries that exact string in column 6.
_COLUMN_OJ_PUBLICATION = 6
_COLUMN_OJ_WITHDRAWAL = 11

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
            #
            # DocumentExtractionError only. A PipelineInitializationError is a
            # broken deployment, not a broken file: it would fail identically
            # for every file here, so skipping it would turn a misconfigured
            # run into a silent, exit-0 "success" over zero records. It is a
            # separate class precisely so this clause lets it through.
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

        # Pass 1: index every withdrawn row by the OJ reference that
        # announced its withdrawal, across ALL tables -- a successor can
        # land on a different page/table than the standard(s) it replaces.
        # A single OJ notice commonly retires more than one standard at
        # once (a consolidating successor), so each key maps to a LIST.
        withdrawal_index: dict[str, list[tuple[str, str]]] = {}
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_OJ_WITHDRAWAL:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                withdrawal_cell = row[_COLUMN_OJ_WITHDRAWAL]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                withdrawal_ref = (withdrawal_cell.text if withdrawal_cell else "").strip()
                if not eso or not designation or eso.startswith("ESO"):
                    continue
                if not withdrawal_ref or withdrawal_ref == "-":
                    continue
                withdrawal_index.setdefault(withdrawal_ref, []).append((designation, eso))

        # Pass 2: build every record's data -- but do not yield yet. A
        # RawRecord that carries a REPLACES reference must not be yielded
        # before the record it names: extract_references() resolves each
        # reference's target with an immediate document lookup and no later
        # retry (see references.py), so a successor processed ahead of its
        # own predecessor(s) would find nothing there yet and silently lose
        # the edge to a "reference_target_not_found" case instead. Table
        # order alone doesn't guarantee this -- in the real fixture the
        # consolidating successor's table (table 0) precedes the table
        # holding the predecessors it replaces (table 1).
        pending: dict[str, tuple[str, str, list[RawReference]]] = {}
        seen_designations: set[str] = set()
        for table in document.tables:
            for row in table.data.grid:
                if len(row) <= _COLUMN_OJ_WITHDRAWAL:
                    continue
                eso_cell = row[_COLUMN_ESO]
                designation_cell = row[_COLUMN_STANDARD_REFERENCE]
                title_cell = row[_COLUMN_TITLE]
                publication_cell = row[_COLUMN_OJ_PUBLICATION]
                eso = (eso_cell.text if eso_cell else "").strip()
                designation = (designation_cell.text if designation_cell else "").strip()
                title = (title_cell.text if title_cell else "").strip()
                publication_ref = (publication_cell.text if publication_cell else "").strip()
                if not eso or not designation or eso.startswith("ESO"):
                    continue
                if designation in seen_designations:
                    continue
                seen_designations.add(designation)

                references = [
                    RawReference(
                        target_issuer="EU",
                        target_designation=self.legislation_reference,
                        edge_type=EdgeType.BASED_ON_LAW,
                    )
                ]
                if publication_ref and publication_ref != "-":
                    for old_designation, old_eso in withdrawal_index.get(publication_ref, []):
                        references.append(
                            RawReference(
                                target_issuer=old_eso,
                                target_designation=old_designation,
                                edge_type=EdgeType.REPLACES,
                            )
                        )

                pending[designation] = (eso, title, references)

        # Order the yields so every REPLACES target is created first: a
        # record with no REPLACES reference of its own can never depend on
        # another pending record, so all such records (predecessors,
        # never-withdrawn standards, and the legal act's referenced
        # standards in general) go out before any consolidating successor
        # that names them. This fixture's consolidation is one level deep
        # (a successor never itself gets replaced within the same run), so
        # this two-group split is sufficient -- not a general topological
        # sort over arbitrarily chained withdrawals.
        without_replaces = [
            designation
            for designation, (_, _, references) in pending.items()
            if not any(r.edge_type == EdgeType.REPLACES for r in references)
        ]
        with_replaces = [
            designation for designation in pending if designation not in without_replaces
        ]

        for designation in [*without_replaces, *with_replaces]:
            eso, title, references = pending[designation]
            yield RawRecord(
                source_id=self.source_id,
                content_hash=f"{content_hash}:{designation}",
                raw_designation=designation,
                raw_issuer=eso,
                raw_title=title or None,
                full_text=None,
                language="en",
                raw_references=references,
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
