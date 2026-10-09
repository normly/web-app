# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""verify_dump and the `verify` CLI command: no database involved."""

import sys
import types

import pytest

from normly_core.exchange import __main__ as cli
from normly_core.exchange.__main__ import main
from normly_core.exchange.exporter import export_dump
from normly_core.exchange.importer import ImportRefused, verify_dump
from normly_core.exchange.signing import generate_keypair
from normly_core.graph.domain import ExchangeColumn

MODEL = "intfloat/multilingual-e5-large"
REVISION = "3d7cfbd"


class _EmptyRepository:
    """Exports a structurally complete dump without rows or a database."""

    def exchange_columns(self, table):
        return [ExchangeColumn("id", "string")]

    def iter_exportable_rows(self, table, *, batch_size=5000):
        return iter(())

    def exportable_deliveries(self):
        return []


@pytest.fixture()
def dump(tmp_path):
    private_pem, public_pem = generate_keypair()
    dump_dir = export_dump(
        _EmptyRepository(), out_dir=tmp_path, dump_version="2026.10.1",
        private_key_pem=private_pem, embedding_model_revision=REVISION,
    )
    return dump_dir, public_pem


def _verify(dump_dir, public_pem, revision=REVISION):
    return verify_dump(
        dump_dir, public_key_pem=public_pem,
        expected_model_name=MODEL, expected_model_revision=revision,
    )


def test_verify_dump_accepts_a_good_dump_and_returns_the_manifest(dump):
    dump_dir, public_pem = dump
    assert _verify(dump_dir, public_pem).dump_version == "2026.10.1"


def test_verify_dump_refuses_a_foreign_key(dump):
    dump_dir, _ = dump
    _, other_public = generate_keypair()
    with pytest.raises(ImportRefused, match="signature"):
        _verify(dump_dir, other_public)


def test_verify_dump_refuses_a_model_revision_mismatch(dump):
    dump_dir, public_pem = dump
    with pytest.raises(ImportRefused, match="revision"):
        _verify(dump_dir, public_pem, revision="other")


def test_verify_dump_refuses_a_tampered_part(dump):
    dump_dir, public_pem = dump
    part = next((dump_dir / "tables").rglob("*.parquet"))
    part.write_bytes(part.read_bytes() + b"x")
    with pytest.raises(ImportRefused, match="checksum"):
        _verify(dump_dir, public_pem)


# --- CLI --------------------------------------------------------------------


@pytest.fixture()
def cli_env(monkeypatch, dump, tmp_path):
    dump_dir, public_pem = dump
    key = tmp_path / "pub.pem"
    key.write_bytes(public_pem)
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    monkeypatch.delenv("NORMLY_KB_PUBLIC_KEY_FILE", raising=False)
    monkeypatch.setenv("NORMLY_EMBEDDING_MODEL_REVISION", REVISION)
    monkeypatch.setenv("NORMLY_KB_BASE_URL", "https://kb.example")
    fake_module = types.ModuleType("normly_core.pipeline.embeddings")
    fake_module.MODEL_NAME = MODEL
    monkeypatch.setitem(sys.modules, "normly_core.pipeline.embeddings", fake_module)
    return dump_dir, key


def test_verify_command_needs_no_database(cli_env, capsys):
    dump_dir, key = cli_env
    assert main(["verify", "--from", str(dump_dir), "--public-key", str(key)]) == 0
    assert "verified knowledge base 2026.10.1" in capsys.readouterr().out


def test_verify_command_fetches_into_a_temp_dir(cli_env, monkeypatch, capsys):
    dump_dir, key = cli_env
    seen = {}

    def fake_fetch(base, version, scratch):
        seen["args"] = (base, version)
        return dump_dir

    monkeypatch.setattr(cli, "fetch_dump", fake_fetch)
    assert main(["verify", "--fetch", "2026.10.1", "--public-key", str(key)]) == 0
    assert seen["args"] == ("https://kb.example", "2026.10.1")


def test_verify_command_reports_refusal_with_exit_1(cli_env, tmp_path, capsys):
    dump_dir, _ = cli_env
    _, other_public = generate_keypair()
    wrong = tmp_path / "wrong.pem"
    wrong.write_bytes(other_public)
    assert main(["verify", "--from", str(dump_dir), "--public-key", str(wrong)]) == 1
    assert "signature" in capsys.readouterr().err


def test_verify_command_reports_fetch_errors(cli_env, monkeypatch, capsys):
    _, key = cli_env

    def boom(*args, **kwargs):
        raise cli.FetchError("HTTP 404 for https://kb.example/x")

    monkeypatch.setattr(cli, "fetch_dump", boom)
    assert main(["verify", "--fetch", "x", "--public-key", str(key)]) == 1
    assert "fetch failed: HTTP 404" in capsys.readouterr().err


def test_verify_command_requires_the_model_revision(cli_env, monkeypatch, capsys):
    dump_dir, key = cli_env
    monkeypatch.delenv("NORMLY_EMBEDDING_MODEL_REVISION")
    assert main(["verify", "--from", str(dump_dir), "--public-key", str(key)]) == 1
    assert "NORMLY_EMBEDDING_MODEL_REVISION" in capsys.readouterr().err


def test_verify_fetch_requires_the_base_url(cli_env, monkeypatch, capsys):
    _, key = cli_env
    monkeypatch.delenv("NORMLY_KB_BASE_URL")
    assert main(["verify", "--fetch", "x", "--public-key", str(key)]) == 1
    assert "NORMLY_KB_BASE_URL" in capsys.readouterr().err


def test_verify_without_any_key_gives_the_clear_error(cli_env, monkeypatch, capsys):
    dump_dir, _ = cli_env

    def _missing():
        raise FileNotFoundError("kb-signing.pub.pem")

    monkeypatch.setattr(cli, "_packaged_public_key", _missing)
    assert main(["verify", "--from", str(dump_dir)]) == 1
    assert "--public-key" in capsys.readouterr().err


def test_key_file_env_var_is_used_when_no_flag_is_given(cli_env, monkeypatch, capsys):
    dump_dir, key = cli_env
    monkeypatch.setenv("NORMLY_KB_PUBLIC_KEY_FILE", str(key))
    assert main(["verify", "--from", str(dump_dir)]) == 0


def test_key_flag_wins_over_the_env_var(cli_env, monkeypatch, tmp_path, capsys):
    dump_dir, key = cli_env
    _, other_public = generate_keypair()
    wrong = tmp_path / "wrong.pem"
    wrong.write_bytes(other_public)
    monkeypatch.setenv("NORMLY_KB_PUBLIC_KEY_FILE", str(wrong))
    assert main(["verify", "--from", str(dump_dir), "--public-key", str(key)]) == 0


def test_unreadable_key_file_env_var_gives_a_clear_error(cli_env, monkeypatch, tmp_path, capsys):
    dump_dir, _ = cli_env
    monkeypatch.setenv("NORMLY_KB_PUBLIC_KEY_FILE", str(tmp_path / "missing.pem"))
    assert main(["verify", "--from", str(dump_dir)]) == 1
    assert "NORMLY_KB_PUBLIC_KEY_FILE" in capsys.readouterr().err
