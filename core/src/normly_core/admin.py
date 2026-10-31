# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Bootstrapping the first administrator of an instance (ADR-030)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
)


class AdminGrantError(Exception):
    pass


def grant_administrator(session: Session, *, email: str, now: datetime) -> str:
    accounts = PostgresAccountRepository(session)
    account = accounts.get_account_by_email(email)
    if account is None:
        raise AdminGrantError(f"no account with the address {email}; sign up first")
    if account.blocked_at is not None:
        raise AdminGrantError("the account is blocked; unblock it first")
    if account.role is Role.ADMINISTRATOR:
        return "unchanged"
    accounts.set_role(account.id, role=Role.ADMINISTRATOR, publisher_id=None)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ADMINISTRATOR_GRANTED_CLI, actor_account_id=None, occurred_at=now,
        target_account_id=account.id,
        details={
            "before": {
                "role": account.role.value,
                "publisher_id": str(account.publisher_id) if account.publisher_id else None,
            },
            "after": {"role": Role.ADMINISTRATOR.value, "publisher_id": None},
        },
    )
    return "granted"
