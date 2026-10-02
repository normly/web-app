#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${ROOT_DIR}/scripts/dev-tmux.sh"
SESSION_NAME="${NORMLY_TMUX_SESSION:-normly-dev}"
FRONTEND_URL="${NORMLY_FRONTEND_URL:-http://localhost:3000}"
OLLAMA_MODEL="${NORMLY_OLLAMA_MODEL:-llama3.1:8b-instruct-q4_0}"
COMPOSE=(docker compose --profile chat-llm)
READY_FILE="${TMPDIR:-/tmp}/normly-dev-${SESSION_NAME}.ready"
export NORMLY_DEV_READY_FILE="$READY_FILE"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Error: %s is required but was not found in PATH.\n' "$1" >&2
    exit 1
  fi
}

session_exists() {
  tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

print_status() {
  cat <<EOF

normly development environment
================================
Frontend: ${FRONTEND_URL}
Chat API: http://localhost:8003
Graph API: http://localhost:8002
Accounts: http://localhost:8001
Database: localhost:5432
Compose: profile chat-llm
Tmux session: ${SESSION_NAME}
Panes: application logs | Ollama logs | working shell

Useful commands:
  docker compose ps
  docker compose logs -f chat
  ./scripts/seed-data.sh --compose
  make dev-stop

Detach without stopping services: Ctrl-b d

EOF
}

working_pane() {
  local attempts=0

  printf 'Starting normly development environment...\n'
  printf 'Waiting for all startup checks to pass...\n'
  until [ -f "$NORMLY_DEV_READY_FILE" ]; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 300 ]; then
      printf 'Startup did not complete within 300 seconds.\n' >&2
      exec "${SHELL:-/bin/bash}"
    fi
    sleep 1
  done

  print_status
  printf 'Startup checks passed.\n'
  printf 'Ollama model: loaded (%s)\n\n' "$OLLAMA_MODEL"
  exec "${SHELL:-/bin/bash}"
}

ollama_pane() {
  printf 'Starting Ollama service...\n'
  exec "${COMPOSE[@]}" up --build ollama
}

open_browser() {
  case "$(uname -s)" in
    Darwin)
      open "$FRONTEND_URL" >/dev/null 2>&1 &
      ;;
    Linux)
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
      else
        printf 'Frontend is ready at %s (xdg-open is not installed).\n' "$FRONTEND_URL"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*)
      start "" "$FRONTEND_URL" >/dev/null 2>&1 &
      ;;
    *)
      printf 'Frontend is ready at %s. Open it in a browser.\n' "$FRONTEND_URL"
      ;;
  esac
}

wait_for_frontend() {
  local attempts=0
  printf 'Waiting for the frontend at %s...\n' "$FRONTEND_URL"
  until curl --fail --silent --show-error --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 180 ]; then
      printf 'Error: frontend did not become ready within 180 seconds.\n' >&2
      return 1
    fi
    sleep 1
  done
}

model_is_available() {
  local models
  models="$("${COMPOSE[@]}" exec -T ollama ollama list 2>/dev/null)" || return 1
  case "$models" in
    *"$OLLAMA_MODEL"*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_ollama_model() {
  local attempts=0
  local models

  printf 'Waiting for Ollama...\n'
  until models="$("${COMPOSE[@]}" exec -T ollama ollama list 2>/dev/null)"; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 180 ]; then
      printf 'Error: Ollama did not become ready within 180 seconds.\n' >&2
      return 1
    fi
    sleep 1
  done

  case "$models" in
    *"$OLLAMA_MODEL"*)
      printf 'Ollama model is already available: %s\n' "$OLLAMA_MODEL"
      ;;
    *)
      printf 'Pulling Ollama model: %s\n' "$OLLAMA_MODEL"
      "${COMPOSE[@]}" exec -T ollama ollama pull "$OLLAMA_MODEL"
      ;;
  esac

  until model_is_available; do
    sleep 1
  done
  printf 'Ollama model is loaded: %s\n' "$OLLAMA_MODEL"
}

start_session() {
  require_command docker
  require_command tmux
  require_command curl

  if session_exists; then
    printf 'Tmux session %s is already running.\n' "$SESSION_NAME"
    exec tmux attach-session -t "$SESSION_NAME"
  fi

  cd "$ROOT_DIR"
  rm -f "$READY_FILE"
  tmux new-session -d -s "$SESSION_NAME" -n dev -c "$ROOT_DIR" \
    "${COMPOSE[*]} up --build db migrate accounts api chat frontend"
  tmux split-window -v -t "$SESSION_NAME:dev" -c "$ROOT_DIR" \
    "$SCRIPT_PATH ollama"
  tmux split-window -h -t "$SESSION_NAME:dev.1" -c "$ROOT_DIR" \
    "$SCRIPT_PATH working"
  tmux select-pane -t "$SESSION_NAME:dev.0"

  if ! wait_for_frontend || ! ensure_ollama_model; then
    printf 'Startup failed; stopping the tmux session.\n' >&2
    rm -f "$READY_FILE"
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
    exit 1
  fi

  printf 'ready\n' >"$READY_FILE"
  open_browser
  exec tmux attach-session -t "$SESSION_NAME"
}

stop_session() {
  require_command docker
  require_command tmux

  cd "$ROOT_DIR"
  "${COMPOSE[@]} down"
  if session_exists; then
    tmux kill-session -t "$SESSION_NAME"
  fi
}

attach_session() {
  require_command tmux
  if ! session_exists; then
    printf 'Tmux session %s is not running. Use make dev first.\n' "$SESSION_NAME" >&2
    exit 1
  fi
  exec tmux attach-session -t "$SESSION_NAME"
}

case "${1:-start}" in
  start) start_session ;;
  working) working_pane ;;
  ollama) ollama_pane ;;
  attach) attach_session ;;
  stop) stop_session ;;
  *)
    printf 'Usage: %s {start|attach|stop}\n' "${0##*/}" >&2
    exit 2
    ;;
esac
