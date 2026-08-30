# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from normly_core.pipeline.docling_extraction import extract_document
from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

_HEADING_PATTERN = re.compile(r"^§\s*\d+\s+.+")

# Docling merges visually adjacent lines into one text block -- the
# fixture's designation ("DGUV Vorschrift 1") and title ("Grundsätze der
# Prävention") are two separate lines in the source PDF but arrive as a
# single Docling text item, unlike pdfplumber's per-line output. Split them
# back apart by the designation's known "DGUV Vorschrift <N>" prefix rather
# than assuming two separate elements.
_DESIGNATION_PATTERN = re.compile(r"^(DGUV Vorschrift \d+)\s*(.*)$")

# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of DGUV publications.
_FILE_PATTERN = "dguv_*.pdf"


class DguvAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        for pdf_path in sorted(self.directory.glob(_FILE_PATTERN)):
            content = pdf_path.read_bytes()
            content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

            document = extract_document(pdf_path)
            texts = [
                item.text
                for item, _level in document.iterate_items()
                if hasattr(item, "text") and item.text
            ]

            first = texts[0].strip() if texts else ""
            match = _DESIGNATION_PATTERN.match(first)
            if match:
                designation = match.group(1)
                title = match.group(2).strip() or None
            else:
                designation = first
                title = None
            full_text = "\n".join(texts)

            yield RawRecord(
                source_id=self.source_id,
                content_hash=content_hash,
                raw_designation=designation,
                raw_issuer="DGUV",
                raw_title=title,
                full_text=full_text,
                language="de",
                fetched_at=datetime.now(timezone.utc),
            )

    def extract_structure(self, record: RawRecord) -> list[RawSection]:
        assert record.full_text is not None
        lines = record.full_text.splitlines()

        sections: list[RawSection] = []
        current_heading: str | None = None
        current_body: list[str] = []
        sequence_number = 0

        def _flush() -> None:
            nonlocal sequence_number
            if current_heading is None:
                return
            sequence_number += 1
            sections.append(
                RawSection(
                    sequence_number=sequence_number,
                    heading=current_heading,
                    text=" ".join(line.strip() for line in current_body if line.strip()),
                )
            )

        for line in lines:
            if _HEADING_PATTERN.match(line.strip()):
                _flush()
                current_heading = line.strip()
                current_body = []
            elif current_heading is not None:
                current_body.append(line)
        _flush()

        return sections

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: every
        # DGUV-Vorschrift is an amtliches Werk, so this source is always
        # classifiable and never hands the runner a "cannot classify".
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference="§ 5 UrhG — amtliches Werk (DGUV-Vorschrift)",
        )
