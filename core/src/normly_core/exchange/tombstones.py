# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Tombstone support file (ADR-026, Erweiterung 2).

The backup carries the retired identifier rows and their foreign-key parents
as one small JSON document, because no knowledge-base dump contains them and
user rows may point at them. The rollback restores the file after the dump
import and before the user data. This module only knows the file format; the
rows are read and written by the repository.

    {"format": 1, "created_at": "<ISO-8601>", "rows": {"source": [...], ...}}
"""

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

from normly_core.exchange.tables import TOMBSTONE_SUPPORT_TABLES

TOMBSTONE_FORMAT = 1

__all__ = [
    "TOMBSTONE_FORMAT",
    "TOMBSTONE_SUPPORT_TABLES",
    "build_document",
    "parse_document",
    "row_count",
]


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def build_document(rows: Mapping[str, list[dict[str, Any]]], *, created_at: datetime) -> str:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    unknown = set(rows) - set(TOMBSTONE_SUPPORT_TABLES)
    if unknown:
        raise ValueError(f"unknown tombstone support tables: {sorted(unknown)}")
    document = {
        "format": TOMBSTONE_FORMAT,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "rows": {name: list(rows.get(name, [])) for name in TOMBSTONE_SUPPORT_TABLES},
    }
    return json.dumps(document, default=_json_default, ensure_ascii=False, indent=1) + "\n"


def parse_document(text: str) -> tuple[dict[str, list[dict[str, Any]]], datetime]:
    """Rows keep their JSON values (timestamps as ISO strings); raises ValueError."""
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("the document must be a JSON object")
    if document.get("format") != TOMBSTONE_FORMAT:
        raise ValueError(
            f"unsupported tombstone format {document.get('format')!r} "
            f"(expected {TOMBSTONE_FORMAT})"
        )
    try:
        created_at = datetime.fromisoformat(document["created_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("created_at is missing or not an ISO-8601 timestamp") from exc
    if created_at.tzinfo is None:
        raise ValueError("created_at carries no timezone")
    rows = document.get("rows")
    if not isinstance(rows, dict) or set(rows) != set(TOMBSTONE_SUPPORT_TABLES):
        raise ValueError(f"rows must hold exactly the tables {list(TOMBSTONE_SUPPORT_TABLES)}")
    for name, table_rows in rows.items():
        if not isinstance(table_rows, list) or not all(isinstance(r, dict) for r in table_rows):
            raise ValueError(f"rows.{name} must be a list of objects")
    return rows, created_at


def row_count(rows: Mapping[str, list[dict[str, Any]]]) -> int:
    return sum(len(table_rows) for table_rows in rows.values())
