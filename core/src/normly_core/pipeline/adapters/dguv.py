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
from normly_core.graph.domain import EdgeType
from normly_core.pipeline.domain import RawRecord, RawReference, RawSection, RightsRule

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
#
# Being a word list, it is necessarily incomplete, so it is only ever used
# where a missing word cannot fabricate anything:
#
# * _split_paragraph_run(), inside a run whose heading is already confirmed --
#   a missing opener costs a bare "§ N" heading instead of the full one.
# * _is_publication_title_line(), as one rejection test among several -- a
#   missing opener there is caught by the structural rules beside it, and a
#   heading is never admitted *because* a word is absent from this list.
#
# _is_heading_start() itself does not consult it: deciding a heading on "the
# word in front is not in this list" is what the designation test replaced --
# see the note there.
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
    abweichend entsprechend zusammen gemeinsam gemäß gemaess gemäss
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

# Real publications set an issue date between designation and title ("DGUV
# Vorschrift 1 vom 1. November 2013 Grundsätze der Prävention"). It is the only
# thing allowed to stand where the title's first word would otherwise be --
# deliberately matched by an explicit shape rather than by "skip leading
# lower-case words", which would also let a verb through and readmit "DGUV
# Vorschrift 1 gilt in Verbindung mit ArbSchG § 5 ..." as a title line.
_ISSUE_DATE_PREFIX = re.compile(
    r"^vom\s+(?:\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\d{1,2}\.\s*\w+\s+\d{4})\s*"
)

# The Inkrafttreten/Außerkrafttreten section's heading -- matched by
# substring, case-insensitively, since the exact surrounding wording
# ("Inkrafttreten/Außerkrafttreten" vs. a future publication phrasing it
# slightly differently) is not itself the signal; "inkrafttreten" appearing
# in a §-heading reliably is.
_TAKES_EFFECT_HEADING = re.compile("inkrafttreten", re.IGNORECASE)

# Isolates the clause naming whoever is being retired: "tritt ... außer
# Kraft" is this section's one fixed phrase for it, regardless of how the
# surrounding sentence is otherwise worded ("Gleichzeitig tritt ... außer
# Kraft", "... tritt gleichzeitig außer Kraft", etc.) -- non-greedy so it
# stops at the FIRST "außer Kraft" rather than swallowing the rest of the
# section if the phrase repeats.
_RETIRING_CLAUSE = re.compile(r"tritt\s+(.+?)\s+außer\s+Kraft", re.IGNORECASE | re.DOTALL)

# A predecessor named by its own modern DGUV designation (rare today, common
# once this system re-ingests a later edition of an already-known
# Vorschrift/Regel/Information/Grundsatz) -- reuses _DESIGNATION_PATTERN's
# own designation shape, unanchored so it can be found anywhere inside the
# retiring clause rather than only at its start.
_MODERN_PREDECESSOR = re.compile(
    r"DGUV (?:Vorschrift \d+|(?:Regel|Information|Grundsatz) \d{3}-\d{3})"
)

# The far more common case: a predecessor from before the DGUV numbering
# reform, named only by its free-text title in quotes ("„Bauarbeiten"" in a
# real, professionally typeset PDF; a reportlab-generated test fixture's
# Helvetica font cannot render „/" at all and collapses both to a plain "'"
# -- _normalise_quotes() below unifies every quote-like character to "'"
# before this pattern ever runs, so it only has to handle one form.
_QUOTED_PREDECESSOR_TITLE = re.compile(r"'([^']+)'")

# Every quote-like character this text might contain, normalised to a
# single straight apostrophe before pattern-matching: German „low-high"
# double quotes and their single-quote counterpart (‚...') as real PDFs set
# them, plain typographic single quotes ('...'), and the plain ASCII quotes
# a reportlab-generated fixture actually produces.
_QUOTE_CHARACTERS = "„“‚‘’\"'"


def _normalise_quotes(text: str) -> str:
    for character in _QUOTE_CHARACTERS:
        text = text.replace(character, "'")
    return text


def _extract_predecessor_reference(lines: list[str]) -> RawReference | None:
    """Find the Inkrafttreten/Außerkrafttreten section within an already
    logical-line-split document (see `_logical_lines`) and, if it names a
    predecessor being retired, return the RawReference for it.

    Mirrors extract_structure()'s own heading-boundary walk (a section runs
    from its own heading line up to, but not including, the next heading
    line) rather than diverging from it -- this has to run here, before
    `RawRecord` is constructed, since `RawRecord` is frozen and
    `extract_structure()` itself is only called later, separately, by the
    runner.
    """
    section_body: list[str] = []
    in_target_section = False
    for line in lines:
        if _HEADING_PATTERN.match(line):
            if in_target_section:
                break
            in_target_section = bool(_TAKES_EFFECT_HEADING.search(line))
            continue
        if in_target_section:
            section_body.append(line)

    if not section_body:
        return None

    text = " ".join(section_body)
    clause_match = _RETIRING_CLAUSE.search(text)
    if clause_match is None:
        return None
    clause = clause_match.group(1)

    modern_match = _MODERN_PREDECESSOR.search(clause)
    if modern_match is not None:
        return RawReference(
            target_issuer="DGUV", target_designation=modern_match.group(0),
            edge_type=EdgeType.REPLACES,
        )

    quoted_match = _QUOTED_PREDECESSOR_TITLE.search(_normalise_quotes(clause))
    if quoted_match is not None:
        return RawReference(
            target_issuer="DGUV", target_designation=quoted_match.group(1),
            edge_type=EdgeType.REPLACES,
        )

    return None


# The adapter reads every file in the directory that carries its own prefix.
# A bare "*.pdf" would be wrong: the directory may hold other sources' files —
# the test fixtures for both adapters already share one — and this adapter can
# only make sense of DGUV publications.
_FILE_PATTERN = "dguv_*.pdf"


def _is_publication_title_line(lead: str) -> bool:
    """Is this lead text the publication's own designation-and-title line?

    `_DESIGNATION_PATTERN` alone cannot answer that: its tail is `\\s*(.*)$`,
    so it accepts anything glued behind the designation number, including a
    whole second sentence ("DGUV Vorschrift 1 Grundsätze der Prävention
    Ausweislich § 14 ArbSchG trägt ..."). The tail therefore has to look like a
    title as well, and a DGUV title is a plain noun phrase:

    * it opens with a capitalised word -- its head noun -- with only an issue
      date allowed in front. A designation continued by prose opens with a verb
      instead ("DGUV Vorschrift 1 regelt ...", "... nennt folgende ...").
    * it stays within the length a heading title stays within.
    * German capitalises nouns and nothing else, so inside a noun phrase the
      capitalised words are separated by lower-case function words ("Grundsätze
      der Prävention", "Betriebsärzte und Fachkräfte für Arbeitssicherheit").
      Two capitalised words in a row therefore mark a new constituent -- a
      sentence starting behind the title ("... der Prävention Ausweislich § 14
      ...", "... im Betrieb Laut § 5 ..."). The title's own first two words are
      exempt: a title's opening word is capitalised whatever it is, so an
      adjective may legitimately stand before its noun there ("Erste Hilfe im
      Betrieb").
    * it contains no capitalised sentence opener beyond its own first word.
      That word list is incomplete by construction (see `_SENTENCE_OPENERS`) --
      it is one test among several here, never the test, and the structural
      rule above is what catches the openers it does not know.
    """
    match = _DESIGNATION_PATTERN.match(lead)
    if match is None:
        return False
    tail = _ISSUE_DATE_PREFIX.sub("", match.group(2).strip(), count=1)
    words = tail.split()
    if not words:
        # Designation alone on the line; the title is set elsewhere or absent.
        return True
    if not words[0][:1].isupper():
        return False
    if len(words) > _MAX_HEADING_WORDS:
        return False
    if any(
        word[:1].isupper() and previous[:1].isupper()
        for previous, word in zip(words[1:], words[2:])
    ):
        return False
    return not any(
        word[:1].isupper() and word.strip(",.;:()").lower() in _SENTENCE_OPENERS
        for word in words[1:]
    )


def _heading_has_a_title(run: str) -> bool:
    """Does the text behind this marker separate into a title and a body?

    The evidence on the marker's other side. `_split_paragraph_run()` falls
    back to a bare "§ N" heading whenever it cannot tell one from the other,
    and that is exactly what happens when the marker is a cross-reference and
    everything behind it is the rest of a sentence ("§ 14 ArbSchG trägt der
    Unternehmer die Kosten.").
    """
    return _MARKER_PATTERN.fullmatch(_split_paragraph_run(run)[0]) is None


def _is_heading_start(text: str, match: re.Match[str], *, is_first_marker: bool) -> bool:
    """Does this paragraph marker start a heading, or is it a cross-reference?

    Both look identical to a regex; what separates them is their surroundings.
    A heading is followed by its title -- a capitalised noun -- and preceded
    either by nothing, by the end of the previous section's last sentence, or
    by the publication's title line. A cross-reference sits inside a sentence:
    it is introduced by a lower-case word ("nach § 5", "gemäß § 12") and
    followed either by a lower-case word or by reference syntax ("§ 5 Absatz
    2").

    The title line is the awkward case: it ends in a capitalised noun with no
    full stop ("... Grundsätze der Prävention § 1 Geltungsbereich"), so a
    capitalised word before the marker has to be allowed to precede a heading.
    That allowance is deliberately kept as narrow as the case that needs it:

    * `is_first_marker` -- only the item's *first* marker can be preceded by
      the publication's own title. Every later marker in the same item sits
      after body text, where a capitalised word before a "§" is a sentence
      start, not a title tail ("... zu tragen. Nach § 14 DGUV Vorschrift 1
      ...", "Ausweislich § 3 ..."), so those require a real sentence boundary.
    * `_is_publication_title_line()` -- and even the first marker must actually
      have that title line in front of it: the lead text must be the
      publication's designation *and nothing but its title* ("DGUV Vorschrift 1
      Grundsätze der Prävention § 1 ..."). Anything else in front of a first
      marker is a sentence. Testing the designation alone was not enough: a
      sentence glued onto the title with no punctuation between them ("... der
      Prävention Ausweislich § 14 ArbSchG trägt ...") still opens with the
      designation, so the title's own shape has to be checked as well.
    * `_heading_has_a_title()` -- and the allowance wants corroboration from
      the marker's other side too. It exists for a heading, and a heading is a
      marker plus its title; where no title can be told apart from what follows
      the marker, nothing supports splitting here.

    The designation test replaces an earlier attempt that instead rejected a
    known list of sentence-opening words (`_SENTENCE_OPENERS`). That direction
    cannot be finished: it closed "Nach § 14 ..." and "Gemäß § 12 ..." but not
    "Ausweislich § 14 ...", not the ß-less "Gemäss § 12 ...", and by
    construction not "Es gelten folgende Vorschriften: § 14 ...", where the
    word before the marker is a capitalised noun like a title's last word.
    Asking instead for the one shape the allowance exists for turns an
    open-ended exclusion list into a closed positive match.

    `_DESIGNATION_PATTERN` is anchored and applied with `.match()`. The anchor
    is what does the work: cover text before the designation denies the
    allowance, so a sentence that merely names a publication ("... nach der
    DGUV Vorschrift 1 § 5 ...") cannot readmit the fabrication. `.search()`
    would behave identically here -- the pattern carries `^` and no MULTILINE
    flag, and the lead text is newline-free by the time it arrives (see
    _logical_lines(), which joins on spaces) -- so `.match()` is chosen only
    for saying plainly what the pattern already requires. The same anchored
    assumption carries the designation/title split in _fetch_file(), where such
    an item would be misread first anyway.

    Every guard fails towards "not a heading". The cost of that is a section
    whose heading is not recognised -- its text is kept, merged into what
    precedes it. The cost of the opposite error is a fabricated section, the
    sentence's opening word orphaned into the previous one, and the rest of a
    perfectly ordinary sentence filed under a heading that does not exist.
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
    if previous_word[:1].islower():
        return False
    if not is_first_marker:
        return False
    if not _is_publication_title_line(preceding):
        return False
    # The run this marker would open, bounded by the next marker: what lies
    # beyond that belongs to the next run either way, and shortening the text
    # under test cannot invent a title where there is none.
    next_marker = _MARKER_PATTERN.search(text, match.end())
    run_end = next_marker.start() if next_marker else len(text)
    return _heading_has_a_title(text[match.start() : run_end].strip())


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

    # "First marker" is counted over every marker in the item, not over the
    # ones that turned out to be headings: what the allowance in
    # _is_heading_start() exists for is a marker that can still have the
    # publication's title in front of it, and only the very first one can.
    starts = [
        match
        for position, match in enumerate(_MARKER_PATTERN.finditer(text))
        if _is_heading_start(text, match, is_first_marker=position == 0)
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

        document = extract_document(pdf_path)
        lines: list[str] = []
        for item, _level in document.iterate_items():
            text = getattr(item, "text", None)
            if text:
                lines.extend(_logical_lines(text))

        predecessor_reference = _extract_predecessor_reference(lines)

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
            raw_references=[predecessor_reference] if predecessor_reference else [],
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
