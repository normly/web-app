# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import DocumentDesignation, DocumentTitle
from normly_core.pipeline.document_embedding import build_document_embedding_text


def _designation(designation: str, *, is_primary: bool) -> DocumentDesignation:
    return DocumentDesignation(
        id=uuid.uuid4(), document_id=uuid.uuid4(), issuer="CEN", designation=designation,
        language="de", edition=None, is_primary=is_primary, delivery_id=uuid.uuid4(),
    )


def _title(title: str) -> DocumentTitle:
    return DocumentTitle(
        id=uuid.uuid4(), document_id=uuid.uuid4(), language="de", title=title,
        delivery_id=uuid.uuid4(),
    )


def test_combines_primary_designation_and_first_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]
    titles = [_title("Qualitätsmanagementsysteme")]

    text = build_document_embedding_text(designations, titles)

    assert text == "EN ISO 9001:2018 — Qualitätsmanagementsysteme"


def test_ignores_a_non_primary_designation_when_a_primary_one_exists():
    designations = [
        _designation("wrong-secondary", is_primary=False),
        _designation("EN ISO 9001:2018", is_primary=True),
    ]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_falls_back_to_designation_alone_when_there_is_no_title():
    designations = [_designation("EN ISO 9001:2018", is_primary=True)]

    text = build_document_embedding_text(designations, [])

    assert text == "EN ISO 9001:2018"


def test_returns_none_when_there_is_no_primary_designation():
    text = build_document_embedding_text([], [_title("Qualitätsmanagementsysteme")])

    assert text is None
