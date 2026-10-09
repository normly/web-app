# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date, datetime, timezone

from sqlalchemy import select

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.orm import DocumentEmbeddingORM, DocumentORM
from normly_core.graph.postgres.repositories import PostgresSourceRepository
from normly_core.pipeline.domain import RawRecord, RightsRule
from normly_core.pipeline.embeddings import MODEL_NAME
from normly_core.pipeline.runner import run_adapter


class _FakeAdapter:
    def __init__(self, source_id, records):
        self.source_id = source_id
        self._records = records

    def fetch(self):
        return list(self._records)

    def extract_structure(self, record):
        return []

    def classify_rights(self, record):
        return RightsRule(
            jurisdiction="DE", may_process=True, may_index_fulltext=False,
            may_cite_passages=False, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        )


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="Test", retrieval_path="file:///dev/null",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=date(2026, 1, 15), responsible_person="Test Reviewer",
    )


def test_ingesting_a_new_document_creates_its_embedding(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-new-doc", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title="Qualitätsmanagementsysteme", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)

    document = db_session.execute(select(DocumentORM)).scalar_one()
    embedding = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalar_one()
    assert embedding.model_name == MODEL_NAME
    assert len(embedding.vector) == 1024


def test_reprocessing_the_same_document_overwrites_its_embedding(db_session):
    # The second record adds the document's first-ever title rather than a
    # replacement one. build_document_embedding_text deliberately prefers the
    # earliest title ("first in list order" -- see its docstring), so a
    # second, different title on an already-titled document would leave the
    # embedding text -- and therefore the vector -- unchanged, which is not
    # what this test means to exercise. Going from no-title to titled is the
    # realistic case where reprocessing legitimately changes the embedding
    # text, while still exercising the same upsert-in-place repository path.
    source = _make_source(db_session)
    first_record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-repeat-1", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title=None, full_text=None,
    )
    second_record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-repeat-2", raw_designation="EN ISO 9001:2018",
        raw_issuer="CEN", raw_title="Qualitätsmanagementsysteme", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [first_record])
    run_adapter(adapter, db_session)
    document = db_session.execute(select(DocumentORM)).scalar_one()
    first_vector = db_session.execute(
        select(DocumentEmbeddingORM.vector).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalar_one()

    second_adapter = _FakeAdapter(source.id, [second_record])
    run_adapter(second_adapter, db_session)

    rows = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalars().all()
    assert len(rows) == 1  # overwritten in place, not a second row
    assert list(rows[0].vector) != list(first_vector)


def test_a_document_with_no_issuer_and_no_prior_designation_gets_no_embedding(db_session):
    source = _make_source(db_session)
    record = RawRecord(
        source_id=source.id, content_hash="sha256:embed-no-issuer", raw_designation="untitled",
        raw_issuer=None, raw_title="Ein Titel ohne Herausgeber", full_text=None,
    )
    adapter = _FakeAdapter(source.id, [record])

    run_adapter(adapter, db_session)

    document = db_session.execute(select(DocumentORM)).scalar_one()
    embeddings = db_session.execute(
        select(DocumentEmbeddingORM).where(DocumentEmbeddingORM.document_id == document.id)
    ).scalars().all()
    assert embeddings == []
