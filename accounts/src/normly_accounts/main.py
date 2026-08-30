# accounts/src/normly_accounts/main.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import create_engine

from normly_accounts.email import RecordingEmailSender, SmtpEmailSender
from normly_accounts.errors import COMMON_ERROR_RESPONSES, register_exception_handlers
from normly_accounts.routers.account_management import account_management_router
from normly_accounts.routers.email_change import email_change_router
from normly_accounts.routers.email_verification import email_verification_router
from normly_accounts.routers.google import google_router
from normly_accounts.routers.login import login_router
from normly_accounts.routers.magic_link import magic_link_router
from normly_accounts.routers.password import password_router
from normly_accounts.routers.password_reset import password_reset_router
from normly_accounts.routers.profile import profile_router
from normly_accounts.routers.registration import registration_router
from normly_accounts.routers.session import session_router
from normly_accounts.routers.sessions import sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ["NORMLY_DATABASE_URL"]
    engine = create_engine(database_url)
    app.state.engine = engine

    smtp_host = os.environ.get("NORMLY_SMTP_HOST")
    if smtp_host:
        app.state.email_sender = SmtpEmailSender(
            host=smtp_host,
            port=int(os.environ.get("NORMLY_SMTP_PORT", "587")),
            from_address=os.environ.get("NORMLY_SMTP_FROM", "no-reply@normly.example"),
            username=os.environ.get("NORMLY_SMTP_USERNAME"),
            password=os.environ.get("NORMLY_SMTP_PASSWORD"),
        )
    else:
        # No SMTP configured -- fall back to a recording sender so the
        # service still boots in local/dev environments. Tests override
        # this explicitly regardless (see conftest.py).
        app.state.email_sender = RecordingEmailSender()

    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="normly Accounts",
        version="1.0.0",
        description="Registration, login, and session management.",
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    # Passing the shared responses to every router is what puts the app-wide
    # 400/503 handlers into the OpenAPI schema; without it a client generator
    # cannot know those bodies exist.
    app.include_router(registration_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(login_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(magic_link_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(password_reset_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(password_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(session_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(sessions_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(email_verification_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(email_change_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(google_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(profile_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(account_management_router, responses=COMMON_ERROR_RESPONSES)
    return app


app = create_app()
