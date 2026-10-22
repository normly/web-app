# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timezone

from normly_chat.accounts_client import ChatAccountIdentity
from normly_chat.budget_guard import QuotaStatus
from normly_chat.dependencies import get_accounts_client, get_budget_guard


class _FixedAccountsClient:
    def __init__(self, identity):
        self._identity = identity

    def validate_session(self, session_token):
        return self._identity


class _StatusGuard:
    def __init__(self):
        self.asked = []

    def status(self, *, pool, user_key):
        self.asked.append((pool, user_key))
        return QuotaStatus(
            used=7, limit=30, resets_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            pool_exhausted=True, pool_resets_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )


def test_usage_requires_an_account(client):
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(None)

    assert client.get("/v1/chat/usage").status_code == 401
    assert client.get("/v1/chat/usage", headers={"Authorization": "Bearer t"}).status_code == 401


def test_usage_returns_the_registered_quota_status(client):
    identity = ChatAccountIdentity(account_id=uuid.uuid4(), email="user@example.org")
    guard = _StatusGuard()
    client.app.dependency_overrides[get_accounts_client] = lambda: _FixedAccountsClient(identity)
    client.app.dependency_overrides[get_budget_guard] = lambda: guard

    response = client.get("/v1/chat/usage", headers={"Authorization": "Bearer t"})

    assert response.status_code == 200
    assert response.json() == {
        "used": 7, "limit": 30, "resets_at": "2026-10-23T00:00:00Z",
        "pool_exhausted": True, "pool_resets_at": "2026-11-01T00:00:00Z",
    }
    assert guard.asked == [("registered", f"account:{identity.account_id}")]
