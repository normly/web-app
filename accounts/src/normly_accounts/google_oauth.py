# accounts/src/normly_accounts/google_oauth.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True)
class GoogleProfile:
    subject_id: str
    email: str


class GoogleOAuthClient(Protocol):
    def build_authorization_url(self, redirect_uri: str, state: str) -> str: ...
    def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile: ...


class HttpxGoogleOAuthClient:
    """
    Real Google OAuth 2.0 Authorization Code flow client, implemented
    directly against Google's documented HTTP endpoints via httpx rather
    than a heavier official client library -- the flow is two HTTP calls
    (token exchange, userinfo fetch), not enough surface to justify the
    extra dependency.
    """

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
        }
        return f"{_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile:
        with httpx.Client() as http:
            token_response = http.post(
                _TOKEN_ENDPOINT,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = http.get(
                _USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            profile = userinfo_response.json()

        return GoogleProfile(subject_id=profile["sub"], email=profile["email"])


def build_google_oauth_client_from_env() -> HttpxGoogleOAuthClient:
    return HttpxGoogleOAuthClient(
        client_id=os.environ.get("NORMLY_GOOGLE_CLIENT_ID", ""),
        client_secret=os.environ.get("NORMLY_GOOGLE_CLIENT_SECRET", ""),
    )
