# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest

from normly_core.pipeline.adapters.baua import BauaAdapter
from normly_core.pipeline.domain import RawRecord


def _write_publication_pdf(path: Path, lines: list[str]) -> None:
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path))
    y = 700  # Start in middle of page for better extraction
    for i, line in enumerate(lines):
        if line:  # Only draw non-empty lines
            pdf.drawString(72, y, line)
        # Small gap between designation/title; large gap before body
        if i == 1:
            y -= 60  # Large gap after title
        else:
            y -= 10  # Small gap for designation/title
    pdf.save()


@pytest.mark.parametrize(
    "prefix, designation, title, filename",
    [
        ("TRGS", "TRGS 900", "Arbeitsplatzgrenzwerte", "baua_trgs_900.pdf"),
        ("TRBS", "TRBS 1201", "Prüfung von Arbeitsmitteln", "baua_trbs_1201.pdf"),
        ("TRBA", "TRBA 100", "Schutzmaßnahmen für Tätigkeiten mit biologischen Arbeitsstoffen in Laboratorien", "baua_trba_100.pdf"),
    ],
)
def test_fetch_splits_designation_and_title_per_series(
    tmp_path, prefix, designation, title, filename
):
    _write_publication_pdf(
        tmp_path / filename,
        [
            designation,
            title,
            "",
            "Diese Regel konkretisiert die Anforderungen im Rahmen ihres Anwendungsbereichs.",
        ],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert len(records) == 1
    record = records[0]
    assert record.raw_designation == designation
    assert record.raw_issuer == "BAuA"
    assert record.raw_title == title
    assert record.full_text is not None
    assert "konkretisiert die Anforderungen" in record.full_text
    assert record.language == "de"


def test_fetch_parses_a_teil_suffixed_designation(tmp_path):
    _write_publication_pdf(
        tmp_path / "baua_trgs_500_teil_1.pdf",
        ["TRGS 500 Teil 1", "Schutzmaßnahmen", "", "Body text hier."],
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert records[0].raw_designation == "TRGS 500 Teil 1"
    assert records[0].raw_title == "Schutzmaßnahmen"


def test_fetch_reads_all_three_series_and_ignores_other_sources_files(tmp_path):
    """`--directory` means the directory, not one hardcoded filename in it,
    and the three series share one adapter (design spec, "Ziel dieses
    Teilprojekts")."""
    _write_publication_pdf(
        tmp_path / "baua_trgs_900.pdf", ["TRGS 900", "Arbeitsplatzgrenzwerte", "", "Text."]
    )
    _write_publication_pdf(
        tmp_path / "baua_trbs_1201.pdf", ["TRBS 1201", "Prüfung von Arbeitsmitteln", "", "Text."]
    )
    _write_publication_pdf(
        tmp_path / "baua_trba_100.pdf", ["TRBA 100", "Schutzmaßnahmen", "", "Text."]
    )
    # A neighbouring source's file in the same directory stays untouched.
    _write_publication_pdf(
        tmp_path / "dguv_vorschrift_1.pdf", ["DGUV Vorschrift 1", "Grundsätze", "", "Text."]
    )

    records = list(BauaAdapter(directory=tmp_path, source_id=uuid.uuid4()).fetch())

    assert sorted(record.raw_designation for record in records) == [
        "TRBA 100", "TRBS 1201", "TRGS 900",
    ]
