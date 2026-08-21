# accounts/src/normly_accounts/dependencies.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from normly_accounts.google_oauth import build_google_oauth_client_from_env


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()


def get_email_sender(request: Request):
    return request.app.state.email_sender


def get_google_oauth_client():
    return build_google_oauth_client_from_env()
