#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Mirror the working tree to the STACKIT VM for building images there
# (roadmap decision E8). Never syncs .env* (except .env.example), .claude or build artefacts.
#
# Usage: scripts/sync-to-vm.sh [user@host]   (default: ubuntu@213.17.23.196)
set -euo pipefail

TARGET="${1:-ubuntu@213.17.23.196}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.next' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'test-results' \
  --exclude '.worktrees' --exclude '.superpowers' --exclude 'site' \
  --exclude '.claude' --include '.env.example' --exclude '.env*' --exclude 'data' \
  "$REPO_ROOT/" "$TARGET:/opt/normly/src/"

echo "synced to $TARGET:/opt/normly/src"
