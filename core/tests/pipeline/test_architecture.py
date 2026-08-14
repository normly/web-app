# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import ast
from pathlib import Path


def test_pipeline_domain_does_not_import_sqlalchemy():
    domain_path = (
        Path(__file__).parents[2] / "src" / "normly_core" / "pipeline" / "domain.py"
    )
    tree = ast.parse(domain_path.read_text())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "sqlalchemy" not in imported_names
