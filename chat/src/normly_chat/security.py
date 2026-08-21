# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import secrets


def generate_session_token() -> str:
    # Same construction as accounts/'s generate_token(): url-safe, ~43
    # characters of entropy from 32 random bytes -- brute-forcing a specific
    # token is not a realistic concern at this length.
    return secrets.token_urlsafe(32)
