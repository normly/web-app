# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from normly_core.pipeline.docling_extraction import extract_document

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"

_ARTIFACTS_PATH_ENV = "NORMLY_DOCLING_ARTIFACTS_PATH"


@pytest.mark.skipif(
    not os.environ.get(_ARTIFACTS_PATH_ENV),
    reason=(
        f"Set {_ARTIFACTS_PATH_ENV} to a directory populated with Docling's "
        "layout and tableformer models (locally: `docling-tools models "
        "download layout tableformer -o <path>`; in the image: "
        "/opt/models/docling) to run this test -- it proves extraction "
        "needs no network access once models are pre-fetched, matching the "
        "production deployment requirement (no runtime access to external "
        "model sources, CLAUDE.md's STACKIT-only constraint)."
    ),
)
def test_extraction_makes_no_network_connection_when_models_are_pre_fetched():
    def _blocked_connect(self, address, *args, **kwargs):
        raise AssertionError(
            f"Docling attempted a network connection to {address!r} during "
            "extraction -- with NORMLY_DOCLING_ARTIFACTS_PATH set, this must "
            "never happen; models must come only from the pre-fetched path."
        )

    with patch.object(socket.socket, "connect", _blocked_connect):
        document = extract_document(FIXTURE_DIR / "dguv_sample_vorschrift.pdf")

    assert document is not None
