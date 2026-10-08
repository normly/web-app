# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Run the Alembic migrations to head from environment configuration.

`alembic.ini` deliberately leaves `sqlalchemy.url` empty so no connection
string is ever committed; tests inject the URL programmatically
(core/tests/conftest.py). This module is the same injection as a command,
for the Compose `migrate` one-shot service and for operators:

    NORMLY_DATABASE_URL=postgresql+psycopg://... python -m normly_core.migrate

Idempotent: a second run against a migrated database is a no-op.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

DATABASE_URL_ENV_VAR = "NORMLY_DATABASE_URL"
#: Directory holding `alembic.ini` and `migrations/`; the container image
#: copies `core/` to /app/core, local runs point this at the checkout.
CORE_DIR_ENV_VAR = "NORMLY_CORE_DIR"
DEFAULT_CORE_DIR = Path("/app/core")


def _alembic_config(database_url: str, core_dir: Path) -> Config:
    config = Config(str(core_dir / "alembic.ini"))
    config.set_main_option("script_location", str(core_dir / "migrations"))
    # configparser interpolation treats "%" specially; percent-encoded
    # passwords (p%2Fx) must survive the round trip.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_to_head(database_url: str, core_dir: Path) -> None:
    command.upgrade(_alembic_config(database_url, core_dir), "head")


def main(argv: list[str] | None = None) -> int:
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if not database_url:
        print(f"{DATABASE_URL_ENV_VAR} environment variable is required", file=sys.stderr)
        return 1
    core_dir = Path(os.environ.get(CORE_DIR_ENV_VAR, DEFAULT_CORE_DIR))
    if not (core_dir / "alembic.ini").is_file():
        print(
            f"no alembic.ini in {core_dir} (set {CORE_DIR_ENV_VAR} to the core/ directory)",
            file=sys.stderr,
        )
        return 1
    upgrade_to_head(database_url, core_dir)
    print("migrations: at head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
