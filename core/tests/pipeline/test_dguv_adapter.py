# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

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
