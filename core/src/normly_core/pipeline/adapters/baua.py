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
# prefix, a running number, and an optional "Teil N" ("part N") suffix for a
# multi-part rule (e.g. "TRGS 500 Teil 1"). See design spec, "Designation
# detection".
_DESIGNATION_SEARCH_PATTERN = re.compile(
    r"(?<![A-Z0-9])(TRGS|TRBS|TRBA)\s+(\d+(?:\s+Teil\s+\d+)?)(?![A-Z0-9])",
    re.IGNORECASE,
)
_FILENAME_DESIGNATION_PATTERN = re.compile(
    r"^baua_(TRGS|TRBS|TRBA)_(\d+)(?:_teil_(\d+))?(?:_.*)?$",
    re.IGNORECASE,
)

# BAuA PDFs can contain several cover and publication-information items before
# the designation. Keep the search in bounded front matter rather than
# accepting an arbitrary mention deep in the body.
_MAX_DESIGNATION_PAGE = 5
_MAX_DESIGNATION_CONTEXT_WORDS = 12

# BAuA's numbered sections use forms such as "1 Zielsetzung" and
# "2.1 Begriffsbestimmungen". A heading must be a short, standalone item;
# long numbered prose remains body text even when Docling assigns it a
# section-header label.
_NUMBERED_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)(?:\.)?\s+(.+)$")
_MAX_HEADING_WORDS = 14
_HEADING_LABELS = {"section_header", "list_item"}

# Publication titles are short. A continuously-set publication can merge the
# title and body into one Docling item, so title extraction is deliberately
# bounded and fails toward `None`; `full_text` retains the complete content.
_MAX_TITLE_WORDS = 12

# One glob per series so a directory holding several BAuA series -- or a
# neighbouring source's files, as the DGUV/EUR-Lex fixtures already share
# one -- is read correctly.
_FILE_PATTERNS = ("baua_trgs_*.pdf", "baua_trbs_*.pdf", "baua_trba_*.pdf")


def _page_numbers(item: object) -> set[int]:
    provenance = getattr(item, "prov", None) or []
    return {
        page_number
        for entry in provenance
        if isinstance((page_number := getattr(entry, "page_no", None)), int)
    }


def _item_label(item: object) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label)).lower()


def _numbered_heading(text: str, label: str) -> bool:
    """Return whether this compact Docling item is a BAuA section heading.

    SectionHeaderItems are the primary signal. Docling sometimes classifies
    numbered subheadings as ListItems, so accept those only for nested section
    numbers; a top-level numbered list item is too ambiguous to split on.
    """
    if label not in _HEADING_LABELS:
        return False
    normalized = " ".join(text.split())
    match = _NUMBERED_HEADING_PATTERN.fullmatch(normalized)
    if match is None:
        return False
    number, title = match.groups()
    words = title.split()
    if not words or len(words) > _MAX_HEADING_WORDS:
        return False
    if not words[0][:1].isupper():
        return False
    if title.endswith((".", "!", "?", ";", ":")):
        return False
    if label == "list_item" and "." not in number:
        return False
    return True


def _designation_hint_from_filename(pdf_path: Path) -> str | None:
    match = _FILENAME_DESIGNATION_PATTERN.match(pdf_path.stem)
    if match is None:
        return None
    series, number, part = match.groups()
    designation = f"{series.upper()} {number}"
    if part is not None:
        designation += f" Teil {part}"
    return designation


def _find_designation(
    items: list[object], *, filename_hint: str | None = None
) -> tuple[str, str | None]:
    """Find a unique designation in bounded front matter.

    The first Docling text item is often publication furniture. Search only
    the first few pages and a bounded number of leading words, and fail closed
    if that region names competing designations. A long merged text item is
    allowed so Docling's page-level merging does not hide a cover designation.
    An unidentifiable record is handed to the existing manual identity-review
    path rather than being assigned cover text as its identity.
    """
    candidates: list[tuple[str, str | None]] = []
    for index, item in enumerate(items):
        text = getattr(item, "text", None)
        if not text:
            continue
        normalized = " ".join(text.split())

        pages = _page_numbers(item)
        if pages and min(pages) > _MAX_DESIGNATION_PAGE:
            continue
        if not pages and index > 80:
            continue

        for match in _DESIGNATION_SEARCH_PATTERN.finditer(normalized):
            prefix_words = normalized[:match.start()].split()
            suffix = normalized[match.end():].strip()
            suffix_words = suffix.split()
            if len(prefix_words) > _MAX_DESIGNATION_CONTEXT_WORDS:
                continue

            designation = f"{match.group(1).upper()} {' '.join(match.group(2).split())}"
            title = None
            if match.start() == 0 and suffix_words:
                if len(suffix_words) <= _MAX_TITLE_WORDS and not suffix.endswith(
                    (".", "!", "?", ";", ":")
                ) and suffix_words[0][:1].isupper() and not re.search(
                    r"\b\d+(?:\.\d+)*\.?\s+\S", suffix
                ):
                    title = suffix
            candidates.append((designation, title))

    designations = {designation for designation, _title in candidates}
    if filename_hint is not None:
        # The operator's filename is only a candidate hint. Require the same
        # designation to be present in extracted front matter before using it.
        candidates = [
            candidate for candidate in candidates if candidate[0] == filename_hint
        ]
        designations = {designation for designation, _title in candidates}
    if len(designations) != 1:
        return "", None

    designation = next(iter(designations))
    title = next(
        (
            candidate_title
            for candidate, candidate_title in candidates
            if candidate == designation and candidate_title is not None
        ),
        None,
    )
    return designation, title


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
        items = list(document.iterate_items())
        item_objects = [item for item, _level in items]
        designation, title = _find_designation(
            item_objects, filename_hint=_designation_hint_from_filename(pdf_path)
        )

        # Preserve every extracted text item. A blank line before a verified
        # numbered heading carries the Docling boundary into RawRecord, whose
        # shared shape intentionally contains text but not Docling item labels.
        texts: list[str] = []
        for item in item_objects:
            text = getattr(item, "text", None)
            if not text:
                continue
            normalized = " ".join(text.split())
            if _numbered_heading(normalized, _item_label(item)):
                texts.append("")
            texts.append(normalized)

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
        if record.full_text is None:
            return []

        sections: list[RawSection] = []
        preamble: list[str] = []
        current_heading: str | None = None
        current_body: list[str] = []

        def _append_section(heading: str | None, body: list[str]) -> None:
            text = " ".join(line.strip() for line in body if line.strip())
            if text or heading is not None:
                sections.append(
                    RawSection(
                        sequence_number=len(sections) + 1,
                        heading=heading,
                        text=text,
                    )
                )

        lines = record.full_text.splitlines()
        previous_was_separator = True
        found_heading = False
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                previous_was_separator = True
                continue

            match = _NUMBERED_HEADING_PATTERN.fullmatch(line)
            heading = None
            if previous_was_separator and match is not None:
                _number, title = match.groups()
                words = title.split()
                if (
                    words
                    and len(words) <= _MAX_HEADING_WORDS
                    and words[0][:1].isupper()
                    and not title.endswith((".", "!", "?", ";", ":"))
                ):
                    heading = line

            if heading is not None:
                found_heading = True
                if current_heading is not None:
                    _append_section(current_heading, current_body)
                elif preamble:
                    _append_section(None, preamble)
                    preamble = []
                current_heading = heading
                current_body = []
            elif current_heading is None:
                preamble.append(line)
            else:
                current_body.append(line)
            previous_was_separator = False

        if current_heading is not None:
            _append_section(current_heading, current_body)
        elif preamble:
            _append_section(None, preamble)

        # If Docling emitted no confidently marked numbered headings, retain
        # the complete document as one segment as in phase 1.
        if not found_heading and record.full_text:
            return [
                RawSection(sequence_number=1, heading=None, text=record.full_text)
            ]
        return sections

    def classify_rights(self, record: RawRecord) -> RightsRule:
        # Narrower than the Protocol's `RightsRule | None` on purpose: every
        # TRGS/TRBS/TRBA is an amtliche Bekanntmachung (official announcement), so
        # this source is always classifiable and never hands the runner a "cannot
        # classify". See design spec, "Legal basis: category A".
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=True,
            may_cite_passages=True, may_export_free=True,
            legal_basis_reference=(
                "§ 5 UrhG — amtliche Bekanntmachung (TRGS/TRBS/TRBA, BAuA im GMBl)"
            ),
        )
