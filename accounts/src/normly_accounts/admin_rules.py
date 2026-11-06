# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Checks every administrative change shares (ADR-030)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, Publisher, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresPublisherRepository,
)


def snapshot(account: Account) -> dict[str, str | None]:
    """Role and binding for the audit log -- IDs only, never the address."""
    return {
        "role": account.role.value,
        "publisher_id": str(account.publisher_id) if account.publisher_id else None,
    }


def target_account_or_404(session: Session, account_id: uuid.UUID) -> Account:
    account = PostgresAccountRepository(session).get_account_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


def ensure_not_self(admin: Account, target: Account) -> None:
    if admin.id == target.id:
        raise HTTPException(status_code=409, detail="self_action")


def ensure_administrator_remains(session: Session, target: Account) -> None:
    """Call before anything that ends `target`'s active administrator status."""
    if target.role is not Role.ADMINISTRATOR or target.blocked_at is not None:
        return
    others = [
        account_id
        for account_id in PostgresAccountRepository(session).lock_active_administrator_ids()
        if account_id != target.id
    ]
    if not others:
        raise HTTPException(status_code=409, detail="last_administrator")


def publisher_or_400(session: Session, publisher_id: uuid.UUID | None) -> Publisher | None:
    if publisher_id is None:
        return None
    publisher = PostgresPublisherRepository(session).get_publisher(publisher_id)
    if publisher is None:
        raise HTTPException(status_code=400, detail="unknown_publisher")
    return publisher
