# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Every route under /v1/admin is guarded, discovered from the app rather than
listed: a route added later is covered without anyone touching this file.

The requests carry dummy path IDs, no query parameters and an empty body.
That is enough because FastAPI resolves dependencies -- the guard among
them -- before it validates path, query and body; a validation error
(400 here) instead of 401/403 would therefore show a route without a guard.
"""

import re
import uuid

import pytest
from fastapi.routing import APIRoute

from normly_core.graph.domain import Role

from normly_accounts.main import create_app
from tests.admin_support import auth_headers, make_account, make_publisher


def _admin_endpoints() -> list[tuple[str, str]]:
    endpoints = []
    for route in create_app().routes:
        if isinstance(route, APIRoute) and route.path.startswith("/v1/admin"):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                endpoints.append((method, route.path))
    return endpoints


ADMIN_ENDPOINTS = _admin_endpoints()


def _call(client, method: str, path: str, headers: dict[str, str] | None = None):
    concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
    kwargs = {"headers": headers or {}}
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        kwargs["json"] = {}
    return client.request(method, concrete, **kwargs)


def test_admin_routes_are_discovered():
    # Guards the guard test: an empty list would pass every case below.
    assert len(ADMIN_ENDPOINTS) >= 13


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_admin_route_refuses_anonymous_requests(client, method, path):
    response = _call(client, method, path)
    assert response.status_code == 401, response.text


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
@pytest.mark.parametrize("role", [Role.USER, Role.PUBLISHER])
def test_admin_route_refuses_non_administrators(client, db_session, method, path, role):
    publisher_id = make_publisher(db_session).id if role is Role.PUBLISHER else None
    account = make_account(
        db_session, f"{role.value}@example.de", role=role, publisher_id=publisher_id,
    )

    response = _call(client, method, path, auth_headers(db_session, account))

    assert (response.status_code, response.json()["detail"]) == (403, "forbidden")
