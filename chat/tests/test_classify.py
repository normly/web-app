# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_chat.classify import QuestionType, classify, extract_designation


def test_classifies_a_validity_question_as_structural_validity():
    assert classify("Ist DIN EN ISO 9001 noch gültig?") == QuestionType.STRUCTURAL_VALIDITY


def test_classifies_a_replacement_question_as_structural_reference():
    assert classify("Was ersetzt DIN EN ISO 9001?") == QuestionType.STRUCTURAL_REFERENCE


def test_classifies_a_reference_question_as_structural_reference():
    assert classify("Worauf verweist EU 2006/42/EC?") == QuestionType.STRUCTURAL_REFERENCE


def test_classifies_an_open_question_as_synthesis():
    assert classify("Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?") == \
        QuestionType.SYNTHESIS


def test_a_trigger_word_without_a_designation_is_synthesis_not_structural():
    # "aktuell" and "gültig" are ordinary German words that show up in plain
    # synthesis questions. A structural classification requires the trigger
    # pattern AND a recognizable designation -- otherwise the structural path
    # has nothing to look up and could only ever produce a fallback.
    assert classify("Welche Schutzausrüstung ist beim Schweißen aktuell vorgeschrieben?") == \
        QuestionType.SYNTHESIS
    assert classify("What safety equipment is valid for welding?") == QuestionType.SYNTHESIS


def test_a_reference_trigger_word_without_a_designation_is_synthesis():
    assert classify("Welche Regel ersetzt die alte Schweißvorschrift?") == QuestionType.SYNTHESIS
    assert classify("Which rule replaces the old welding guidance?") == QuestionType.SYNTHESIS


def test_extract_designation_finds_a_din_style_designation_with_issuer_prefix():
    # DIN-style designations are stored WITH the issuer baked into the
    # designation string (issuer="DIN", designation="DIN EN ISO 9001") --
    # verified against core/tests/graph/test_designation_and_title.py's real
    # fixtures, not assumed.
    result = extract_designation("Ist DIN EN ISO 9001 noch gültig?")
    assert result == ("DIN", "DIN EN ISO 9001")


def test_extract_designation_finds_an_eu_style_designation_without_issuer_prefix():
    # EU legal-act designations are stored WITHOUT "EU" in the designation
    # string (issuer="EU", designation="2006/42/EC") -- verified against
    # core/tests/pipeline/test_eur_lex_adapter.py's real fixture.
    result = extract_designation("Was regelt EU 2006/42/EC?")
    assert result == ("EU", "2006/42/EC")


def test_extract_designation_returns_none_when_nothing_recognizable():
    assert extract_designation("Wie sicher sind Werkstätten?") is None
