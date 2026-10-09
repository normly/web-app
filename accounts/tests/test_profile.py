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
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Tester"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Jamie"
    assert body["last_name"] == "Tester"


def test_update_profile_requires_authorization(client):
    response = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Tester"},
    )
    assert response.status_code == 401


def test_update_profile_leaves_an_omitted_field_untouched(client):
    _, headers = _register_and_authorize(client)
    client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Tester"},
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
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Tester"},
        headers=headers,
    )

    response = client.patch(
        "/v1/accounts/profile", json={"first_name": None, "last_name": "Tester"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] is None
    assert body["last_name"] == "Tester"


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


def test_upload_avatar_resizes_to_256_and_serves_it_via_the_avatar_endpoint(client):
    _, headers = _register_and_authorize(client)
    image_bytes = _make_test_image()

    upload_response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", image_bytes, "image/jpeg")},
        headers=headers,
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["has_avatar"] is True

    avatar_response = client.get("/v1/accounts/avatar", headers=headers)
    assert avatar_response.status_code == 200
    resized = Image.open(io.BytesIO(avatar_response.content))
    assert resized.size == (256, 256)


def test_delete_avatar_clears_it(client, db_session):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.delete("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 200
    assert response.json()["has_avatar"] is False


def test_get_avatar_returns_404_when_unset(client):
    _, headers = _register_and_authorize(client)

    response = client.get("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 404


def test_get_avatar_returns_the_image_with_correct_headers(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.get("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, max-age=0, must-revalidate"
    assert "etag" in response.headers
    resized = Image.open(io.BytesIO(response.content))
    assert resized.size == (256, 256)


def test_get_avatar_returns_304_when_if_none_match_matches(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )
    first = client.get("/v1/accounts/avatar", headers=headers)
    etag = first.headers["etag"]

    response = client.get(
        "/v1/accounts/avatar", headers={**headers, "If-None-Match": etag},
    )

    assert response.status_code == 304
    assert response.content == b""


def test_get_avatar_returns_200_when_if_none_match_does_not_match(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.get(
        "/v1/accounts/avatar", headers={**headers, "If-None-Match": '"stale-etag"'},
    )

    assert response.status_code == 200
    assert len(response.content) > 0


def test_get_avatar_requires_authorization(client):
    response = client.get("/v1/accounts/avatar")
    assert response.status_code == 401


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


def test_update_profile_rejects_an_invalid_notification_preference(client):
    _, headers = _register_and_authorize(client)
    response = client.patch(
        "/v1/accounts/profile", json={"notification_preference": "bogus"}, headers=headers
    )
    assert response.status_code == 400
    assert "notification_preference" in response.json()["detail"]
