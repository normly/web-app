# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import numpy as np

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.importer import import_dump
from normly_core.exchange.manifest import Manifest
from normly_core.exchange.parquet_io import read_rows
from normly_core.exchange.signing import generate_keypair
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository
from normly_core.graph.postgres.repositories import (
    PostgresDocumentEmbeddingRepository,
    PostgresEmbeddingRepository,
    PostgresSegmentRepository,
)

from .helpers import NOW, make_delivery, make_document, make_source

MODEL = "intfloat/multilingual-e5-large"
REVISION = "3d7cfbd"


def test_full_dimension_embeddings_survive_export_and_import(db_session, tmp_path):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "emb")
    document = make_document(db_session, delivery, "TRGS 900")
    segment, _ = PostgresSegmentRepository(db_session).add_segment(
        document_id=document.id, delivery_id=delivery.id, sequence_number=1,
        heading="1", text="Text", language="de",
    )
    segment_vector = [i / 1024 for i in range(1024)]
    document_vector = [(1023 - i) / 2048 for i in range(1024)]
    embeddings = PostgresEmbeddingRepository(db_session)
    document_embeddings = PostgresDocumentEmbeddingRepository(db_session)
    embeddings.add_embedding(
        segment_id=segment.id, delivery_id=delivery.id, model_name=MODEL, vector=segment_vector
    )
    document_embeddings.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name=MODEL,
        vector=document_vector,
    )

    private_pem, public_pem = generate_keypair()
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_dir = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.1",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )

    # Overwrite the live document vector so only a correct import restores it.
    document_embeddings.upsert_document_embedding(
        document_id=document.id, delivery_id=delivery.id, model_name=MODEL,
        vector=[0.0] * 1024,
    )
    import_dump(
        repository, dump_dir=dump_dir, public_key_pem=public_pem,
        expected_model_name=MODEL, expected_model_revision=REVISION, now=NOW,
    )
    db_session.expire_all()

    restored = embeddings.get_embedding_unchecked(segment.id, MODEL)
    assert restored is not None
    assert len(restored.vector) == 1024
    np.testing.assert_allclose(restored.vector, segment_vector, atol=1e-6)

    # Document embeddings have no read method; re-export and compare the rows.
    second = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.2",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    manifest = Manifest.from_bytes((second / "manifest.json").read_bytes())
    (entry,) = manifest.tables["document_embedding"]
    (row,) = [r for batch in read_rows(second / entry.path) for r in batch]
    assert len(row["vector"]) == 1024
    np.testing.assert_allclose(row["vector"], document_vector, atol=1e-6)
