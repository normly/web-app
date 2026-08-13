# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import ast
import inspect
from pathlib import Path

from normly_core.graph.domain import DocumentRepository
from normly_core.graph.postgres.repositories import PostgresDocumentRepository


def test_domain_module_does_not_import_sqlalchemy():
    domain_path = (
        Path(__file__).parents[2] / "src" / "normly_core" / "graph" / "domain.py"
    )
    tree = ast.parse(domain_path.read_text())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "sqlalchemy" not in imported_names


UNGATED_READS = ("get_document_unchecked", "list_designations", "list_titles")


def test_document_repository_protocol_exposes_no_ungated_read():
    """
    The design spec: "Es gibt keine Methode, die Dokumente ungefiltert
    zurückgibt." The ungated reads remain available on the concrete
    implementation for pipeline and identity-resolution use, but they are not
    part of the public Protocol any API layer programs against.
    """
    protocol_methods = {
        name for name in vars(DocumentRepository) if not name.startswith("_")
    }

    assert protocol_methods.isdisjoint(UNGATED_READS)
    assert {"get_document_for_jurisdiction", "list_documents_for_jurisdiction"} <= (
        protocol_methods
    )


def test_every_protocol_read_takes_a_jurisdiction():
    for name in vars(DocumentRepository):
        if not name.startswith("list_") and not name.startswith("get_"):
            continue
        parameters = inspect.signature(getattr(DocumentRepository, name)).parameters
        assert "jurisdiction" in parameters, name


def test_ungated_reads_stay_available_on_the_concrete_repository():
    for name in UNGATED_READS:
        assert callable(getattr(PostgresDocumentRepository, name))
