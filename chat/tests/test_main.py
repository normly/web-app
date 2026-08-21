# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_app_boots_and_serves_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["license"]["name"] == "Apache-2.0"
