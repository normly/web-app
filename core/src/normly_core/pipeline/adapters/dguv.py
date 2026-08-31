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

# A paragraph marker: "§ 1", "§ 12", occasionally "§ 2a" in German legal
# numbering. Kept as one building block so the heading matcher below and the
# splitter in _logical_lines() can never drift apart.
_PARAGRAPH_MARKER = r"§\s*\d+[a-z]?"

# A heading line is a paragraph marker, optionally followed by its title.
# The title is optional on purpose: _split_paragraph_run() falls back to a bare
# marker heading when it cannot tell title from body text (see there), and
# real publications also set the marker and its title on two separate lines.
_HEADING_PATTERN = re.compile(rf"^{_PARAGRAPH_MARKER}(?:\s+\S.*)?$")

_MARKER_PATTERN = re.compile(_PARAGRAPH_MARKER)

_SENTENCE_END = (".", "!", "?")

# A §-heading's title is a noun phrase and never runs longer than this. The cap
# only bounds the search for the title/body boundary below; exceeding it means
# "no confident boundary found", not "cut here".
_MAX_HEADING_WORDS = 10

# German capitalises nouns, so a capitalised word is either a noun or the first
# word of a sentence. A capitalised word from this closed class of non-nouns is
# therefore a sentence start -- the cue used to find where a §-heading's title
# ends and its body begins inside one merged Docling text item. Lower-case
# occurrences ("Pflichten des Unternehmers") never match: the check requires an
# upper-case initial.
_SENTENCE_OPENERS = frozenset(
    """
    der die das dem den des dieser diese dieses diesem diesen
    ein eine einer eines einem einen kein keine keiner keinem keinen
    er sie es wer was welche welcher wenn sofern soweit solange während falls
    alle allen aller jeder jede jedes jedem jeden beide beiden
    bei für fuer nach vor zur zum im in an auf aus mit ohne über ueber unter
    durch gegen je pro von vom beim am ab bis neben seit trotz um zu
    und oder sowie auch als ferner außerdem ausserdem zusätzlich zusaetzlich
    darüber darueber daneben dabei dazu dadurch damit deshalb daher somit
    hierzu hierfür hierfuer insbesondere weiterhin ergänzend ergaenzend
    abweichend entsprechend zusammen gemeinsam
    ist sind war waren hat haben muss müssen muessen kann können koennen
    darf dürfen duerfen soll sollen wird werden gilt gelten liegt liegen
    """.split()
)

# Reference syntax: a "§ 5" inside running text is a cross-reference, not a new
# heading, and these are the words that typically follow one. Splitting on them
# would fabricate a section out of a sentence's middle.
_REFERENCE_FOLLOWERS = frozenset(
    {"absatz", "abs", "abs.", "satz", "nr", "nr.", "nummer", "buchstabe", "ff", "ff."}
)

# Docling merges visually adjacent lines into one text block -- designation
# ("DGUV Vorschrift 1") and title ("Grundsätze der Prävention") are two
# separate lines in the source PDF but arrive as a single Docling text item,
# unlike pdfplumber's per-line output. _logical_lines() restores the line
# breaks it can recognise (§-headings); the designation and its title carry no
# such marker, so they are split back apart here by the designation's known
# prefix rather than by assuming two separate elements.
#
# Covers both of DGUV's real numbering conventions (see
# https://publikationen.dguv.de/regelwerk/): "DGUV Vorschrift <N>" uses a
# plain running number (Vorschrift 1, Vorschrift 2, ...); "DGUV Regel",
# "DGUV Information", and "DGUV Grundsatz" instead use a "<NNN>-<NNN>"
# scheme where the first three digits mark the publication series (Regeln
# 100-xxx, Informationen 2xx-xxx, Grundsätze 3xx-xxx) -- e.g. "DGUV Regel
# 100-001", "DGUV Information 204-022", "DGUV Grundsatz 314-003".
_DESIGNATION_PATTERN = re.compile(
    r"^(DGUV (?:Vorschrift \d+|(?:Regel|Information|Grundsatz) \d{3}-\d{3}))\s*(.*)$"
)

# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of DGUV publications.
_FILE_PATTERN = "dguv_*.pdf"


def _is_heading_start(text: str, match: re.Match[str]) -> bool:
    """Does this paragraph marker start a heading, or is it a cross-reference?

    Both look identical to a regex; what separates them is their surroundings.
    A heading is followed by its title -- a capitalised noun -- and preceded
    either by nothing, by the end of the previous section's last sentence, or
    by the publication's title line. A cross-reference sits inside a sentence:
    it is introduced by a lower-case word ("nach § 5", "gemäß § 12") and
    followed either by a lower-case word or by reference syntax ("§ 5 Absatz
    2").
    """
    following = text[match.end() :].lstrip().split(" ", 1)[0]
    if not following[:1].isupper():
        return False
    if following.rstrip(",.;:").lower() in _REFERENCE_FOLLOWERS:
        return False

    preceding = text[: match.start()].rstrip()
    if not preceding:
        return True
    previous_word = preceding.rsplit(" ", 1)[-1]
    if previous_word.endswith(_SENTENCE_END):
        return True
    # A lower-case word before the marker means the marker is part of that
    # sentence, so it cannot be a heading.
    return not previous_word[:1].islower()


def _split_paragraph_run(run: str) -> list[str]:
    """Split one "§ N ..." run into a heading line and, if present, a body line.

    Docling hands over whatever its layout model considered one block. That is
    a single line ("§ 1 Geltungsbereich") for a PDF whose paragraphs are set
    apart by blank lines, but a whole continuously-set page -- heading and body
    glued together with spaces -- for one that is not. Both shapes reach this
    function; the line break between title and body has to be reconstructed.
    """
    marker_match = _MARKER_PATTERN.match(run)
    assert marker_match is not None
    marker = f"§ {run[marker_match.start() : marker_match.end()].lstrip('§').strip()}"
    words = run[marker_match.end() :].split()
    if not words:
        return [marker]

    # Where does the title end? A capitalised sentence opener starts the body.
    # The title's own first word is skipped: it is the title, whatever it is.
    boundary: int | None = None
    for index, word in enumerate(words[: _MAX_HEADING_WORDS + 1]):
        if index == 0:
            continue
        if word[:1].isupper() and word.strip(",.;:()").lower() in _SENTENCE_OPENERS:
            boundary = index
            break
        if word.endswith(_SENTENCE_END):
            # A sentence ended before any opener was found: past this point
            # everything is body text, so no boundary can be recovered.
            break

    if boundary is not None:
        return [f"{marker} {' '.join(words[:boundary])}", " ".join(words[boundary:])]

    if len(words) <= _MAX_HEADING_WORDS and not any(
        word.endswith(_SENTENCE_END) for word in words
    ):
        # No sentence in sight and short enough: the whole run is a heading --
        # the shape Docling produces for a PDF with blank lines between
        # paragraphs, where one text item really is one line.
        return [f"{marker} {' '.join(words)}"]

    # Body text is in here but the boundary is not recoverable. Keep the marker
    # as the heading and hand the rest over as body: a bare "§ N" heading is
    # less useful than the real one, but nothing is lost or invented.
    return [marker, " ".join(words)]


def _logical_lines(text: str) -> list[str]:
    """Rebuild the logical lines of one Docling text item.

    Docling's layout model merges visually adjacent lines into a single text
    item, and how much it merges depends on the source PDF's spacing -- from
    one item per line to one item per page. This restores the line structure
    extract_structure() needs, using the §-paragraph markers Docling's own
    element classification does not reliably expose (it labels them ListItem;
    see tests/pipeline/test_dguv_adapter.py).
    """
    text = " ".join(text.split())
    if not text:
        return []

    starts = [
        match for match in _MARKER_PATTERN.finditer(text) if _is_heading_start(text, match)
    ]
    if not starts:
        return [text]

    lines = []
    lead = text[: starts[0].start()].strip()
    if lead:
        lines.append(lead)
    for position, match in enumerate(starts):
        end = starts[position + 1].start() if position + 1 < len(starts) else len(text)
        lines.extend(_split_paragraph_run(text[match.start() : end].strip()))
    return lines


class DguvAdapter:
    def __init__(self, *, directory: Path, source_id: uuid.UUID):
        self.directory = directory
        self.source_id = source_id

    def fetch(self) -> Iterable[RawRecord]:
        for pdf_path in sorted(self.directory.glob(_FILE_PATTERN)):
            content = pdf_path.read_bytes()
            content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

            document = extract_document(pdf_path)
            lines: list[str] = []
            for item, _level in document.iterate_items():
                text = getattr(item, "text", None)
                if text:
                    lines.extend(_logical_lines(text))

            first = lines[0] if lines else ""
            match = _DESIGNATION_PATTERN.match(first)
            if match:
                designation = match.group(1)
                title = match.group(2).strip() or None
            else:
                designation = first
                title = None
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
