#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_DIR="${ROOT_DIR}/core/tests/fixtures"

USE_COMPOSE=false
for arg in "$@"; do
  if [ "$arg" = "--compose" ]; then
    USE_COMPOSE=true
  fi
done

if [ "$USE_COMPOSE" = true ]; then
  echo "==> Seeding sample data via Docker Compose (using api container)..."
  docker compose exec -e NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@db:5432/normly" \
    api python -m normly_core.pipeline.cli ingest --directory /app/core/tests/fixtures dguv
  echo "==> Successfully seeded sample data in Docker Compose!"
else
  export NORMLY_DATABASE_URL="${NORMLY_DATABASE_URL:-postgresql+psycopg://normly:normly@localhost:5432/normly}"
  echo "==> Seeding sample data locally to ${NORMLY_DATABASE_URL}..."

  TMP_DIR="$(mktemp -d /tmp/normly-seed-XXXXXX)"
  trap 'rm -rf "${TMP_DIR}"' EXIT

  cp "${FIXTURES_DIR}/dguv_sample_vorschrift.pdf" "${TMP_DIR}/"

  PYTHON_BIN="python3"
  if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  fi

  "${PYTHON_BIN}" -m normly_core.pipeline.cli ingest --directory "${TMP_DIR}" dguv
  echo "==> Successfully seeded sample data!"
fi
