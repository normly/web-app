# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Builds accounts in a given state directly through the repositories."""

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import Account, BlockReason, Publisher, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresPublisherRepository,
)

from normly_accounts.security import generate_token, hash_password


def make_publisher(db_session, name: str = "VDE Verlag") -> Publisher:
    return PostgresPublisherRepository(db_session).create_publisher(
        name=name, created_at=datetime.now(timezone.utc)
    )


def make_account(
    db_session, email: str, *, role: Role = Role.USER, publisher_id=None,
    password: str | None = None, blocked: bool = False, locale: str = "de",
) -> Account:
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(
        email=email, password_hash=hash_password(password) if password else None, locale=locale,
    )
    if role is not Role.USER:
        repo.set_role(account.id, role=role, publisher_id=publisher_id)
    if blocked:
        repo.block_account(account.id, reason=BlockReason.ABUSE, blocked_at=datetime.now(timezone.utc))
    db_session.flush()
    return repo.get_account_by_id(account.id)


def auth_headers(db_session, account: Account) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = generate_token()
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token=token, created_at=now,
        expires_at=now + timedelta(days=30),
    )
    db_session.flush()
    return {"Authorization": f"Bearer {token}"}


def make_admin(db_session, email: str = "admin@normly.example") -> tuple[Account, dict[str, str]]:
    admin = make_account(db_session, email, role=Role.ADMINISTRATOR)
    return admin, auth_headers(db_session, admin)
