# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Deletion log document for the rollback (user-data lifecycle).

A rollback restores user data from a backup, which brings back accounts and
chats deleted since. The rollback exports the deletions made after the backup
before it drops the database and replays them afterwards. The document holds
identifiers only, never personal data:

    {"format": 1, "created_at": "<ISO-8601>",
     "entries": [{"kind": "account"|"chat_session", "entity_id": "<uuid>",
                  "deleted_at": "<ISO-8601>"}, ...]}

scripts/normly-env.sh (`normly_check_deletions`) checks the same rules on the
host; keep both in step (a test compares them).
"""

import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

DELETION_FORMAT = 1
DELETION_KINDS = ("account", "chat_session")

__all__ = ["DELETION_FORMAT", "DELETION_KINDS", "build_document", "entries_after", "parse_document"]


def entries_after(
    entries: Iterable[tuple[str, uuid.UUID, datetime]], since: datetime
) -> list[tuple[str, uuid.UUID, datetime]]:
    """Entries strictly later than `since` (the backup already holds the others)."""
    return [entry for entry in entries if entry[2] > since]


def build_document(
    entries: Iterable[tuple[str, uuid.UUID, datetime]], *, created_at: datetime
) -> str:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    rows = []
    for kind, entity_id, deleted_at in entries:
        if kind not in DELETION_KINDS:
            raise ValueError(f"unknown deletion kind {kind!r}")
        if deleted_at.tzinfo is None:
            raise ValueError("deleted_at must be timezone-aware")
        rows.append((deleted_at.astimezone(timezone.utc), kind, str(entity_id)))
    document = {
        "format": DELETION_FORMAT,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "entries": [
            {"kind": kind, "entity_id": entity_id, "deleted_at": deleted_at.isoformat()}
            for deleted_at, kind, entity_id in sorted(rows)
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=1) + "\n"


def _timestamp(value: Any, what: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} is missing or not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{what} carries no timezone")


def parse_document(text: str) -> list[tuple[str, uuid.UUID]]:
    """The deletions to replay, in document order; raises ValueError."""
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("the document must be a JSON object")
    fmt = document.get("format")
    if type(fmt) is not int or fmt != DELETION_FORMAT:
        raise ValueError(
            f"unsupported deletion format {fmt!r} (expected {DELETION_FORMAT})"
        )
    _timestamp(document.get("created_at"), "created_at")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError("entries must be a list")
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("every entry must be an object")
        kind = entry.get("kind")
        if kind not in DELETION_KINDS:
            raise ValueError(f"unknown deletion kind {kind!r}")
        entity_id = entry.get("entity_id")
        try:
            parsed_id = uuid.UUID(entity_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("entity_id is missing or not a UUID") from exc
        _timestamp(entry.get("deleted_at"), "deleted_at")
        result.append((kind, parsed_id))
    return result
