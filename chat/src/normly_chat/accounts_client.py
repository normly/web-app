# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx


# Same reasoning as api_client.py's: accounts/ is a sibling service, so an
# explicit short timeout beats httpx's implicit 5s default.
_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class ChatAccountIdentity:
    account_id: uuid.UUID
    email: str


class AccountsClient:
    """
    Thin httpx wrapper over accounts/'s GET /v1/accounts/session -- the
    contract that service was built to expose to every future consumer that
    needs to resolve a session token to an identity (see the accounts design
    spec). An invalid/expired/missing token resolves to None, never an
    exception: chat/ treats "no usable account token" as the normal anonymous
    case, not an error.
    """

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def validate_session(self, session_token: str) -> ChatAccountIdentity | None:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
            response = http.get(
                f"{self._base_url}/v1/accounts/session",
                headers={"Authorization": f"Bearer {session_token}"},
            )
        if response.status_code == 401:
            return None
        response.raise_for_status()
        body = response.json()
        return ChatAccountIdentity(account_id=uuid.UUID(body["account_id"]), email=body["email"])
