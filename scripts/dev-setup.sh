#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=========================================="
echo " normly Local Development Environment Setup"
echo "=========================================="

# 1. Check Prerequisites
echo "==> Checking prerequisites..."

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required for PostgreSQL with pgvector, but is not installed or not in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: Python 3 (>= 3.11, recommended 3.12) is required." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: Node.js (recommended v22) and npm are required." >&2
  exit 1
fi

# Warning for Linux users regarding libgl1 and libglib2.0-0
if [ "$(uname -s)" = "Linux" ]; then
  if ! ldconfig -p 2>/dev/null | grep -q "libGL.so.1"; then
    echo "NOTICE: libgl1 / libglib2.0-0 might be missing. If Docling PDF extraction fails, install via: sudo apt-get install -y libgl1 libglib2.0-0"
  fi
fi

# 2. Start PostgreSQL container with pgvector
echo "==> Ensuring PostgreSQL (pgvector) container is running..."
if docker ps --format '{{.Names}}' | grep -q '^normly-pg$'; then
  echo "PostgreSQL container 'normly-pg' is already running."
elif docker ps -a --format '{{.Names}}' | grep -q '^normly-pg$'; then
  echo "Starting existing 'normly-pg' container..."
  docker start normly-pg
else
  echo "Creating and starting new 'normly-pg' container..."
  docker run -d --name normly-pg \
    -p 5432:5432 \
    -e POSTGRES_USER=normly \
    -e POSTGRES_PASSWORD=normly \
    -e POSTGRES_DB=normly \
    pgvector/pgvector:pg16
fi

echo "Waiting for database to be ready..."
until docker exec normly-pg pg_isready -U normly -d normly >/dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready."

# 3. Setup Python Virtual Environment
echo "==> Setting up Python virtual environment in .venv..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip setuptools wheel --quiet
echo "Installing Python packages in editable mode..."
.venv/bin/pip install -e ./core -e ./accounts -e ./api -e ./chat

# 4. Run Migrations
echo "==> Applying database migrations..."
export NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@localhost:5432/normly"
(cd core && ../.venv/bin/alembic upgrade head)

# 5. Seed sample data
echo "==> Seeding initial sample data..."
./scripts/seed-data.sh

# 6. Setup Frontend
echo "==> Setting up frontend dependencies..."
(cd frontend && npm ci)

echo ""
echo "=========================================="
echo " Setup complete!"
echo "=========================================="
echo "To run the application locally:"
echo "  ./scripts/dev-run.sh"
echo ""
echo "To run with Docker Compose instead:"
echo "  docker compose up --build"
echo "=========================================="
