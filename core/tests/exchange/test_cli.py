# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import stat
import sys
import types

import pytest

from normly_core.exchange import __main__ as cli
from normly_core.exchange.__main__ import main
from normly_core.exchange.tables import KNOWLEDGE_TABLES


def test_tables_command_prints_group(capsys):
    assert main(["tables", "knowledge"]) == 0
    assert capsys.readouterr().out.split() == list(KNOWLEDGE_TABLES)


def test_keygen_writes_both_keys_and_refuses_overwrite(tmp_path, capsys):
    private, public = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == 0
    assert oct(private.stat().st_mode & 0o777) == "0o600"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == 1
    assert "exists" in capsys.readouterr().err


def test_command_without_database_url_fails(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    assert main(["info"]) == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err


def test_import_requires_a_source():
    with pytest.raises(SystemExit):
        main(["import"])


def test_missing_packaged_key_gives_a_clear_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.setenv("NORMLY_EMBEDDING_MODEL_REVISION", "r")

    def _missing():
        raise FileNotFoundError("kb-signing.pub.pem")

    monkeypatch.setattr(cli, "_packaged_public_key", _missing)
    assert main(["import", "--from", str(tmp_path)]) == 1
    assert "--public-key" in capsys.readouterr().err


def test_keygen_sets_restricted_modes(tmp_path):
    private, public = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == 0
    assert stat.S_IMODE(private.stat().st_mode) == 0o600
    assert stat.S_IMODE(public.stat().st_mode) == 0o644


def test_fetch_without_base_url_fails(monkeypatch, capsys, tmp_path):
    key = tmp_path / "pub.pem"
    key.write_bytes(b"x")
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.setenv("NORMLY_EMBEDDING_MODEL_REVISION", "r")
    monkeypatch.delenv("NORMLY_KB_BASE_URL", raising=False)
    assert main(["import", "--fetch", "latest", "--public-key", str(key)]) == 1
    assert "NORMLY_KB_BASE_URL" in capsys.readouterr().err


class _FakeSession:
    instances: list = []

    def __init__(self, engine):
        self.rolled_back = self.committed = False
        _FakeSession.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True


class _FakeEngine:
    def dispose(self):
        pass


@pytest.fixture()
def fake_db(monkeypatch, tmp_path):
    _FakeSession.instances = []
    key = tmp_path / "pub.pem"
    key.write_bytes(b"x")
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.setenv("NORMLY_EMBEDDING_MODEL_REVISION", "r")
    monkeypatch.setenv("NORMLY_KB_BASE_URL", "https://kb.example")
    monkeypatch.setattr(cli, "create_engine", lambda url: _FakeEngine())
    monkeypatch.setattr(cli, "Session", _FakeSession)
    monkeypatch.setattr(cli, "PostgresKnowledgeExchangeRepository", lambda session: object())
    fake_module = types.ModuleType("normly_core.pipeline.embeddings")
    fake_module.MODEL_NAME = "m"
    monkeypatch.setitem(sys.modules, "normly_core.pipeline.embeddings", fake_module)
    return key


@pytest.mark.parametrize("exc_name", ["ImportRefused", "ImportBlockedError"])
def test_import_refusal_rolls_back_and_exits_1(monkeypatch, capsys, tmp_path, fake_db, exc_name):
    from normly_core.exchange.importer import ImportRefused
    from normly_core.graph.domain import ImportBlockedError

    error = {
        "ImportRefused": ImportRefused("nope"),
        "ImportBlockedError": ImportBlockedError("watchlist", "nope"),
    }[exc_name]

    def refuse(*args, **kwargs):
        raise error

    monkeypatch.setattr(cli, "import_dump", refuse)
    assert main(["import", "--from", str(tmp_path), "--public-key", str(fake_db)]) == 1
    err = capsys.readouterr().err
    assert "import refused:" in err and "nope" in err
    (session,) = _FakeSession.instances
    assert session.rolled_back and not session.committed


def test_fetch_failure_exits_1_with_message(monkeypatch, capsys, fake_db):
    def boom(*args, **kwargs):
        raise cli.FetchError("HTTP 404 for https://kb.example/latest")

    monkeypatch.setattr(cli, "fetch_dump", boom)
    assert main(["import", "--fetch", "latest", "--public-key", str(fake_db)]) == 1
    assert "fetch failed: HTTP 404" in capsys.readouterr().err
    (session,) = _FakeSession.instances
    assert session.rolled_back and not session.committed


@pytest.mark.parametrize("flags,expected", [([], False), (["--allow-empty"], True)])
def test_import_passes_allow_empty_through(monkeypatch, tmp_path, fake_db, flags, expected):
    seen = {}

    def fake_import(*args, **kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(dump_version="v")

    monkeypatch.setattr(cli, "import_dump", fake_import)
    assert main(["import", "--from", str(tmp_path), "--public-key", str(fake_db), *flags]) == 0
    assert seen["allow_empty"] is expected


# --- tombstone support commands ---------------------------------------------


class _FakeTombstoneRepository:
    restored: list = []

    def __init__(self, session):
        pass

    def export_tombstone_support(self):
        return {
            "source": [], "delivery": [], "work": [{"id": "w1"}], "document": [], "edge": [],
        }

    def restore_tombstone_support(self, rows, *, restored_at):
        if rows["work"] and rows["work"][0].get("bad"):
            raise ValueError("row columns do not match the table")
        _FakeTombstoneRepository.restored.append((rows, restored_at))


@pytest.fixture()
def fake_tombstone_db(monkeypatch):
    _FakeSession.instances = []
    _FakeTombstoneRepository.restored = []
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    monkeypatch.delenv("NORMLY_EMBEDDING_MODEL_REVISION", raising=False)
    monkeypatch.setattr(cli, "create_engine", lambda url: _FakeEngine())
    monkeypatch.setattr(cli, "Session", _FakeSession)
    monkeypatch.setattr(cli, "PostgresKnowledgeExchangeRepository", _FakeTombstoneRepository)


@pytest.mark.parametrize("command", ["export-tombstones", "import-tombstones"])
def test_tombstone_commands_require_the_database_url(monkeypatch, capsys, command):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    assert main([command]) == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err


def test_export_tombstones_prints_a_valid_document_without_committing(
    capsys, fake_tombstone_db
):
    import json

    assert main(["export-tombstones"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["format"] == 1
    assert list(document["rows"]) == ["source", "delivery", "work", "document", "edge"]
    assert document["rows"]["work"] == [{"id": "w1"}]
    (session,) = _FakeSession.instances
    assert not session.committed


def test_import_tombstones_restores_commits_and_reports(
    monkeypatch, capsys, fake_tombstone_db
):
    import io

    text = (
        '{"format": 1, "created_at": "2026-11-01T12:00:00+00:00", "rows": '
        '{"source": [], "delivery": [], "work": [{"id": "w1"}], "document": [], "edge": []}}'
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert main(["import-tombstones"]) == 0
    assert "restored tombstone support: 1 rows" in capsys.readouterr().out
    ((rows, restored_at),) = _FakeTombstoneRepository.restored
    assert rows["work"] == [{"id": "w1"}] and restored_at.isoformat().startswith("2026-11-01T12")
    (session,) = _FakeSession.instances
    assert session.committed and not session.rolled_back


@pytest.mark.parametrize("text", ["garbage", '{"format": 7}'])
def test_import_tombstones_rejects_a_broken_document(
    monkeypatch, capsys, fake_tombstone_db, text
):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert main(["import-tombstones"]) == 1
    assert "invalid tombstone document" in capsys.readouterr().err
    assert _FakeTombstoneRepository.restored == []
    assert not any(s.committed for s in _FakeSession.instances)


def test_import_tombstones_rolls_back_when_the_repository_rejects_rows(
    monkeypatch, capsys, fake_tombstone_db
):
    import io

    text = (
        '{"format": 1, "created_at": "2026-11-01T12:00:00+00:00", "rows": '
        '{"source": [], "delivery": [], "work": [{"bad": 1}], "document": [], "edge": []}}'
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert main(["import-tombstones"]) == 1
    assert "invalid tombstone document" in capsys.readouterr().err
    (session,) = _FakeSession.instances
    assert session.rolled_back and not session.committed


def test_packaged_public_key_is_a_valid_ed25519_public_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    key = load_pem_public_key(cli._packaged_public_key())

    assert isinstance(key, Ed25519PublicKey)
