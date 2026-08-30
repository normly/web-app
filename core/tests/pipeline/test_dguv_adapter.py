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


def _write_vorschrift_pdf(path, designation: str, title: str) -> None:
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
    _write_vorschrift_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", "DGUV Vorschrift 1", "Grundsätze der Prävention"
    )
    _write_vorschrift_pdf(
        tmp_path / "dguv_vorschrift_2.pdf", "DGUV Vorschrift 2", "Betriebsärzte"
    )
    # A neighbouring source's file in the same directory stays untouched.
    _write_vorschrift_pdf(tmp_path / "eur_lex_something.pdf", "2006/42/EC", "Machinery")

    records = list(DguvAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert [record.raw_designation for record in records] == [
        "DGUV Vorschrift 1",
        "DGUV Vorschrift 2",
    ]
    assert len({record.content_hash for record in records}) == 2


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
