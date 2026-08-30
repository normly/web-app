# accounts/tests/test_get_current_account.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.dependencies import get_current_account, get_session


@pytest.fixture()
def probe_app(db_session):
    app = FastAPI()

    @app.get("/probe")
    def probe(account=Depends(get_current_account)) -> dict:
        return {"account_id": str(account.id), "email": account.email}

    app.dependency_overrides[get_session] = lambda: db_session
    return app


@pytest.fixture()
def probe_client(probe_app):
    with TestClient(probe_app) as client:
        yield client


def test_valid_bearer_token_resolves_the_account(probe_client, db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="probe@example.de", password_hash=None
    )
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="probe-token", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = probe_client.get(
        "/probe", headers={"Authorization": f"Bearer {session.session_token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"account_id": str(account.id), "email": "probe@example.de"}


def test_missing_header_returns_401(probe_client):
    response = probe_client.get("/probe")
    assert response.status_code == 401


def test_malformed_header_returns_401(probe_client):
    response = probe_client.get("/probe", headers={"Authorization": "not-a-bearer-token"})
    assert response.status_code == 401


def test_unknown_token_returns_401(probe_client):
    response = probe_client.get(
        "/probe", headers={"Authorization": "Bearer does-not-exist"}
    )
    assert response.status_code == 401


def test_expired_session_returns_401(probe_client, db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="expired@example.de", password_hash=None
    )
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="expired-token", created_at=now,
        expires_at=now - timedelta(seconds=1),
    )

    response = probe_client.get(
        "/probe", headers={"Authorization": f"Bearer {session.session_token}"}
    )

    assert response.status_code == 401
