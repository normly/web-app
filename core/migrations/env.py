# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from normly_core.graph.postgres.orm import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

if not config.get_main_option("sqlalchemy.url"):
    if env_url := os.environ.get("NORMLY_DATABASE_URL"):
        config.set_main_option("sqlalchemy.url", env_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("NORMLY_DATABASE_URL")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = dict(config.get_section(config.config_ini_section, {}))
    if not configuration.get("sqlalchemy.url"):
        if resolved_url := config.get_main_option("sqlalchemy.url") or os.environ.get("NORMLY_DATABASE_URL"):
            configuration["sqlalchemy.url"] = resolved_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
