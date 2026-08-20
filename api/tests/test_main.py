# api/tests/test_main.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors


def test_openapi_schema_is_served_and_licensed_apache_2_0(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["license"]["name"] == "Apache-2.0"
