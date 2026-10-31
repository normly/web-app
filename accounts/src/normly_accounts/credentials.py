# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Resetting the sign-in data of an account whose mailbox was never proven (ADR-030)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
)


def reset_credentials(session: Session, account_id: uuid.UUID) -> None:
    """
    Every way in that whoever registered the address may hold: sessions,
    Google links, open tokens and the password. The caller holds the account
    row lock (lock order: administrator rows, account row, token rows).
    """
    PostgresAccountSessionRepository(session).delete_sessions_for_account(account_id)
    PostgresAccountGoogleIdentityRepository(session).unlink_all_for_account(account_id)
    PostgresAccountTokenRepository(session).delete_for_account(account_id)
    PostgresAccountRepository(session).clear_password_hash(account_id)
