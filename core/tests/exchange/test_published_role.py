# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""The public dump carries a role label, never a personal name (ADR-025)."""

from datetime import datetime, timezone

import sqlalchemy as sa

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.importer import import_dump
from normly_core.exchange.manifest import Manifest
from normly_core.exchange.parquet_io import read_rows
from normly_core.exchange.signing import generate_keypair
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.graph.postgres.exchange import (
    PUBLISHED_ROLE,
    PostgresKnowledgeExchangeRepository,
)
from normly_core.graph.postgres.orm import RightsClassificationORM, SourceORM

from .helpers import make_delivery, make_document, make_source

NAME = "Erika Mustermann"
REVISION = "3d7cfbd"
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def _named(db_session):
    source = make_source(db_session, responsible_person=NAME)
    delivery = make_delivery(db_session, source, "n")
    make_document(db_session, delivery, "TRGS 900", classified_by=NAME)


def _export(repository, tmp_path, version="2026.10.1"):
    private_pem, public_pem = generate_keypair()
    dump_dir = export_dump(
        repository, out_dir=tmp_path, dump_version=version,
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    return dump_dir, public_pem


def test_exported_rows_carry_the_role_while_the_database_keeps_the_names(db_session):
    _named(db_session)
    repository = PostgresKnowledgeExchangeRepository(db_session)

    sources = [r for b in repository.iter_exportable_rows("source") for r in b]
    rights = [r for b in repository.iter_exportable_rows("rights_classification") for r in b]

    assert sources and rights
    assert {r["responsible_person"] for r in sources} == {PUBLISHED_ROLE}
    assert {r["classified_by"] for r in rights} == {PUBLISHED_ROLE}
    assert db_session.scalars(sa.select(SourceORM.responsible_person)).all() == [NAME]
    assert db_session.scalars(sa.select(RightsClassificationORM.classified_by)).all() == [NAME]


def test_masked_columns_exist_in_the_schema():
    from normly_core.graph.postgres.exchange import _PERSONAL_NAME_COLUMNS
    from normly_core.graph.postgres.orm import Base

    assert _PERSONAL_NAME_COLUMNS
    for table, column in _PERSONAL_NAME_COLUMNS.items():
        assert column in Base.metadata.tables[table].c


def test_no_personal_name_anywhere_in_the_dump(db_session, tmp_path):
    _named(db_session)
    dump_dir, _ = _export(PostgresKnowledgeExchangeRepository(db_session), tmp_path)
    manifest = Manifest.from_bytes((dump_dir / "manifest.json").read_bytes())

    for table in KNOWLEDGE_TABLES:
        for entry in manifest.tables[table]:
            for batch in read_rows(dump_dir / entry.path):
                for row in batch:
                    assert NAME not in repr(row), table
    for path in dump_dir.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert NAME.encode() not in data, path
            assert b"Mustermann" not in data, path


def test_import_overwrites_names_with_the_role(db_session, tmp_path):
    _named(db_session)
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_dir, public_pem = _export(repository, tmp_path)

    import_dump(
        repository, dump_dir=dump_dir, public_key_pem=public_pem,
        expected_model_name="intfloat/multilingual-e5-large",
        expected_model_revision=REVISION, now=NOW,
    )

    assert db_session.scalars(sa.select(SourceORM.responsible_person)).all() == [PUBLISHED_ROLE]
    assert db_session.scalars(
        sa.select(RightsClassificationORM.classified_by)
    ).all() == [PUBLISHED_ROLE]
