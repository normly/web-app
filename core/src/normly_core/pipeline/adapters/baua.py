# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.pipeline.docling_extraction import (
    DocumentExtractionError,
    extract_document,
    report_skipped_source,
)
from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

# BAuA's three technical-rule series share one designation shape: a series
# prefix, a running number, and an optional "Teil N" suffix for a
# multi-part rule (e.g. "TRGS 500 Teil 1"). See design spec, "Designation-
# Erkennung".
_DESIGNATION_PATTERN = re.compile(
    r"^(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)\s*(.*)$"
)

# A title's own first line is short. Phase 1 deliberately runs no
# sentence-boundary heuristic (see design spec) -- but a continuously-set
# publication (see docs/superpowers/specs/2026-08-30-docling-migration-design.md,
# "Empirischer Befund") merges the *entire* page into one Docling text item,
# and without any bound the pattern's `(.*)$` tail would then capture the
# whole document as its "title". A bare length cap is not a sentence
# heuristic: it only ever costs a missed title (falls back to `None`, same
# as an unmatched designation), never a fabricated one, and `full_text`
# keeps the complete text regardless.
_MAX_TITLE_WORDS = 12

# One glob per series so a directory holding several BAuA series -- or a
# neighbouring source's files, as the DGUV/EUR-Lex fixtures already share
# one -- is read correctly.
_FILE_PATTERNS = ("baua_trgs_*.pdf", "baua_trbs_*.pdf", "baua_trba_*.pdf")


class BauaAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        paths = sorted(
            path for pattern in _FILE_PATTERNS for path in self.directory.glob(pattern)
        )
        for pdf_path in paths:
            # One unreadable file must cost only that file -- the runner
            # cannot isolate a failure raised inside fetch() itself (it
            # surfaces while pulling the next record, outside the runner's
            # per-record guard, and a generator that raised cannot be
            # resumed), so the adapter does it here and reports on stderr
            # instead of aborting the run. See dguv.py/eur_lex.py for the
            # identical pattern.
            #
            # DocumentExtractionError only: a PipelineInitializationError is
            # a broken deployment, not a broken file, and must end the run
            # rather than be skipped once per file.
            try:
                yield from self._fetch_file(pdf_path)
            except DocumentExtractionError as error:
                report_skipped_source(pdf_path, error)

    def _fetch_file(self, pdf_path: Path) -> Iterable[RawRecord]:
        content = pdf_path.read_bytes()
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

        document = extract_document(pdf_path)
        texts = [
            text for item, _level in document.iterate_items()
            if (text := getattr(item, "text", None))
        ]
        first_text = texts[0] if texts else ""

        match = _DESIGNATION_PATTERN.match(first_text)
        if match:
            designation = f"{match.group(1)} {match.group(2)}"
            tail = match.group(3).strip()
            title = tail if tail and len(tail.split()) <= _MAX_TITLE_WORDS else None
        else:
            designation = first_text
            title = None

        yield RawRecord(
            source_id=self.source_id,
            content_hash=content_hash,
            raw_designation=designation,
            raw_issuer="BAuA",
            raw_title=title,
            full_text="\n".join(texts),
            language="de",
            fetched_at=datetime.now(timezone.utc),
        )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        # Phase 1 (design spec, "Entscheidung: Struktur-Tiefe Phase 1"): one
        # segment holding the whole document, no numbered-section splitting
        # yet -- deliberately deferred, not forgotten.
        if record.full_text is None:
            return []
        return [RawSection(sequence_number=1, heading=None, text=record.full_text)]

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: every
        # TRGS/TRBS/TRBA is an amtliche Bekanntmachung, so this source is
        # always classifiable and never hands the runner a "cannot
        # classify". See design spec, "Rechtegrundlage: Kategorie A".
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference=(
                "§ 5 UrhG — amtliche Bekanntmachung (TRGS/TRBS/TRBA, BAuA im GMBl)"
            ),
        )
