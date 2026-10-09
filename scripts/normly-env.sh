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
#     unquoted values and after a closing quote, no expansion of any kind (a
#     "$" is literal, unlike in Compose), the last assignment wins. A UTF-8 BOM
#     is ignored.
#   - Only NORMLY_DATABASE_URL, NORMLY_BACKUP_AGE_RECIPIENT,
#     NORMLY_BACKUP_REMOTE, NORMLY_KB_PUBLIC_KEY_FILE, NORMLY_KB_BASE_URL and
#     RCLONE_* / AWS_* (rclone credentials) are exported.
#   - A missing file is allowed (nothing is exported). A missing python3 or a
#     file that exists but cannot be read is an error: message on stderr,
#     non-zero return.
#   - Variables already set in the process environment win over the file, so an
#     operator can override one value for a single run.
normly_load_env() {
  local file="$1" key value out
  [ -f "$file" ] || return 0
  command -v python3 > /dev/null 2>&1 \
    || { echo "normly-env: python3 is required to read $file but was not found" >&2; return 1; }
  # Not a process substitution: its exit status would be lost and a failed
  # read would look like an empty file. NUL bytes cannot live in a variable,
  # so the reader writes to a temporary file whose status is checked first.
  out="$(mktemp)" || { echo "normly-env: cannot create a temporary file" >&2; return 1; }
  if ! python3 - "$file" > "$out" <<'PY'
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
QUOTED = re.compile(r"^(['\"])(.*?)\1(?:\s+#.*)?$")

values = {}
try:
    with open(sys.argv[1], encoding="utf-8-sig", errors="replace") as handle:
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
            quoted = QUOTED.match(value)
            if quoted:
                value = quoted.group(2)
            else:
                value = re.split(r"\s#", value, maxsplit=1)[0].rstrip()
            values[key] = value
except OSError as error:
    sys.stderr.write("normly-env: cannot read %s: %s\n" % (sys.argv[1], error.strerror))
    sys.exit(1)
for key, value in values.items():
    sys.stdout.write(key + "\0" + value + "\0")
PY
  then
    rm -f "$out"
    echo "normly-env: could not load $file; refusing to continue with an empty configuration" >&2
    return 1
  fi
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < "$out"
  rm -f "$out"
}
