# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from normly_core.pipeline.domain import RightsRule
from normly_core.pipeline.docling_extraction import extract_document
from normly_core.pipeline.docling_markdown import export_document_markdown
from normly_core.pipeline.adapters import dguv
from normly_core.pipeline.adapters.dguv import DguvAdapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"
_PERMITTED_RULE = RightsRule(
    jurisdiction="DE",
    may_process=True,
    may_index_fulltext=True,
    may_cite_passages=True,
    may_export_free=True,
    legal_basis_reference="test source",
)
_CONTENT_HASH = "sha256:" + "a" * 64


def test_same_pdf_exports_identical_markdown_on_repeated_docling_conversions():
    source_path = FIXTURE_DIR / "dguv_sample_vorschrift.pdf"

    first = extract_document(source_path).export_to_markdown()
    second = extract_document(source_path).export_to_markdown()

    assert first == second


def test_adapter_sidecar_matches_the_same_real_docling_document(
    tmp_path, monkeypatch
):
    source_path = FIXTURE_DIR / "dguv_sample_vorschrift.pdf"
    converted_documents = []
    exported_documents = []
    extract = dguv.extract_document
    export = dguv.export_document_markdown

    def capture_conversion(path):
        document = extract(path)
        converted_documents.append(document)
        return document

    def capture_export(document, **kwargs):
        exported_documents.append(document)
        return export(document, **kwargs)

    monkeypatch.setattr(dguv, "extract_document", capture_conversion)
    monkeypatch.setattr(dguv, "export_document_markdown", capture_export)
    adapter = DguvAdapter(
        directory=FIXTURE_DIR,
        source_id=uuid.uuid4(),
        docling_markdown_dir=tmp_path,
    )

    records = list(adapter.fetch())

    assert len(records) == 1
    assert len(converted_documents) == len(exported_documents) == 1
    assert exported_documents[0] is converted_documents[0]
    markdown_path = next(tmp_path.glob("*.md"))
    sidecar_digest = hashlib.sha256(markdown_path.read_bytes()).digest()
    document_digest = hashlib.sha256(
        converted_documents[0].export_to_markdown().encode("utf-8")
    ).digest()
    assert sidecar_digest == document_digest


def test_export_document_markdown_is_content_addressed_and_repeatable(tmp_path):
    document = MagicMock()
    document.export_to_markdown.return_value = "# Example\n\nExtracted text.\n"
    source_path = Path("dguv_vorschrift_1.pdf")
    output_dir = tmp_path / "nested" / "markdown"

    first_path = export_document_markdown(
        document,
        source_path=source_path,
        content_hash=_CONTENT_HASH,
        output_dir=output_dir,
        rights_rule=_PERMITTED_RULE,
    )
    second_path = export_document_markdown(
        document,
        source_path=source_path,
        content_hash=_CONTENT_HASH,
        output_dir=output_dir,
        rights_rule=_PERMITTED_RULE,
    )

    expected_path = output_dir / f"dguv_vorschrift_1--{'a' * 64}.md"
    assert first_path == second_path == expected_path
    assert first_path.read_text(encoding="utf-8") == "# Example\n\nExtracted text.\n"
    assert list(output_dir.glob("*.tmp")) == []
    assert document.export_to_markdown.call_count == 2


@pytest.mark.parametrize(
    "rights_rule",
    [
        replace(_PERMITTED_RULE, may_process=False),
        replace(_PERMITTED_RULE, may_export_free=False),
        None,
    ],
)
def test_export_document_markdown_does_not_write_when_rights_do_not_allow_it(
    tmp_path, rights_rule
):
    document = MagicMock()
    output_dir = tmp_path / "markdown"

    result = export_document_markdown(
        document,
        source_path=Path("restricted.pdf"),
        content_hash=_CONTENT_HASH,
        output_dir=output_dir,
        rights_rule=rights_rule,
    )

    assert result is None
    assert not output_dir.exists()
    document.export_to_markdown.assert_not_called()


def test_export_document_markdown_rejects_an_invalid_content_hash(tmp_path):
    document = MagicMock()

    with pytest.raises(ValueError, match="SHA-256"):
        export_document_markdown(
            document,
            source_path=Path("bad.pdf"),
            content_hash="sha256:not-a-digest",
            output_dir=tmp_path / "markdown",
            rights_rule=_PERMITTED_RULE,
        )

    document.export_to_markdown.assert_not_called()
