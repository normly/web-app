# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.pipeline.adapters.baua import BauaAdapter
from normly_core.pipeline.domain import RawRecord


# Keep the generated CI cases and opt-in local real-document checks tied to the
# same known first/last heading canaries, without including any source body text.
BAUA_REAL_DOCUMENT_HEADING_CANARIES = (
    (
        "TRGS-401.pdf",
        "TRGS 401",
        "baua_trgs_401.pdf",
        "1 Anwendungsbereich",
        "7 Arbeitsmedizinische Vorsorge",
    ),
    (
        "TRGS-402.pdf",
        "TRGS 402",
        "baua_trgs_402.pdf",
        "1 Anwendungsbereich",
        "7 Dokumentation",
    ),
)


def assert_heading_canaries(
    adapter: BauaAdapter,
    record: RawRecord,
    *,
    sample_name: str,
    expected_designation: str,
    expected_first_heading: str,
    expected_last_heading: str,
) -> None:
    """Apply the same extraction assertions to synthetic and real PDFs."""
    assert record.raw_designation == expected_designation, sample_name
    assert bool(record.full_text), sample_name

    sections = adapter.extract_structure(record)
    assert sections, sample_name
    assert [section.sequence_number for section in sections] == list(
        range(1, len(sections) + 1)
    ), sample_name
    headings = [section.heading for section in sections if section.heading is not None]
    assert headings, f"{sample_name}: no section headings extracted"
    assert headings[0] == expected_first_heading, sample_name
    assert headings[-1] == expected_last_heading, sample_name
