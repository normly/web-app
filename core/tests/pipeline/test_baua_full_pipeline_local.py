# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Opt-in full-pipeline checks using the private local BAuA test corpus.

Initialize the private submodule from the repository root, prepare the pinned
local model artifacts, and set NORMLY_RUN_LOCAL_BAUA_PIPELINE_TEST=1 to run this
module. The PostgreSQL data directory is held in tmpfs and removed at teardown.
This module is skipped in CI and ordinary local test runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

_OPT_IN = os.environ.get("NORMLY_RUN_LOCAL_BAUA_PIPELINE_TEST") == "1"
_DOCUMENT_DIR_VALUE = os.environ.get("BAUA_REAL_DOCUMENTS_DIR")
_REQUIRED_DOCUMENTS = (
    "TRGS-001.pdf",
    "TRGS-401.pdf",
    "TRGS-402.pdf",
)

if _OPT_IN:
    if not _DOCUMENT_DIR_VALUE:
        raise pytest.UsageError(
            "set BAUA_REAL_DOCUMENTS_DIR to the private local BAuA test corpus"
        )

    _DOCUMENT_DIR = Path(_DOCUMENT_DIR_VALUE).expanduser().resolve()
    _missing_documents = [
        name for name in _REQUIRED_DOCUMENTS if not (_DOCUMENT_DIR / name).is_file()
    ]
    if _missing_documents:
        raise pytest.UsageError(
            "required local BAuA test samples are missing: "
            + ", ".join(_missing_documents)
        )

    _EMBEDDING_MODEL_PATH_VALUE = os.environ.get("NORMLY_EMBEDDING_MODEL_PATH")
    _DOCLING_ARTIFACTS_PATH_VALUE = os.environ.get("NORMLY_DOCLING_ARTIFACTS_PATH")
    for _name, _value in (
        ("NORMLY_EMBEDDING_MODEL_PATH", _EMBEDDING_MODEL_PATH_VALUE),
        ("NORMLY_DOCLING_ARTIFACTS_PATH", _DOCLING_ARTIFACTS_PATH_VALUE),
    ):
        if not _value or not Path(_value).expanduser().is_dir():
            raise pytest.UsageError(f"{_name} must point to a local model directory")

    _EMBEDDING_MODEL_PATH = Path(_EMBEDDING_MODEL_PATH_VALUE).expanduser().resolve()
else:
    _DOCUMENT_DIR = None
    _EMBEDDING_MODEL_PATH = None

pytestmark = pytest.mark.skipif(
    not _OPT_IN,
    reason="set NORMLY_RUN_LOCAL_BAUA_PIPELINE_TEST=1 to run the local full-pipeline test",
)


@pytest.fixture(scope="session")
def postgres_container():
    """Run test PostgreSQL entirely in volatile storage and remove it afterward."""
    container = PostgresContainer("pgvector/pgvector:pg16", driver="psycopg")
    container.with_env("PGDATA", "/var/lib/postgresql/tmp_pgdata")
    container.with_tmpfs_mount("/var/lib/postgresql/tmp_pgdata", "rw,size=512m")
    # Keep this database's tmpfs pages inside the container's memory cgroup;
    # Docker interprets equal memory and memory+swap limits as no container swap.
    container.with_kwargs(mem_limit="1g", memswap_limit="1g")

    with container as started:
        yield started


def test_real_baua_samples_persist_embed_and_retrieve_locally(
    db_session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from normly_core.graph.postgres.repositories import (
        PostgresDocumentRepository,
        PostgresEmbeddingRepository,
        PostgresIdentityResolutionRepository,
        PostgresSegmentRepository,
    )
    from normly_core.pipeline import runner
    from normly_core.pipeline.cli import build_adapter
    from normly_core.pipeline.embeddings import MODEL_NAME, EmbeddingModel

    from .baua_test_support import BAUA_REAL_DOCUMENT_HEADING_CANARIES

    assert _DOCUMENT_DIR is not None
    assert _EMBEDDING_MODEL_PATH is not None

    # Stage the original private PDFs by symlink, using the adapter's expected
    # filename convention. No PDF bytes are copied into the app repository.
    for filename, _designation, staged_name, _first, _last in (
        BAUA_REAL_DOCUMENT_HEADING_CANARIES
    ):
        (tmp_path / staged_name).symlink_to(_DOCUMENT_DIR / filename)
    (tmp_path / "baua_trgs_001.pdf").symlink_to(_DOCUMENT_DIR / "TRGS-001.pdf")

    adapter = build_adapter("baua", directory=tmp_path, session=db_session)
    model = EmbeddingModel(model_path=_EMBEDDING_MODEL_PATH)
    # Reuse the real local model instead of loading its large weights twice.
    monkeypatch.setattr(runner, "EmbeddingModel", lambda: model)

    summary = runner.run_adapter(adapter, db_session)

    assert summary.records_processed == 3
    assert summary.records_failed == 0
    assert summary.records_enqueued_for_review == 1
    assert summary.documents_created == 2
    assert summary.segments_created > 0
    assert summary.embeddings_created == summary.segments_created

    document_repo = PostgresDocumentRepository(db_session)
    segment_repo = PostgresSegmentRepository(db_session)
    embedding_repo = PostgresEmbeddingRepository(db_session)

    for (
        filename,
        designation,
        _staged_name,
        expected_first_heading,
        expected_last_heading,
    ) in BAUA_REAL_DOCUMENT_HEADING_CANARIES:
        document = document_repo.find_by_designation("BAuA", designation)
        assert document is not None, filename

        segments = segment_repo.list_segments_for_jurisdiction(document.id, "DE")
        headings = [segment.heading for segment in segments if segment.heading is not None]
        assert headings, filename
        assert headings[0] == expected_first_heading, filename
        assert headings[-1] == expected_last_heading, filename
        assert [segment.sequence_number for segment in segments] == list(
            range(1, len(segments) + 1)
        ), filename

        for segment in segments:
            stored_embedding = embedding_repo.get_embedding_unchecked(
                segment.id, MODEL_NAME
            )
            assert stored_embedding is not None, filename
            assert len(stored_embedding.vector) == 1024, filename
            assert any(component != 0.0 for component in stored_embedding.vector), filename

        target_segments = [
            segment
            for segment in segments
            if segment.heading == expected_first_heading and segment.text.strip()
        ]
        assert target_segments, filename
        target = target_segments[0]
        query = f"Was regelt {designation} im Abschnitt {expected_first_heading}?"
        query_vector = model.embed_query(query)
        hits = segment_repo.find_similar_segments_for_jurisdiction(
            query_vector, "DE", MODEL_NAME, limit=5
        )
        hit_ids = {segment.id for segment in hits}
        assert target.id in hit_ids, filename

        assert (
            segment_repo.find_similar_segments_for_jurisdiction(
                query_vector, "EU", MODEL_NAME, limit=100
            )
            == []
        ), filename

    pending_cases = PostgresIdentityResolutionRepository(db_session).list_pending_cases()
    assert len(pending_cases) == 1
    assert pending_cases[0].reason == "unparseable_designation"
