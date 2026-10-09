# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json
import shutil
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from normly_core.exchange.exporter import export_dump
from normly_core.exchange.importer import ImportRefused, import_dump
from normly_core.exchange.manifest import Manifest, sha256_file
from normly_core.exchange.parquet_io import read_rows, write_parts
from normly_core.exchange.tables import KNOWLEDGE_TABLES
from normly_core.exchange.signing import generate_keypair, sign
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository

from .helpers import make_delivery, make_document, make_source

MODEL = "intfloat/multilingual-e5-large"
REVISION = "3d7cfbd"
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.fixture()
def exported(db_session, tmp_path):
    source = make_source(db_session)
    delivery = make_delivery(db_session, source, "x")
    make_document(db_session, delivery, "TRGS 900")
    private_pem, public_pem = generate_keypair()
    repository = PostgresKnowledgeExchangeRepository(db_session)
    dump_dir = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.1",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    return repository, dump_dir, public_pem, private_pem


def _import(repository, dump_dir, public_pem, revision=REVISION):
    return import_dump(
        repository, dump_dir=dump_dir, public_key_pem=public_pem,
        expected_model_name=MODEL, expected_model_revision=revision, now=NOW,
    )


def _resign(dump_dir, private_pem, mutate):
    raw = json.loads((dump_dir / "manifest.json").read_text())
    mutate(raw)
    data = (json.dumps(raw, sort_keys=True, indent=2) + "\n").encode()
    (dump_dir / "manifest.json").write_bytes(data)
    (dump_dir / "manifest.json.sig").write_bytes(sign(private_pem, data))


def test_export_writes_manifest_signature_and_tables(exported):
    _, dump_dir, _, _ = exported
    assert (dump_dir / "manifest.json").is_file()
    assert len((dump_dir / "manifest.json.sig").read_bytes()) == 64
    assert (dump_dir / "tables" / "document" / "part-0000.parquet").is_file()


def test_export_refuses_to_overwrite_a_version(exported):
    repository, dump_dir, _, _ = exported
    with pytest.raises(FileExistsError):
        export_dump(
            repository, out_dir=dump_dir.parent, dump_version="2026.10.1",
            private_key_pem=generate_keypair()[0], embedding_model_revision=REVISION,
        )


def _rows(directory, table):
    manifest = Manifest.from_bytes((directory / "manifest.json").read_bytes())
    return [
        r for e in manifest.tables[table] for b in read_rows(directory / e.path) for r in b
    ]


def test_reexport_after_import_is_row_identical(exported, tmp_path):
    repository, dump_dir, public_pem, private_pem = exported
    _import(repository, dump_dir, public_pem)
    second = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.2",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    for table in KNOWLEDGE_TABLES:
        assert _rows(second, table) == _rows(dump_dir, table), table


def test_exported_manifest_checksums_match(exported):
    _, dump_dir, _, _ = exported
    manifest = Manifest.from_bytes((dump_dir / "manifest.json").read_bytes())
    for files in manifest.tables.values():
        for entry in files:
            assert sha256_file(dump_dir / entry.path) == entry.sha256


def test_import_roundtrip_is_idempotent(exported):
    repository, dump_dir, public_pem, _ = exported
    for _ in range(2):
        record = _import(repository, dump_dir, public_pem)
    assert record.dump_version == "2026.10.1"
    assert repository.imported_version().dump_version == "2026.10.1"


def test_import_refuses_tampered_table_file(exported):
    repository, dump_dir, public_pem, _ = exported
    part = dump_dir / "tables" / "document" / "part-0000.parquet"
    part.write_bytes(part.read_bytes() + b"x")
    with pytest.raises(ImportRefused, match="checksum"):
        _import(repository, dump_dir, public_pem)


def test_import_refuses_bad_signature(exported):
    repository, dump_dir, _, _ = exported
    with pytest.raises(ImportRefused, match="signature"):
        _import(repository, dump_dir, generate_keypair()[1])


def test_import_refuses_other_embedding_revision(exported):
    repository, dump_dir, public_pem, _ = exported
    with pytest.raises(ImportRefused, match="embedding model revision"):
        _import(repository, dump_dir, public_pem, revision="other")


def test_import_refuses_other_exchange_schema_version(exported):
    repository, dump_dir, public_pem, private_pem = exported
    _resign(dump_dir, private_pem, lambda raw: raw.update(exchange_schema_version=99))
    with pytest.raises(ImportRefused, match="exchange schema version"):
        _import(repository, dump_dir, public_pem)


def test_import_refuses_missing_table_in_manifest(exported):
    repository, dump_dir, public_pem, private_pem = exported
    _resign(dump_dir, private_pem, lambda raw: raw["tables"].pop("document"))
    with pytest.raises(ImportRefused, match="lacks tables"):
        _import(repository, dump_dir, public_pem)


def test_import_refuses_other_embedding_model(exported):
    repository, dump_dir, public_pem, private_pem = exported
    _resign(dump_dir, private_pem, lambda raw: raw.update(embedding_models=["other/model"]))
    with pytest.raises(ImportRefused, match="embeddings use"):
        _import(repository, dump_dir, public_pem)


def test_import_refuses_vector_dimension_mismatch(exported):
    repository, dump_dir, public_pem, private_pem = exported
    columns = repository.exchange_columns("embedding")
    row = {c.name: None for c in columns}
    row["vector"] = [0.1, 0.2, 0.3]
    shutil.rmtree(dump_dir / "tables" / "embedding")
    (entry,) = write_parts(dump_dir, "embedding", columns, iter([[row]]), rows_per_part=10)

    def mutate(raw):
        raw["tables"]["embedding"] = [
            {"path": entry.path, "sha256": entry.sha256, "rows": entry.rows}
        ]

    _resign(dump_dir, private_pem, mutate)
    with pytest.raises(ImportRefused, match="dimension"):
        _import(repository, dump_dir, public_pem)


@pytest.mark.parametrize("damage", ["no_manifest", "no_signature", "garbage", "missing_key"])
def test_import_maps_broken_manifest_to_refusal(exported, damage):
    repository, dump_dir, public_pem, private_pem = exported
    if damage == "no_manifest":
        (dump_dir / "manifest.json").unlink()
    elif damage == "no_signature":
        (dump_dir / "manifest.json.sig").unlink()
    elif damage == "garbage":
        data = b"not json"
        (dump_dir / "manifest.json").write_bytes(data)
        (dump_dir / "manifest.json.sig").write_bytes(sign(private_pem, data))
    else:
        _resign(dump_dir, private_pem, lambda raw: raw.pop("dump_version"))
    with pytest.raises(ImportRefused, match="manifest|signature"):
        _import(repository, dump_dir, public_pem)


def test_empty_dump_is_refused_when_the_database_holds_documents(db_session, tmp_path):
    private_pem, public_pem = generate_keypair()
    repository = PostgresKnowledgeExchangeRepository(db_session)
    empty_dir = export_dump(
        repository, out_dir=tmp_path, dump_version="2026.10.1",
        private_key_pem=private_pem, embedding_model_revision=REVISION, now=NOW,
    )
    # an empty database imports an empty dump without the flag
    _import(repository, empty_dir, public_pem)
    assert repository.imported_version() is not None

    make_document(db_session, make_delivery(db_session, make_source(db_session), "g"), "A")
    with pytest.raises(ImportRefused, match="no documents"):
        _import(repository, empty_dir, public_pem)
    assert db_session.execute(sa.text("SELECT count(*) FROM document")).scalar_one() == 1
    assert db_session.execute(sa.text("SELECT count(*) FROM rights_classification")).scalar_one() == 1

    import_dump(
        repository, dump_dir=empty_dir, public_key_pem=public_pem,
        expected_model_name=MODEL, expected_model_revision=REVISION, now=NOW,
        allow_empty=True,
    )
    retired = db_session.execute(
        sa.text("SELECT count(*) FROM document WHERE retired_at IS NOT NULL")
    ).scalar_one()
    assert retired == 1
