# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_accounts.google_oauth import GoogleProfile


def test_openapi_schema_documents_every_v1_endpoint(client):
    schema = client.get("/openapi.json").json()

    paths = set(schema["paths"].keys())
    assert paths == {
        "/v1/accounts/register",
        "/v1/accounts/login",
        "/v1/accounts/logout",
        "/v1/accounts/session",
        "/v1/accounts/verify-email",
        "/v1/accounts/password-reset/request",
        "/v1/accounts/password-reset/confirm",
        "/v1/accounts/google/login",
        "/v1/accounts/google/callback",
        "/v1/accounts/magic-link/request",
        "/v1/accounts/magic-link/confirm",
    }
    assert schema["info"]["license"]["name"] == "Apache-2.0"


def test_openapi_schema_documents_the_error_responses_with_their_model(client):
    """
    The error bodies are only useful to a client generator if the schema names
    them. Asserting the $ref, not just the status code, is what catches a
    `responses={400: {"description": ...}}` that documents no model at all.
    """
    schema = client.get("/openapi.json").json()
    error_ref = "#/components/schemas/ErrorResponse"

    # The 400/503 pair comes from the app-wide handlers, so every operation
    # on every path declares it.
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status in ("400", "503"):
                assert operation["responses"][status]["content"]["application/json"][
                    "schema"
                ]["$ref"] == error_ref, f"{method.upper()} {path} {status}"


def test_full_email_password_lifecycle(client, db_session):
    from sqlalchemy import select
    from normly_core.graph.domain import AccountTokenPurpose
    from normly_core.graph.postgres.orm import AccountTokenORM
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    register = client.post(
        "/v1/accounts/register",
        json={"email": "capstone@example.de", "password": "first password here"},
    )
    assert register.status_code == 200
    token = register.json()["session_token"]

    session_check = client.get(
        "/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert session_check.status_code == 200
    assert session_check.json()["email"] == "capstone@example.de"

    account = PostgresAccountRepository(db_session).get_account_by_email("capstone@example.de")
    verify_row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.EMAIL_VERIFICATION,
        )
    ).scalar_one()
    verify = client.get("/v1/accounts/verify-email", params={"token": verify_row.token})
    assert verify.status_code == 200

    logout = client.post("/v1/accounts/logout", json={"session_token": token})
    assert logout.status_code == 200
    assert client.get(
        "/v1/accounts/session", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401

    client.post("/v1/accounts/password-reset/request", json={"email": "capstone@example.de"})
    reset_row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.PASSWORD_RESET,
        )
    ).scalar_one()
    reset = client.post(
        "/v1/accounts/password-reset/confirm",
        json={"token": reset_row.token, "new_password": "second password here"},
    )
    assert reset.status_code == 200

    relogin = client.post(
        "/v1/accounts/login",
        json={"email": "capstone@example.de", "password": "second password here"},
    )
    assert relogin.status_code == 200


def test_google_and_magic_link_can_resolve_to_the_same_account(client, db_session):
    from normly_accounts.dependencies import get_google_oauth_client

    class _FakeGoogleOAuthClient:
        def build_authorization_url(self, redirect_uri, state):
            return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

        def exchange_code(self, code, redirect_uri):
            return GoogleProfile(
                subject_id="capstone-sub", email="both@example.de", email_verified=True
            )

    client.app.dependency_overrides[get_google_oauth_client] = _FakeGoogleOAuthClient

    google_login = client.get(
        "/v1/accounts/google/callback", params={"code": "c", "state": "s"}
    )
    assert google_login.status_code == 200
    account_id = google_login.json()["account"]["id"]

    client.post("/v1/accounts/magic-link/request", json={"email": "both@example.de"})
    from sqlalchemy import select
    from normly_core.graph.domain import AccountTokenPurpose
    from normly_core.graph.postgres.orm import AccountTokenORM
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    account = PostgresAccountRepository(db_session).get_account_by_email("both@example.de")
    token_row = db_session.execute(
        select(AccountTokenORM).where(
            AccountTokenORM.account_id == account.id,
            AccountTokenORM.purpose == AccountTokenPurpose.MAGIC_LINK,
        )
    ).scalar_one()
    magic_confirm = client.post(
        "/v1/accounts/magic-link/confirm", json={"token": token_row.token}
    )

    assert magic_confirm.status_code == 200
    assert magic_confirm.json()["account"]["id"] == account_id
