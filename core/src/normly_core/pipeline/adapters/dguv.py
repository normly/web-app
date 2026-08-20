# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pdfplumber

from normly_core.pipeline.domain import RawRecord, RawSection, RightsRule

_HEADING_PATTERN = re.compile(r"^§\s*\d+\s+.+")

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

            with pdfplumber.open(pdf_path) as pdf:
                lines: list[str] = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    lines.extend(text.splitlines())

            designation = lines[0].strip()
            title = lines[1].strip() if len(lines) > 1 else None
            full_text = "\n".join(lines)

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
