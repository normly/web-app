# shellcheck shell=bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Shared by normly-deploy and normly-backup (source it, do not run it).
#
# The VM's .env is written for Docker Compose, whose dialect allows unquoted
# values with spaces, '#' and '$' (NORMLY_BRAND_COLOR_HSL=222 89% 55%). Bash
# cannot source such a file, so it is parsed here instead and only the keys the
# scripts need are exported. Nothing in the file is ever evaluated.

# normly_load_env FILE
#   - KEY=VALUE lines, optional "export " prefix, blank lines and # comments
#     ignored, one pair of matching quotes stripped, " # comment" stripped from
#     unquoted values, no expansion of any kind, the last assignment wins.
#   - Only NORMLY_DATABASE_URL, NORMLY_BACKUP_*, NORMLY_KB_PUBLIC_KEY_FILE,
#     NORMLY_KB_BASE_URL and RCLONE_* / AWS_* (rclone credentials) are exported.
#   - Variables already set in the process environment win over the file, so an
#     operator can override one value for a single run.
normly_load_env() {
  local file="$1" key value
  [ -f "$file" ] || return 0
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < <(python3 - "$file" <<'PY'
import re
import sys

ALLOWED = {
    "NORMLY_DATABASE_URL",
    "NORMLY_BACKUP_AGE_RECIPIENT",
    "NORMLY_BACKUP_REMOTE",
    "NORMLY_KB_PUBLIC_KEY_FILE",
    "NORMLY_KB_BASE_URL",
}
PREFIXES = ("RCLONE_", "AWS_")
LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")

values = {}
with open(sys.argv[1], encoding="utf-8", errors="replace") as handle:
    for raw in handle:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key not in ALLOWED and not key.startswith(PREFIXES):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = re.split(r"\s#", value, maxsplit=1)[0].rstrip()
        values[key] = value
for key, value in values.items():
    sys.stdout.write(key + "\0" + value + "\0")
PY
  )
}
