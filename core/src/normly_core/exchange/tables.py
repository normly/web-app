# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Which table belongs to which backup/exchange group.

Three groups (TP4 spec, Teil 2):

* knowledge -- the free knowledge base. Reproducible from source deliveries,
  distributed as a versioned dump (Teil 3), never part of the daily backup.
* user -- accounts, chats, watchlists, notifications. Small, irreplaceable,
  backed up daily. Rows reference knowledge rows by foreign key, which is why
  the dump must keep IDs unchanged.
* pipeline -- state of the local ingestion (review queue). Neither exported
  nor backed up.

Both lists are ordered parents-first so inserts can run front to back and
deletes back to front. `test_tables.py` fails when a table is added to the ORM
without being placed here.
"""

KNOWLEDGE_TABLES: tuple[str, ...] = (
    "source",
    "delivery",
    "work",
    "document",
    "document_designation",
    "document_title",
    "rights_classification",
    "edge",
    "segment",
    "embedding",
    "document_embedding",
)

USER_TABLES: tuple[str, ...] = (
    "account",
    "account_session",
    "account_google_identity",
    "account_token",
    "oauth_state",
    "watchlist",
    "notification",
    "rights_notification_baseline",
    "notified_edge",
    "chat_session",
    "chat_message",
    "chat_message_citation",
    "rate_limit_bucket",
)

PIPELINE_STATE_TABLES: tuple[str, ...] = ("identity_resolution_case",)

#: Written by the dump import itself; belongs to no group above.
SYSTEM_TABLES: tuple[str, ...] = ("knowledge_base_import",)

#: Exists in the database but not in the ORM metadata.
UNMANAGED_TABLES: tuple[str, ...] = ("alembic_version",)


def group_tables(name: str) -> tuple[str, ...]:
    if name == "knowledge":
        return KNOWLEDGE_TABLES
    if name == "user":
        return USER_TABLES
    if name == "pipeline":
        return PIPELINE_STATE_TABLES
    if name == "all":
        return (
            *USER_TABLES,
            *reversed(KNOWLEDGE_TABLES),
            *PIPELINE_STATE_TABLES,
            *SYSTEM_TABLES,
            *UNMANAGED_TABLES,
        )
    raise ValueError(f"unknown table group: {name!r}")
