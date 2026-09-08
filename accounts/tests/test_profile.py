# accounts/tests/test_profile.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io

from PIL import Image

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)


def _register_and_authorize(client):
    response = client.post(
        "/v1/accounts/register", json={"email": "profile@example.de", "password": "correct horse"}
    )
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_test_image(size=(800, 600), color=(255, 0, 0)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_update_profile_sets_first_and_last_name(client):
    _, headers = _register_and_authorize(client)

    response = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Jamie"
    assert body["last_name"] == "Weber"


def test_update_profile_requires_authorization(client):
    response = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
    )
    assert response.status_code == 401


def test_update_profile_leaves_an_omitted_field_untouched(client):
    _, headers = _register_and_authorize(client)
    client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )

    response = client.patch(
        "/v1/accounts/profile", json={"last_name": "NewLastName"}, headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Jamie"
    assert body["last_name"] == "NewLastName"


def test_update_profile_explicit_null_still_clears_a_field(client):
    _, headers = _register_and_authorize(client)
    client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )

    response = client.patch(
        "/v1/accounts/profile", json={"first_name": None, "last_name": "Weber"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] is None
    assert body["last_name"] == "Weber"


def test_upload_avatar_resizes_to_256_and_returns_data_url(client):
    _, headers = _register_and_authorize(client)
    image_bytes = _make_test_image()

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", image_bytes, "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 200
    data_url = response.json()["avatar_data_url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    import base64
    stored = base64.b64decode(data_url.split(",", 1)[1])
    resized = Image.open(io.BytesIO(stored))
    assert resized.size == (256, 256)


def test_upload_avatar_rejects_a_file_that_is_too_large(client):
    _, headers = _register_and_authorize(client)
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.bin", oversized, "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 400


def test_upload_avatar_rejects_a_non_image_file(client):
    _, headers = _register_and_authorize(client)

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.txt", b"not an image", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 400


def test_upload_avatar_rejects_a_truncated_image_instead_of_crashing(client):
    _, headers = _register_and_authorize(client)
    valid_image = _make_test_image()
    truncated = valid_image[: len(valid_image) // 2]

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", truncated, "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "avatar must be a valid image file"


def test_delete_avatar_clears_it(client, db_session):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.delete("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 200
    assert response.json()["avatar_data_url"] is None


def test_update_notification_preference(client):
    _, headers = _register_and_authorize(client)
    response = client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["notification_preference"] == "email"


def test_updating_only_the_name_leaves_notification_preference_unchanged(client):
    _, headers = _register_and_authorize(client)
    client.patch("/v1/accounts/profile", json={"notification_preference": "both"}, headers=headers)
    response = client.patch("/v1/accounts/profile", json={"first_name": "Jamie"}, headers=headers)
    assert response.json()["notification_preference"] == "both"
