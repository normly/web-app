# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.markers import (
    MarkedParagraph,
    number_context,
    parse_marked_answer,
    split_paragraphs,
)


def test_number_context_numbers_from_one():
    assert number_context(["Erster.", "Zweiter."]) == "[1] Erster.\n\n[2] Zweiter."


def test_split_paragraphs_splits_at_blank_lines_and_drops_empty_blocks():
    assert split_paragraphs("A\nweiter\n\n  \n\nB\n") == ["A\nweiter", "B"]
    assert split_paragraphs("") == []


def test_markers_are_collected_per_paragraph_and_stripped():
    answer = "Schutzbrillen sind Pflicht [1].\n\nDas gilt auch für Helfer [2][3]."

    assert parse_marked_answer(answer, 3) == [
        MarkedParagraph("Schutzbrillen sind Pflicht.", [0]),
        MarkedParagraph("Das gilt auch für Helfer.", [1, 2]),
    ]


def test_comma_lists_and_mid_sentence_markers_are_understood():
    answer = "Laut Vorschrift [1, 2] gilt das, siehe auch [2]."

    assert parse_marked_answer(answer, 2) == [
        MarkedParagraph("Laut Vorschrift gilt das, siehe auch.", [0, 1]),
    ]


def test_markers_outside_the_source_range_are_dropped():
    assert parse_marked_answer("Text [0] und [7] und [2].", 2) == [
        MarkedParagraph("Text und und.", [1]),
    ]


def test_an_answer_without_markers_keeps_its_paragraphs_with_no_sources():
    assert parse_marked_answer("Eins.\n\nZwei.", 3) == [
        MarkedParagraph("Eins.", []),
        MarkedParagraph("Zwei.", []),
    ]


def test_a_marker_only_block_attaches_to_the_previous_paragraph():
    assert parse_marked_answer("Eins.\n\n[2]", 2) == [MarkedParagraph("Eins.", [1])]


def test_a_leading_marker_only_block_is_dropped():
    assert parse_marked_answer("[1]\n\nEins.", 2) == [MarkedParagraph("Eins.", [])]
