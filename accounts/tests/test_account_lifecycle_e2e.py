# accounts/tests/test_account_lifecycle_e2e.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io
import re

from PIL import Image


def _make_1x1_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_full_account_profile_lifecycle(client, email_sender):
    # 1. Register.
    register = client.post(
        "/v1/accounts/register",
        json={"email": "lifecycle@example.de", "password": "correct horse battery staple"},
    )
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    # 2. Set first/last name.
    profile_update = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["first_name"] == "Jamie"

    # 3. Upload an avatar -- a minimal valid 1x1 PNG.
    png_1x1 = _make_1x1_png()
    avatar_upload = client.post(
        "/v1/accounts/avatar", files={"avatar": ("avatar.png", io.BytesIO(png_1x1), "image/png")},
        headers=headers,
    )
    assert avatar_upload.status_code == 200
    assert avatar_upload.json()["has_avatar"] is True
    # The avatar upload must not have clobbered the name set in step 2 --
    # profile.py and Task 4's set_avatar both write to the same account row.
    assert avatar_upload.json()["first_name"] == "Jamie"

    # 4. Request and confirm an email change.
    email_change = client.post(
        "/v1/accounts/email/change", json={"new_email": "lifecycle-new@example.de"},
        headers=headers,
    )
    assert email_change.status_code == 200
    # The confirmation link's token isn't observable from this test's HTTP
    # surface (it's only ever emailed) -- extract it from the captured
    # outgoing email, the same way test_email_change.py already does for the
    # equivalent single-endpoint case.
    token = re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)
    confirm = client.get(
        "/v1/accounts/email/confirm",
        params={"token": token, "email": "lifecycle-new@example.de"},
    )
    assert confirm.status_code == 200

    # 5. Change the password.
    password_change = client.post(
        "/v1/accounts/password",
        json={"current_password": "correct horse battery staple", "new_password": "new secret"},
        headers=headers,
    )
    assert password_change.status_code == 200
    relogin = client.post(
        "/v1/accounts/login", json={"email": "lifecycle-new@example.de", "password": "new secret"}
    )
    assert relogin.status_code == 200

    # 6. List sessions (now two: the original registration session plus the
    # relogin from step 5) and revoke the older one.
    sessions = client.get("/v1/accounts/sessions", headers=headers).json()
    assert len(sessions) == 2
    other_session_id = [s["id"] for s in sessions if not s["is_current"]][0]
    revoke = client.delete(f"/v1/accounts/sessions/{other_session_id}", headers=headers)
    assert revoke.status_code == 200

    # 7. Export -- reflects the changed email, name, and avatar.
    export = client.get("/v1/accounts/export", headers=headers)
    assert export.status_code == 200
    exported_account = export.json()["account"]
    assert exported_account["email"] == "lifecycle-new@example.de"
    assert exported_account["first_name"] == "Jamie"
    assert exported_account["avatar_data_url"] is not None

    # 8. Delete the account (needs the *new* password from step 5).
    delete = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "new secret"}, headers=headers,
    )
    assert delete.status_code == 200

    # 9. Every new endpoint this plan added must now reject the dead session.
    assert client.get("/v1/accounts/session", headers=headers).status_code == 401
    assert client.patch(
        "/v1/accounts/profile", json={"first_name": "x", "last_name": "y"}, headers=headers,
    ).status_code == 401
    assert client.get("/v1/accounts/sessions", headers=headers).status_code == 401
    assert client.get("/v1/accounts/export", headers=headers).status_code == 401
    assert client.post(
        "/v1/accounts/email/change", json={"new_email": "irrelevant@example.de"}, headers=headers,
    ).status_code == 401
    assert client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "x"},
        headers=headers,
    ).status_code == 401
