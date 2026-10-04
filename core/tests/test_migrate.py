# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

# core/tests has no __init__.py, so conftest constants are not importable;
# same definition as core/tests/conftest.py:13.
CORE_DIR = Path(__file__).resolve().parents[1]


def _alembic_head() -> str:
    cfg = Config(str(CORE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _run_migrate(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**os.environ, **env}, capture_output=True, text=True, timeout=300,
    )


def test_migrate_module_upgrades_to_head_and_is_idempotent(db_url):
    env = {"NORMLY_DATABASE_URL": db_url, "NORMLY_CORE_DIR": str(CORE_DIR)}

    first = _run_migrate(env)
    assert first.returncode == 0, first.stderr
    assert "migrations: at head" in first.stdout

    second = _run_migrate(env)
    assert second.returncode == 0, second.stderr

    engine = create_engine(db_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()
    assert version == _alembic_head()


def test_migrate_module_fails_without_database_url():
    env = {k: v for k, v in os.environ.items() if k != "NORMLY_DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**env, "NORMLY_CORE_DIR": str(CORE_DIR)}, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "NORMLY_DATABASE_URL" in result.stderr


def test_migrate_module_fails_when_core_dir_has_no_alembic_ini(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "normly_core.migrate"],
        env={**os.environ, "NORMLY_DATABASE_URL": "postgresql+psycopg://x:y@localhost:1/z",
             "NORMLY_CORE_DIR": str(tmp_path)},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "alembic.ini" in result.stderr
