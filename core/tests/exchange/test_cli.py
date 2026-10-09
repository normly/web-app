# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

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
