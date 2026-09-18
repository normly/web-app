#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -d ".venv" ]; then
  echo "Error: Virtual environment .venv not found. Please run ./scripts/dev-setup.sh first." >&2
  exit 1
fi

export NORMLY_DATABASE_URL="${NORMLY_DATABASE_URL:-postgresql+psycopg://normly:normly@localhost:5432/normly}"
export NORMLY_API_BASE_URL="${NORMLY_API_BASE_URL:-http://localhost:8002}"
export NORMLY_ACCOUNTS_BASE_URL="${NORMLY_ACCOUNTS_BASE_URL:-http://localhost:8001}"
export NORMLY_CHAT_BASE_URL="${NORMLY_CHAT_BASE_URL:-http://localhost:8003}"
export NORMLY_OLLAMA_BASE_URL="${NORMLY_OLLAMA_BASE_URL:-http://localhost:11434}"
export NORMLY_OLLAMA_MODEL="${NORMLY_OLLAMA_MODEL:-llama3.1:8b-instruct-q4_0}"

PIDS=()

cleanup() {
  echo ""
  echo "==> Shutting down services..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  echo "==> All services stopped."
}

trap cleanup EXIT INT TERM

echo "=========================================="
echo " Starting normly local development services"
echo "=========================================="
echo " Database:  ${NORMLY_DATABASE_URL}"
echo " Accounts:  http://localhost:8001 (Docs: /docs)"
echo " API:       http://localhost:8002 (Docs: /docs)"
echo " Chat:      http://localhost:8003 (Docs: /docs)"
echo " Frontend:  http://localhost:3000"
echo "=========================================="
echo "Press Ctrl+C to stop all services."
echo ""

# Start Accounts service (8001)
(
  cd accounts
  exec ../.venv/bin/uvicorn normly_accounts.main:app --host 127.0.0.1 --port 8001 --reload
) &
PIDS+=($!)

# Start API service (8002)
(
  cd api
  exec ../.venv/bin/uvicorn normly_api.main:app --host 127.0.0.1 --port 8002 --reload
) &
PIDS+=($!)

# Start Chat service (8003)
(
  cd chat
  exec ../.venv/bin/uvicorn normly_chat.main:app --host 127.0.0.1 --port 8003 --reload
) &
PIDS+=($!)

# Start Frontend (3000)
(
  cd frontend
  exec npm run dev
) &
PIDS+=($!)

# Wait for all background processes
wait
