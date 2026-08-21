# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import secrets

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_token() -> str:
    """
    A cryptographically random, URL-safe token for session tokens and
    one-time account_token values alike. `token_urlsafe(32)` yields ~43
    characters, well above any brute-force-relevant length.
    """
    return secrets.token_urlsafe(32)
