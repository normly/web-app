# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest

from normly_core.pipeline.adapters.dguv import DguvAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_fetch_yields_one_record_per_pdf_with_full_text():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())

    records = list(adapter.fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == "DGUV Vorschrift 1"
    assert record.raw_issuer == "DGUV"
    assert record.raw_title == "Grundsätze der Prävention"
    assert record.full_text is not None
    assert "§ 1 Geltungsbereich" in record.full_text
    assert record.language == "de"


def _write_publication_pdf(path, designation: str, title: str) -> None:
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    lines = [
        designation,
        title,
        "",
        "§ 1 Geltungsbereich",
        "Diese Vorschrift gilt für alle Unternehmen und Versicherte.",
    ]
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()


def _write_publication_pdf_with_sections(path, designation: str, title: str, sections: list[tuple[str, str]]) -> None:
    """Like `_write_publication_pdf`, but with an arbitrary list of
    (heading, body) sections instead of the fixed single `§ 1
    Geltungsbereich`. `heading` must already include its `§ N` marker,
    e.g. `"§ 13 Inkrafttreten/Außerkrafttreten"`.

    `body` is word-wrapped before being drawn: `canvas.drawString` never
    wraps on its own, and this task's own Inkrafttreten/Außerkrafttreten
    body sentences run well past the page's printable width (confirmed
    empirically -- an unwrapped long line gets silently clipped mid-word
    by Docling's extraction, since it never appears in the rendered page).
    Wrapping at word boundaries and drawing each wrapped line separately
    keeps every word inside the page; `_logical_lines()` already merges
    such continuation lines back into one logical line (see
    `_write_continuous_publication_pdf`, which relies on the same
    Docling behaviour for its own multi-line body text).
    """
    import textwrap

    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    lines = [designation, title, ""]
    for heading, body in sections:
        lines.append(heading)
        lines.extend(textwrap.wrap(body, width=70) or [body])
        lines.append("")
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()


def test_fetch_captures_the_issue_date_as_edition(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf",
        "DGUV Vorschrift 1",
        "vom 1. November 2013 Grundsätze der Prävention",
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition == "2013-11-01"
    assert records[0].raw_title == "Grundsätze der Prävention"


def test_fetch_captures_a_numeric_issue_date_as_edition(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_2.pdf",
        "DGUV Vorschrift 2",
        "vom 1.6.2022 Betriebsärzte und Fachkräfte für Arbeitssicherheit",
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition == "2022-06-01"
    assert records[0].raw_title == "Betriebsärzte und Fachkräfte für Arbeitssicherheit"


def test_fetch_leaves_edition_none_when_no_issue_date_is_present(tmp_path):
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_3.pdf", "DGUV Vorschrift 3", "Erste Hilfe"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].edition is None
    assert records[0].raw_title == "Erste Hilfe"


def test_fetch_attaches_a_replaces_reference_for_a_modern_designation_predecessor(tmp_path):
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_2.pdf",
        "DGUV Vorschrift 2",
        "Betriebsärzte und Fachkräfte für Arbeitssicherheit",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Dezember 2025 in Kraft. "
                "Gleichzeitig tritt die DGUV Vorschrift 2 vom 1. Januar 2011 außer Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    references = records[0].raw_references
    assert len(references) == 1
    assert references[0].target_issuer == "DGUV"
    assert references[0].target_designation == "DGUV Vorschrift 2"
    from normly_core.graph.domain import EdgeType
    assert references[0].edge_type == EdgeType.REPLACES


def test_fetch_attaches_a_replaces_reference_for_a_free_text_title_predecessor(tmp_path):
    # The successor's OWN title is deliberately two words ("Bauarbeiten
    # allgemein"), not the single word "Bauarbeiten" the real-world
    # predecessor is quoted under in the body text below: verified directly
    # against this project's own Docling extraction that with a single-word
    # title, the entire designation+title block gets excluded from
    # `document.iterate_items()`'s default iteration (not merely the title
    # being misclassified as a page header -- the mechanism is less precisely
    # characterized than that; what's confirmed is that `_fetch_file`'s
    # `lines[0]` ends up holding the "§ 13 Inkrafttreten/Außerkrafttreten"
    # heading text instead of the designation when this happens), so
    # `raw_designation` comes out wrong. A two-word title avoids this. This
    # is a fixture-generation quirk of this specific synthetic PDF layout,
    # unrelated to the predecessor-detection regexes under test.
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_38.pdf",
        "DGUV Vorschrift 38",
        "Bauarbeiten allgemein",
        [
            (
                "§ 13 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am ersten Tag des auf die "
                "Veroeffentlichung folgenden Monats in Kraft. Gleichzeitig tritt die "
                "Unfallverhuetungsvorschrift 'Bauarbeiten' vom September 1976 in der "
                "Fassung vom Januar 1997 außer Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_designation == "DGUV Vorschrift 38"
    references = records[0].raw_references
    assert len(references) == 1
    assert references[0].target_issuer == "DGUV"
    assert references[0].target_designation == "Bauarbeiten"
    from normly_core.graph.domain import EdgeType
    assert references[0].edge_type == EdgeType.REPLACES


def test_fetch_attaches_no_reference_when_there_is_no_inkrafttreten_section(tmp_path):
    """A first edition, or any Vorschrift whose PDF simply lacks this
    section, must not error and must not fabricate a reference."""
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_references == []


def test_fetch_attaches_no_reference_when_the_section_names_no_predecessor(tmp_path):
    """An Inkrafttreten/Außerkrafttreten section can exist and simply not
    retire anything (a genuine first edition still states when it takes
    effect) -- no 'tritt ... außer Kraft' clause means no match, not an
    error."""
    _write_publication_pdf_with_sections(
        tmp_path / "dguv_vorschrift_5.pdf",
        "DGUV Vorschrift 5",
        "Erste Hilfe",
        [
            (
                "§ 9 Inkrafttreten/Außerkrafttreten",
                "Diese Unfallverhuetungsvorschrift tritt am 1. Januar 2026 in Kraft.",
            ),
        ],
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_references == []


def test_fetch_processes_every_matching_file_in_the_directory(tmp_path):
    """`--directory` means the directory, not one hardcoded filename in it."""
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_2.pdf", "DGUV Vorschrift 2", "Betriebsärzte"
    )
    # A neighbouring source's file in the same directory stays untouched.
    _write_publication_pdf(tmp_path / "eur_lex_something.pdf", "2006/42/EC", "Machinery")

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert [record.raw_designation for record in records] == [
        "DGUV Vorschrift 1",
        "DGUV Vorschrift 2",
    ]
    assert len({record.content_hash for record in records}) == 2


def test_fetch_skips_an_unreadable_file_and_keeps_reading_the_rest(tmp_path, capsys):
    """One bad record must block only itself -- the runner's guarantee. It
    cannot hold for a file that fails inside fetch(): the runner meets that
    error while pulling the next record, outside its per-record guard, and a
    generator that raised cannot be resumed. So the adapter isolates it, and
    says so on stderr rather than skipping in silence."""
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )
    (tmp_path / "dguv_vorschrift_2.pdf").write_text("this is not a PDF")
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_3.pdf", "DGUV Vorschrift 3", "Betriebsärzte"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert [record.raw_designation for record in records] == [
        "DGUV Vorschrift 1",
        "DGUV Vorschrift 3",
    ]
    assert "dguv_vorschrift_2.pdf" in capsys.readouterr().err


def test_fetch_does_not_skip_a_misconfigured_pipeline(tmp_path, capsys, monkeypatch):
    """A broken deployment must end the run, not be skipped once per file.

    The per-file skip above and the eager pipeline check in
    docling_extraction.py meet here: NORMLY_DOCLING_ARTIFACTS_PATH pointing at
    a path with no models fails identically for every file, so a per-file
    `except` would skip all of them and let the run finish with exit code 0, a
    success line, and zero records ingested -- an unattended production run
    with a broken deployment looking exactly like a healthy one. The failure
    is a separate exception class so this cannot happen.
    """
    from normly_core.pipeline import docling_extraction
    from normly_core.pipeline.docling_extraction import PipelineInitializationError

    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_2.pdf", "DGUV Vorschrift 2", "Betriebsärzte"
    )

    monkeypatch.setenv("NORMLY_DOCLING_ARTIFACTS_PATH", str(tmp_path / "no_models_here"))
    docling_extraction._converters.clear()
    try:
        with pytest.raises(PipelineInitializationError):
            list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())
    finally:
        # The bogus path is never cached (only a usable converter is), but the
        # cache was cleared to force a rebuild, so leave it empty rather than
        # holding a converter the next test believes it built.
        docling_extraction._converters.clear()

    # Not reported as a skipped file either: skipping is what it must not do.
    assert "skipping" not in capsys.readouterr().err


def test_fetch_splits_designation_and_title_for_a_dguv_regel(tmp_path):
    """The designation/title split must not be Vorschrift-specific: DGUV
    also publishes Regeln, Informationen, and Grundsätze under a distinct
    "<NNN>-<NNN>" numbering scheme (e.g. "DGUV Regel 100-001"), and this
    adapter's own file pattern and stated scope claim to handle any DGUV
    publication, not just Vorschriften."""
    _write_publication_pdf(
        tmp_path / "dguv_regel_100_001.pdf", "DGUV Regel 100-001", "Grundsätze der Prävention"
    )

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    assert records[0].raw_designation == "DGUV Regel 100-001"
    assert records[0].raw_title == "Grundsätze der Prävention"


def test_extract_structure_splits_on_paragraph_headings():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    sections = adapter.extract_structure(record)

    assert len(sections) == 3
    assert sections[0].heading == "§ 1 Geltungsbereich"
    assert "Diese Vorschrift gilt" in sections[0].text
    assert sections[1].heading == "§ 2 Pflichten des Unternehmers"
    assert sections[2].heading == "§ 3 Pflichten der Versicherten"
    assert [s.sequence_number for s in sections] == [1, 2, 3]


def _write_continuous_publication_pdf(path) -> None:
    """A DGUV-style publication set continuously -- no blank spacer lines.

    The committed fixture separates its paragraphs with blank lines, which
    makes Docling's layout model emit one text item per line. A normally set
    publication has no such spacers, and Docling then merges the whole page
    into a single text item (verified against Docling 2.123.1). Both shapes
    occur in a real corpus, depending on how the PDF was authored.
    """
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    lines = [
        "DGUV Vorschrift 1",
        "Grundsätze der Prävention",
        "§ 1 Geltungsbereich",
        "Diese Vorschrift gilt für alle Unternehmen und Versicherte.",
        "Sie gilt ferner für Bildungseinrichtungen.",
        "§ 2 Pflichten des Unternehmers",
        "Der Unternehmer hat die erforderlichen Maßnahmen zur Verhütung von",
        "Arbeitsunfällen zu treffen.",
        "§ 3 Pflichten der Versicherten",
        "Die Versicherten haben die Anweisungen des Unternehmers zu befolgen.",
    ]
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()


def test_fetch_splits_a_continuously_set_publication_docling_merges_into_one_item(tmp_path):
    """The realistic layout: no blank lines, so Docling returns the entire page
    as a single merged text item. Reading structure off item boundaries alone
    then finds nothing -- designation, title and every § end up glued into one
    blob. The line structure has to be rebuilt from the §-markers."""
    _write_continuous_publication_pdf(tmp_path / "dguv_vorschrift_1.pdf")
    adapter = DguvAdapter(directory=tmp_path, source_id=uuid.uuid4())

    record = list(adapter.fetch())[0]

    assert record.raw_designation == "DGUV Vorschrift 1"
    assert record.raw_title == "Grundsätze der Prävention"

    sections = adapter.extract_structure(record)
    assert [section.heading for section in sections] == [
        "§ 1 Geltungsbereich",
        "§ 2 Pflichten des Unternehmers",
        "§ 3 Pflichten der Versicherten",
    ]
    assert [section.sequence_number for section in sections] == [1, 2, 3]
    assert sections[0].text.startswith("Diese Vorschrift gilt für alle Unternehmen")
    assert "Bildungseinrichtungen" in sections[0].text
    assert "Arbeitsunfällen zu treffen" in sections[1].text
    assert "Anweisungen des Unternehmers" in sections[2].text


def test_logical_lines_keeps_a_single_heading_line_intact():
    """The other shape: one Docling item that already is exactly one line."""
    from normly_core.pipeline.adapters.dguv import _logical_lines

    assert _logical_lines("§ 1 Geltungsbereich") == ["§ 1 Geltungsbereich"]
    assert _logical_lines("§ 2 Pflichten des Unternehmers") == [
        "§ 2 Pflichten des Unternehmers"
    ]


def test_logical_lines_does_not_split_at_a_cross_reference():
    """"§ 5" inside a sentence is a reference, not a heading -- splitting there
    would fabricate a section out of the middle of a paragraph."""
    from normly_core.pipeline.adapters.dguv import _logical_lines

    body = "Der Unternehmer hat nach § 5 Absatz 2 die Versicherten zu unterweisen."

    assert _logical_lines(body) == [body]


def test_logical_lines_does_not_split_at_a_cross_reference_opening_a_sentence():
    """The reference guard cannot only look at what follows the marker.

    "§ 5 Absatz 2" is caught by _REFERENCE_FOLLOWERS, but a cross-reference
    that names its regulation instead of a subsection is followed by a
    capitalised word like any heading ("§ 14 DGUV Vorschrift 1", "§ 12
    ArbSchG"). What is in front of the marker then has to decide -- and both
    sentences below open with a capitalised word only because they open a
    sentence, not because a title ended there. Splitting here would invent a
    section, orphan the sentence's first word into whatever preceded it, and
    file the rest of the sentence under a heading that does not exist.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    first = "Nach § 14 DGUV Vorschrift 1 hat der Unternehmer die Kosten zu tragen."
    assert _logical_lines(first) == [first]

    second = "Die Regel gilt. Gemäß § 12 ArbSchG sind Maßnahmen zu treffen."
    assert _logical_lines(second) == [second]


def test_logical_lines_does_not_split_at_a_cross_reference_inside_a_section_body():
    """The same shape, but deep inside an item that already has real headings.

    The allowance for a capitalised word before a marker exists for exactly
    one thing: the publication's own title line, which can only ever sit
    before the *first* marker of an item. A marker further in is preceded by
    body text, so it needs a real sentence boundary -- otherwise every
    "Ausweislich § 3 ..." in a section's own prose starts a phantom section
    and steals the rest of the paragraph from the section it belongs to.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    text = (
        "DGUV Vorschrift 1 Grundsätze der Prävention "
        "§ 1 Geltungsbereich Diese Vorschrift gilt für alle Unternehmen. "
        "§ 2 Pflichten des Unternehmers Der Unternehmer trifft die Maßnahmen. "
        "Ausweislich § 14 DGUV Vorschrift 1 trägt er die Kosten."
    )

    assert _logical_lines(text) == [
        "DGUV Vorschrift 1 Grundsätze der Prävention",
        "§ 1 Geltungsbereich",
        "Diese Vorschrift gilt für alle Unternehmen.",
        "§ 2 Pflichten des Unternehmers",
        "Der Unternehmer trifft die Maßnahmen. "
        "Ausweislich § 14 DGUV Vorschrift 1 trägt er die Kosten.",
    ]


def test_logical_lines_still_splits_the_publications_own_title_line():
    """The case the capitalised-word allowance was built for, kept working.

    "Grundsätze der Prävention" ends the title with a noun and no full stop,
    so the first marker really is preceded by a capitalised word and really is
    a heading. Narrowing the allowance must not take this away.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    assert _logical_lines(
        "DGUV Vorschrift 1 Grundsätze der Prävention § 1 Geltungsbereich"
    ) == ["DGUV Vorschrift 1 Grundsätze der Prävention", "§ 1 Geltungsbereich"]


def test_logical_lines_does_not_split_at_a_cross_reference_opened_by_an_unlisted_word():
    """The allowance may not depend on a list of known sentence openers.

    Any word list is open-ended: "Ausweislich" and the ß-less "Gemäss" open a
    sentence exactly like "Nach" or "Gemäß" do, and no closed enumeration of
    German introducers can be finished. The allowance is therefore granted on
    what it exists for -- the publication's own designation line -- and every
    other lead text is a sentence, whatever word it happens to start with.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    unlisted = "Ausweislich § 14 DGUV Vorschrift 1 trägt der Unternehmer die Kosten."
    assert _logical_lines(unlisted) == [unlisted]

    sz_folded = "Gemäss § 12 ArbSchG sind Maßnahmen zu treffen."
    assert _logical_lines(sz_folded) == [sz_folded]


def test_logical_lines_does_not_split_at_a_colon_introduced_reference():
    """No word list can reach this one: the word before the marker is a
    capitalised noun ("Vorschriften:"), the same shape a title line ends in.
    Only the absence of a designation in front of the marker tells them apart.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    enumeration = "Es gelten folgende Vorschriften: § 14 DGUV Vorschrift 1 und weitere."

    assert _logical_lines(enumeration) == [enumeration]


def test_logical_lines_finds_a_real_heading_after_a_leading_cross_reference():
    """An ordinary merged item that happens to open with a cross-reference.

    Rejecting the leading "§ 14" must not cost the real "§ 2" behind it: this
    is not an exotic edge case but the everyday shape of a merged page whose
    first sentence cites another regulation.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    text = (
        "Ausweislich § 14 DGUV Vorschrift 1 trägt er die Kosten. "
        "§ 2 Pflichten des Unternehmers Der Unternehmer trifft die Maßnahmen."
    )

    assert _logical_lines(text) == [
        "Ausweislich § 14 DGUV Vorschrift 1 trägt er die Kosten.",
        "§ 2 Pflichten des Unternehmers",
        "Der Unternehmer trifft die Maßnahmen.",
    ]


def test_logical_lines_still_splits_a_title_line_carrying_an_issue_date():
    """The designation line as real publications set it: designation, issue
    date, title. The date's ordinal ("1.") ends in a full stop and its year is
    a bare number, neither of which may disturb the split -- and the lead text
    still has to be recognised as a designation for the first marker to count
    as a heading."""
    from normly_core.pipeline.adapters.dguv import _logical_lines

    assert _logical_lines(
        "DGUV Vorschrift 1 vom 1. November 2013 "
        "Grundsätze der Prävention § 1 Geltungsbereich"
    ) == [
        "DGUV Vorschrift 1 vom 1. November 2013 Grundsätze der Prävention",
        "§ 1 Geltungsbereich",
    ]


def test_logical_lines_does_not_split_when_a_sentence_is_glued_onto_the_title():
    """Opening with the designation is not enough to be a title line.

    The designation pattern's tail is `(.*)`, so it swallows whatever follows
    the designation number -- including a whole second sentence run onto the
    title with no punctuation between them. Every text below therefore starts
    with a real designation, and none of them is a title line: the marker sits
    inside a sentence, and splitting there fabricates a section out of it.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    glued_sentence = (
        "DGUV Vorschrift 1 Grundsätze der Prävention "
        "Ausweislich § 14 ArbSchG trägt der Unternehmer die Kosten."
    )
    assert _logical_lines(glued_sentence) == [glued_sentence]

    designation_as_subject = (
        "DGUV Vorschrift 1 regelt in Verbindung mit ArbSchG "
        "§ 5 Gefährdungsbeurteilung der Arbeitsplätze."
    )
    assert _logical_lines(designation_as_subject) == [designation_as_subject]

    enumeration = (
        "DGUV Vorschrift 1 nennt folgende Vorschriften: "
        "§ 14 DGUV Vorschrift 1 und weitere."
    )
    assert _logical_lines(enumeration) == [enumeration]

    other_series = (
        "DGUV Regel 100-001 Anwendung der Unfallverhuetungsvorschrift "
        "Gemaess ArbSchG § 5 Gefaehrdungsbeurteilung der Arbeitsplaetze."
    )
    assert _logical_lines(other_series) == [other_series]


def test_logical_lines_does_not_split_on_a_glued_sentence_with_an_unlisted_opener():
    """The glued-sentence guard may not lean on a list of known openers either.

    "Ausweislich", "Laut", "Zwecks" open a sentence exactly like "Gemäß" does
    and no enumeration of them can be finished, so the title's *shape* has to
    decide: German capitalises nouns, so a noun phrase separates its
    capitalised words by lower-case function words ("Grundsätze der
    Prävention"). Two capitalised words in a row past the title's opening word
    mean a new constituent began -- whatever word it is.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    # The run behind this marker even splits cleanly into title and body
    # ("§ 5 ArbSchG" + "Der Unternehmer ..."), so only the lead can reject it.
    listed_nowhere = (
        "DGUV Vorschrift 1 Grundsätze der Prävention "
        "Laut § 5 ArbSchG Der Unternehmer zahlt die Kosten."
    )
    assert _logical_lines(listed_nowhere) == [listed_nowhere]

    # ... and here the run behind the marker looks exactly like a real heading.
    heading_shaped_run = (
        "DGUV Vorschrift 1 Grundsätze der Prävention "
        "Zwecks § 5 Gefährdungsbeurteilung der Arbeitsplätze"
    )
    assert _logical_lines(heading_shaped_run) == [heading_shaped_run]

    after_a_two_word_title = (
        "DGUV Information 204-022 Erste Hilfe im Betrieb "
        "Ausweislich § 14 SGB Die Kosten trägt der Unternehmer."
    )
    assert _logical_lines(after_a_two_word_title) == [after_a_two_word_title]


def test_logical_lines_splits_title_lines_of_every_real_shape():
    """The counterpart: the title shapes the guard above must let through.

    A title's own first word is capitalised whatever its part of speech, so an
    adjective may stand before its noun there ("Erste Hilfe") -- the one place
    two capitalised words in a row are a title and not a new sentence. A title
    also runs longer than the fixture's three words, and a publication may set
    no title on the designation line at all.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    assert _logical_lines(
        "DGUV Information 204-022 Erste Hilfe im Betrieb § 1 Geltungsbereich"
    ) == ["DGUV Information 204-022 Erste Hilfe im Betrieb", "§ 1 Geltungsbereich"]

    assert _logical_lines(
        "DGUV Vorschrift 2 Betriebsärzte und Fachkräfte für Arbeitssicherheit "
        "§ 1 Geltungsbereich"
    ) == [
        "DGUV Vorschrift 2 Betriebsärzte und Fachkräfte für Arbeitssicherheit",
        "§ 1 Geltungsbereich",
    ]

    assert _logical_lines("DGUV Vorschrift 1 § 1 Geltungsbereich") == [
        "DGUV Vorschrift 1",
        "§ 1 Geltungsbereich",
    ]


def test_logical_lines_splits_consecutive_headings_without_a_title_line():
    """Two real headings in one merged item, no designation in front of them.

    The lead-side guards only ever apply to a marker that has text before it;
    a page that begins with its first heading must keep splitting on every one
    of them, body sentences and all.
    """
    from normly_core.pipeline.adapters.dguv import _logical_lines

    text = (
        "§ 1 Geltungsbereich Diese Vorschrift gilt für alle Unternehmen und Versicherte. "
        "§ 2 Pflichten des Unternehmers "
        "Der Unternehmer hat die Kosten für die Maßnahmen zu tragen."
    )

    assert _logical_lines(text) == [
        "§ 1 Geltungsbereich",
        "Diese Vorschrift gilt für alle Unternehmen und Versicherte.",
        "§ 2 Pflichten des Unternehmers",
        "Der Unternehmer hat die Kosten für die Maßnahmen zu tragen.",
    ]


def test_logical_lines_keeps_the_whole_text_when_the_title_boundary_is_unclear():
    """Where title and body cannot be told apart, a bare "§ N" heading is
    correct-but-poorer. Inventing a boundary, or dropping the text, is not."""
    from normly_core.pipeline.adapters.dguv import _logical_lines

    lines = _logical_lines("§ 4 Unterweisung Arbeitgeber unterweisen jährlich.")

    assert lines == ["§ 4", "Unterweisung Arbeitgeber unterweisen jährlich."]


def test_classify_rights_allows_full_processing():
    adapter = DguvAdapter(directory=FIXTURE_DIR, source_id=uuid.uuid4())
    record = list(adapter.fetch())[0]

    rule = adapter.classify_rights(record)

    assert rule.may_process is True
    assert rule.may_index_fulltext is True
    assert rule.may_cite_passages is True
    assert rule.may_export_free is True
    assert rule.jurisdiction == "DE"


def test_docling_classifies_paragraph_headings_as_list_items_not_section_headers():
    """
    Documents a real, empirically verified Docling behavior (2.123.1):
    §-paragraph headings in DGUV-style plainly-formatted legal text come
    back as ListItem, not SectionHeaderItem -- Docling's layout model has
    no visual cue (larger font, boldness, spacing) to distinguish them from
    a numbered list. This is exactly why extract_structure() stays
    pattern-based instead of trusting Docling's element classification --
    see docs/superpowers/specs/2026-08-30-docling-migration-design.md,
    "Empirischer Befund" and "Entscheidungsverfahren für künftige Adapter".

    If this test starts failing after a future Docling version upgrade,
    that is a deliberate signal that the classification behavior changed --
    re-run the decision procedure in the design doc, do not just delete or
    "fix" this assertion.
    """
    from docling_core.types.doc import ListItem, SectionHeaderItem

    from normly_core.pipeline.docling_extraction import extract_document

    document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")
    known_headings = {
        "§ 1 Geltungsbereich", "§ 2 Pflichten des Unternehmers",
        "§ 3 Pflichten der Versicherten",
    }
    heading_items = [
        item for item, _level in document.iterate_items()
        if getattr(item, "text", None) in known_headings
    ]

    assert len(heading_items) == 3
    assert all(isinstance(item, ListItem) for item in heading_items)
    assert not any(isinstance(item, SectionHeaderItem) for item in heading_items)
