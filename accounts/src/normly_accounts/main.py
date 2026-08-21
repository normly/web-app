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
from normly_accounts.routers.email_verification import email_verification_router
from normly_accounts.routers.google import google_router
from normly_accounts.routers.login import login_router
from normly_accounts.routers.password_reset import password_reset_router
from normly_accounts.routers.registration import registration_router
from normly_accounts.routers.session import session_router


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
    app.include_router(registration_router)
    app.include_router(login_router)
    app.include_router(password_reset_router)
    app.include_router(session_router)
    app.include_router(email_verification_router)
    app.include_router(google_router)
    return app


app = create_app()
