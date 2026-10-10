# shellcheck shell=bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Shared by normly-deploy, normly-backup and normly-cleanup (source it, do not run it).
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
  local file="$1" items i
  [ -f "$file" ] || return 0
  command -v python3 > /dev/null 2>&1 \
    || { echo "normly-env: python3 is required to read $file but was not found" >&2; return 1; }
  # The reader ends its output with a sentinel. Without it (python failed or
  # was killed) the load fails instead of looking like an empty file. Nothing
  # is written to disk, so no value can be left behind in a temporary file.
  mapfile -d '' items < <(python3 - "$file" <<'PY'
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
sys.stdout.write("NORMLY_ENV_END\0")
PY
  )
  if [ "${#items[@]}" -lt 1 ] || [ "${items[-1]}" != "NORMLY_ENV_END" ]; then
    echo "normly-env: could not load $file; refusing to continue with an empty configuration" >&2
    return 1
  fi
  for ((i = 0; i + 1 < ${#items[@]} - 1; i += 2)); do
    if [ -z "${!items[i]+x}" ]; then
      export "${items[i]}=${items[i+1]}"
    fi
  done
}

# normly_check_tombstones FILE
#   Host-side sanity check of a tombstone support document (format 1: a JSON
#   object whose "rows" holds exactly the five tables, each a list). Prints the
#   reason on stderr and returns non-zero when it does not hold. Used before an
#   irreversible step on both sides: backup (before encrypting and uploading) and
#   rollback (before the database is dropped).
normly_check_tombstones() {
  python3 -c '
import json, sys
TABLES = ["source", "delivery", "work", "document", "edge"]
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        doc = json.load(handle)
except (OSError, ValueError) as error:
    sys.exit("not readable JSON (%s)" % error)
if not isinstance(doc, dict) or doc.get("format") != 1:
    sys.exit("not a format-1 document")
rows = doc.get("rows")
if not isinstance(rows, dict) or sorted(rows) != sorted(TABLES):
    sys.exit("rows must hold exactly: " + ", ".join(TABLES))
if not all(isinstance(rows[name], list) for name in TABLES):
    sys.exit("every table must be a list")' "$1"
}

# normly_check_deletions FILE
#   Host-side sanity check of a deletion log document (format 1: a JSON object
#   with a created_at timestamp and a list "entries" of objects whose kind is
#   account or chat_session, entity_id a UUID, deleted_at a timestamp). Same
#   rules as normly_core.exchange.deletions.parse_document, which a test keeps
#   in step. Prints the reason on stderr and returns non-zero when it does not
#   hold. Used by the rollback before the database is dropped.
normly_check_deletions() {
  python3 -c '
import json, sys, uuid
from datetime import datetime
def stamp(value, what):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        sys.exit(what + " is missing or not an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        sys.exit(what + " carries no timezone")
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        doc = json.load(handle)
except (OSError, ValueError) as error:
    sys.exit("not readable JSON (%s)" % error)
if not isinstance(doc, dict) or type(doc.get("format")) is not int or doc["format"] != 1:
    sys.exit("not a format-1 document")
stamp(doc.get("created_at"), "created_at")
entries = doc.get("entries")
if not isinstance(entries, list):
    sys.exit("entries must be a list")
for entry in entries:
    if not isinstance(entry, dict):
        sys.exit("every entry must be an object")
    if entry.get("kind") not in ("account", "chat_session"):
        sys.exit("unknown kind %r" % (entry.get("kind"),))
    try:
        uuid.UUID(entry.get("entity_id"))
    except (AttributeError, TypeError, ValueError):
        sys.exit("entity_id is missing or not a UUID")
    stamp(entry.get("deleted_at"), "deleted_at")' "$1"
}
