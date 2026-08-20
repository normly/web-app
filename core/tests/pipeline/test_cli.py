# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from normly_core.pipeline.cli import build_adapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"


def test_build_adapter_returns_eur_lex_adapter_for_eur_lex_source():
    adapter = build_adapter("eur-lex", directory=FIXTURE_DIR)
    assert type(adapter).__name__ == "EurLexAdapter"


def test_build_adapter_returns_dguv_adapter_for_dguv_source():
    adapter = build_adapter("dguv", directory=FIXTURE_DIR)
    assert type(adapter).__name__ == "DguvAdapter"


def test_build_adapter_rejects_unknown_source():
    with pytest.raises(ValueError, match="unknown source"):
        build_adapter("not-a-real-source", directory=FIXTURE_DIR)
