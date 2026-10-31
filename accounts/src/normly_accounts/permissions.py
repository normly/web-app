# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
What each role may do -- the one definition both the server-side guard and the
"What the roles see" dialog read, so the two cannot drift apart (ADR-030).

Values: "yes", "no", "own" (only the person's own data), "own_aggregated"
(only the publisher's own content, aggregated, never per person), "all".
Planned capabilities are shown in the dialog but guard nothing yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from normly_core.graph.domain import Role

MATRIX_ROLES = ("anonymous", "user", "publisher", "administrator")
USER_MANAGEMENT = "user_management"


@dataclass(frozen=True)
class Capability:
    key: str
    planned: bool
    values: dict[str, str]


def _row(key: str, anonymous: str, user: str, publisher: str, administrator: str,
         *, planned: bool = False) -> Capability:
    return Capability(key=key, planned=planned, values={
        "anonymous": anonymous, "user": user, "publisher": publisher,
        "administrator": administrator,
    })


CAPABILITIES: tuple[Capability, ...] = (
    _row("search_and_free_content", "yes", "yes", "yes", "yes"),
    # Anonymous chats are not stored; the conversation lives in the tab (ADR-027).
    _row("chat_and_history", "no", "own", "own", "own"),
    _row("chats_of_others", "no", "no", "no", "no"),
    _row("personal_usage_data_of_others", "no", "no", "no", "no"),
    _row("usage_and_demand", "no", "no", "own_aggregated", "all", planned=True),
    _row("deliveries", "no", "no", "own", "all", planned=True),
    _row("billing", "no", "no", "own", "all", planned=True),
    _row(USER_MANAGEMENT, "no", "no", "no", "yes"),
)

_BY_KEY = {capability.key: capability for capability in CAPABILITIES}


def allows(role: Role, key: str) -> bool:
    capability = _BY_KEY[key]
    return not capability.planned and capability.values[role.value] != "no"
