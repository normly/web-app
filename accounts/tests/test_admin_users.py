# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import Role

from tests.admin_support import make_account, make_admin, make_publisher


def test_list_filters_and_pages(client, db_session):
    _, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    make_account(db_session, "p@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id)
    make_account(db_session, "blocked@example.de", blocked=True)
    client.post("/v1/admin/invitations", headers=headers, json={"email": "new@example.de", "role": "user"})

    page = client.get("/v1/admin/users?page_size=10", headers=headers).json()
    assert page["total"] == 4 and page["page"] == 1
    assert {r["status"] for r in page["rows"]} == {"active", "blocked", "invited"}

    blocked = client.get("/v1/admin/users?status=blocked", headers=headers).json()
    assert [r["email"] for r in blocked["rows"]] == ["blocked@example.de"]
    publishers = client.get("/v1/admin/users?role=publisher", headers=headers).json()
    assert publishers["rows"][0]["publisher_name"] == "VDE Verlag"
    assert client.get("/v1/admin/users?page_size=7", headers=headers).status_code == 400
    assert client.get("/v1/admin/users?sort=password_hash", headers=headers).status_code == 400


def test_summary_and_role_matrix(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "blocked@example.de", blocked=True)

    summary = client.get("/v1/admin/users/summary", headers=headers).json()
    assert summary["accounts_total"] == 2
    assert summary["accounts_by_role"] == {"user": 1, "publisher": 0, "administrator": 1}
    assert summary["most_frequent_block_reason"] == "abuse"

    matrix = client.get("/v1/admin/role-matrix", headers=headers).json()
    assert matrix["roles"] == ["anonymous", "user", "publisher", "administrator"]
    management = next(r for r in matrix["rows"] if r["capability"] == "user_management")
    assert management["values"]["administrator"] == "yes"
    usage = next(r for r in matrix["rows"] if r["capability"] == "usage_and_demand")
    assert usage["values"]["publisher"] == "aggregated_own"
