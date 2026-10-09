# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Harness: run the real shell scripts with fake binaries first on PATH. Each fake
appends its argv to $CALLS and may be scripted through env vars, so tests can
assert order and arguments of every external command.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]

FAKE = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$CALLS"
override="FAKE_$(basename "$0" | tr 'a-z-' 'A-Z_')_EXIT"
if [ "${!override:-0}" != "0" ]; then exit "${!override}"; fi
fail_on="FAKE_$(basename "$0" | tr 'a-z-' 'A-Z_')_FAIL_ON"
if [ -n "${!fail_on:-}" ]; then
  case " $* " in *"${!fail_on}"*) exit 1 ;; esac
fi
digest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
case "$(basename "$0")" in
  cosign)
    if [ -z "${FAKE_COSIGN_OUT:-}" ]; then
      printf '[{"critical":{"image":{"docker-manifest-digest":"%s"}}}]\\n' "$digest"
      exit 0
    fi ;;
  docker)
    case " $* " in
      *" image inspect "*)
        if [ -n "${FAKE_DOCKER_INSPECT_OUT:-}" ]; then printf '%s\\n' "$FAKE_DOCKER_INSPECT_OUT"
        else ref="${!#}"; printf '["%s@%s"]\\n' "${ref%:*}" "$digest"; fi
        exit 0 ;;
      *ScriptDirectory*) printf '%s\\n' "${FAKE_DOCKER_HEAD_OUT:-rev1}"; exit 0 ;;
      *"exchange info"*)
        [ -z "${FAKE_DOCKER_INFO_EMPTY:-}" ] || exit 0
        printf '%s\\n' "${FAKE_DOCKER_INFO_OUT:-${FAKE_DOCKER_OUT:-2026.10.1}}"; exit 0 ;;
    esac ;;
  rclone)
    # a remote .meta.json fetched by copyto lands as a local file
    if [ "$1" = copyto ]; then
      case "$2" in *:*) case "$3" in *:*) ;; *meta.json)
        meta="${FAKE_RCLONE_META:-}"
        [ -n "$meta" ] || meta='{"alembic_revision": "rev1"}'
        printf '%s' "$meta" > "$3" ;; esac ;; esac
    fi ;;
esac
out="FAKE_$(basename "$0" | tr 'a-z-' 'A-Z_')_OUT"
if [ -n "${!out:-}" ]; then printf '%s\\n' "${!out}"; fi
if [ -n "${FAKE_DOCKER_EXIT_ON:-}" ] && [ "$(basename "$0")" = docker ]; then
  case " $* " in *" $FAKE_DOCKER_EXIT_ON "*) exit 1 ;; esac
fi
# fake tools that write a file named after -o / --file
case "$(basename "$0")" in
  rclone) if [ "$1" = copyto ] && [ -n "${FAKE_RCLONE_KEEP_DIR:-}" ]; then
            cp "$2" "$FAKE_RCLONE_KEEP_DIR/$(basename "$3")"
          fi ;;
  pg_dump) for a in "$@"; do case "$a" in --file=*) : > "${a#--file=}";; esac; done ;;
  age) prev=""; for a in "$@"; do [ "$prev" = "-o" ] && echo cipher > "$a"; prev="$a"; done ;;
esac
exit 0
"""


@pytest.fixture()
def harness(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("docker", "cosign", "rclone", "age", "pg_dump", "pg_restore", "psql", "sha256sum"):
        path = bin_dir / name
        path.write_text(FAKE)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    calls = tmp_path / "calls.log"
    calls.write_text("")
    fake_backup = bin_dir / "fake-normly-backup"
    fake_backup.write_text("#!/usr/bin/env bash\necho 20261009T100000Z-pre-0.1.2\n")
    fake_backup.chmod(fake_backup.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAKE_PSQL_OUT": "rev0001",  # default Alembic head for normly-backup's lookup
        "NORMLY_DIR": str(tmp_path / "normly"),
        "NORMLY_DATABASE_URL": "postgresql+psycopg://u:p@db:5432/normly",
        "NORMLY_BACKUP_AGE_RECIPIENT": "age1recipient",
        "NORMLY_BACKUP_REMOTE": "stackit:bucket",
        "NORMLY_COMPOSE": "docker compose",
        "NORMLY_BACKUP_BIN": str(fake_backup),
    }
    (tmp_path / "normly").mkdir()

    class Harness:
        def run(self, script, *args, extra_env=None, input_text=None):
            return subprocess.run(
                [str(SCRIPTS / script), *args], env={**env, **(extra_env or {})},
                capture_output=True, text=True, input=input_text,
            )

        def calls(self):
            return calls.read_text().splitlines()

        dir = tmp_path / "normly"

    return Harness()
