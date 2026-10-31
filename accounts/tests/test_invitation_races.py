# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Requests already in flight when an invitation accept resets an unverified
account (ADR-030). The concurrent accept is simulated at the exact point it
would commit: between the request's first read and its session write.
"""

import threading
import time
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

import normly_accounts.routers.login as login_module
from normly_accounts.security import verify_password
from tests.admin_support import auth_headers, make_account, make_admin


def _sessions_deleted_before_extend(monkeypatch, db_session, account_id):
    original = PostgresAccountSessionRepository.extend_session

    def extend_after_concurrent_delete(self, session_id, new_expires_at):
        PostgresAccountSessionRepository(db_session).delete_sessions_for_account(account_id)
        return original(self, session_id, new_expires_at)

    monkeypatch.setattr(
        PostgresAccountSessionRepository, "extend_session", extend_after_concurrent_delete,
    )


def test_session_check_refuses_a_session_deleted_while_in_flight(client, db_session, monkeypatch):
    account = make_account(db_session, "squatter@example.de")
    headers = auth_headers(db_session, account)
    _sessions_deleted_before_extend(monkeypatch, db_session, account.id)

    response = client.get("/v1/accounts/session", headers=headers)

    assert (response.status_code, response.json()["detail"]) == (401, "invalid or expired session")


def test_guarded_route_refuses_a_session_deleted_while_in_flight(client, db_session, monkeypatch):
    """The role is already the invited one when the account is read; the guard must not pass."""
    admin, headers = make_admin(db_session)
    _sessions_deleted_before_extend(monkeypatch, db_session, admin.id)

    response = client.get("/v1/admin/role-matrix", headers=headers)

    assert (response.status_code, response.json()["detail"]) == (401, "invalid or expired session")


def test_login_refuses_when_the_password_was_cleared_after_verification(
    client, db_session, monkeypatch,
):
    account = make_account(db_session, "squatter@example.de", password="attacker pw",
                           role=Role.USER)

    def verify_then_concurrent_accept(password, password_hash):
        verified = verify_password(password, password_hash)
        PostgresAccountRepository(db_session).clear_password_hash(account.id)
        return verified

    monkeypatch.setattr(login_module, "verify_password", verify_then_concurrent_accept)

    response = client.post("/v1/accounts/login",
                           json={"email": "squatter@example.de", "password": "attacker pw"})

    assert (response.status_code, response.json()["detail"]) == (401, "invalid email or password")
    assert PostgresAccountSessionRepository(db_session).list_sessions_for_account(account.id) == []


# --- Real concurrency: a second connection plays the accept transaction. ---

def _wait_until_a_backend_waits_for_a_lock(connection, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        waiting = connection.execute(sa.text(
            "SELECT count(*) FROM pg_locks WHERE NOT granted"
        )).scalar_one()
        if waiting:
            return
        time.sleep(0.05)
    raise AssertionError("the request never waited for the accept transaction's lock")


def _in_thread(call):
    result = {}
    thread = threading.Thread(target=lambda: result.setdefault("response", call()))
    thread.start()
    return thread, result


def _commit_accept_reset_while_request_waits(migrated_engine, account_id, call):
    """
    Opens the accept transaction (row lock, cleared password, deleted
    sessions), starts the request, waits until Postgres shows it blocked on
    that transaction, then commits -- the interleaving the review described.
    """
    with migrated_engine.connect() as accept_conn, migrated_engine.connect() as observer:
        accept = Session(bind=accept_conn)
        accounts = PostgresAccountRepository(accept)
        accounts.lock_account(account_id)
        PostgresAccountSessionRepository(accept).delete_sessions_for_account(account_id)
        accounts.clear_password_hash(account_id)
        accept.flush()

        thread, result = _in_thread(call)
        _wait_until_a_backend_waits_for_a_lock(observer)
        accept.commit()
        thread.join(timeout=10)
        assert not thread.is_alive()
        return result["response"]


def _committed_account(real_client, password: str):
    email = f"race-{uuid.uuid4().hex}@example.de"
    registered = real_client.post("/v1/accounts/register", json={"email": email, "password": password})
    body = registered.json()
    return email, uuid.UUID(body["account"]["id"]), body["session_token"]


def test_in_flight_login_loses_against_a_concurrent_reset(real_client, migrated_engine):
    email, account_id, _ = _committed_account(real_client, "attacker pw")

    response = _commit_accept_reset_while_request_waits(
        migrated_engine, account_id,
        lambda: real_client.post("/v1/accounts/login", json={"email": email, "password": "attacker pw"}),
    )

    assert response.status_code == 401
    with migrated_engine.connect() as connection:
        sessions = PostgresAccountSessionRepository(Session(bind=connection))
        assert sessions.list_sessions_for_account(account_id) == []


def test_in_flight_session_request_loses_against_a_concurrent_reset(real_client, migrated_engine):
    _, account_id, token = _committed_account(real_client, "attacker pw")

    response = _commit_accept_reset_while_request_waits(
        migrated_engine, account_id,
        lambda: real_client.get("/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}),
    )

    assert response.status_code == 401
