# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import WorkCreatedVia
from normly_core.graph.postgres.repositories import PostgresWorkRepository


def _register_and_authorize(client, email="watchlist@example.de"):
    response = client.post("/v1/accounts/register", json={"email": email, "password": "correct horse"})
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_work(db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    db_session.commit()
    return work


def test_add_to_watchlist(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)

    response = client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    assert response.status_code == 200
    assert response.json()["work_id"] == str(work.id)


def test_add_to_watchlist_is_idempotent(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)

    client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    response = client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    assert response.status_code == 200

    listing = client.get("/v1/accounts/watchlist", headers=headers)
    assert len(listing.json()) == 1


def test_remove_from_watchlist(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)
    client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)

    response = client.delete(f"/v1/accounts/watchlist/{work.id}", headers=headers)
    assert response.status_code == 200

    listing = client.get("/v1/accounts/watchlist", headers=headers)
    assert listing.json() == []


def test_remove_from_watchlist_when_not_watched_does_not_error(client):
    _, headers = _register_and_authorize(client)
    response = client.delete(f"/v1/accounts/watchlist/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 200


def test_watchlist_endpoints_require_authentication(client):
    response = client.get("/v1/accounts/watchlist")
    assert response.status_code == 401
