# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.domain import (
    AccountTokenPurpose,
    ChatMessageRole,
    NotificationPreference,
    NotificationTriggerType,
    Role,
    WorkCreatedVia,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
    PostgresChatRepository,
    PostgresInvitationRepository,
    PostgresNotificationRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)

from tests.admin_support import make_account, make_admin, make_publisher


def _invite(client, headers, db_session, email, **extra):
    client.post("/v1/admin/invitations", headers=headers, json={"email": email, **extra})
    return PostgresInvitationRepository(db_session).get_invitation_by_email(email).token


def test_accepting_creates_a_verified_signed_in_publisher(client, db_session):
    _, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    token = _invite(client, headers, db_session, "partner@vde.example",
                    role="publisher", publisher_id=str(publisher.id), locale="en")

    response = client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert response.status_code == 200
    session_token = response.json()["session_token"]
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {session_token}"}).json()
    assert (session["role"], session["publisher_id"]) == ("publisher", str(publisher.id))
    account = PostgresAccountRepository(db_session).get_account_by_email("partner@vde.example")
    assert account.email_verified_at is not None and account.locale == "en"
    assert PostgresInvitationRepository(db_session).get_invitation_by_token(token) is None
    audit = db_session.execute(
        sa.text("SELECT details::text FROM admin_audit_log WHERE action = 'invitation_accepted' "
                "AND target_account_id = :a"), {"a": account.id},
    ).scalar_one()
    assert '"credentials_reset": false' in audit and "partner@vde.example" not in audit
    again = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (again.status_code, again.json()["detail"]) == (410, "invitation_invalid")


def test_an_existing_account_gets_the_role_only_on_accept(client, db_session):
    _, headers = make_admin(db_session)
    existing = make_account(db_session, "colleague@example.de", password="correct horse")
    token = _invite(client, headers, db_session, "colleague@example.de", role="administrator")
    accounts = PostgresAccountRepository(db_session)
    assert accounts.get_account_by_id(existing.id).role is Role.USER

    client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert accounts.get_account_by_id(existing.id).role is Role.ADMINISTRATOR


def test_a_matching_address_alone_never_grants_the_role(client, db_session):
    """Someone registers the invited address first; without the link nothing changes."""
    _, headers = make_admin(db_session)
    _invite(client, headers, db_session, "target@vde.example", role="administrator")
    client.post("/v1/accounts/register", json={"email": "target@vde.example", "password": "correct horse"})
    login = client.post("/v1/accounts/login", json={"email": "target@vde.example", "password": "correct horse"})
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {login.json()['session_token']}"}).json()
    assert session["role"] == "user"


def test_expired_and_blocked(client, db_session):
    _, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, "late@example.de", role="user")
    db_session.execute(sa.text("UPDATE account_invitation SET expires_at = :t WHERE token = :k"),
                       {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "k": token})
    assert client.post("/v1/accounts/invitations/accept", json={"token": token}).status_code == 410

    make_account(db_session, "soon-blocked@example.de")
    token = _invite(client, headers, db_session, "soon-blocked@example.de", role="user")
    account = PostgresAccountRepository(db_session).get_account_by_email("soon-blocked@example.de")
    client.post(f"/v1/admin/accounts/{account.id}/block", json={"reason": "abuse"}, headers=headers)
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (403, "account_blocked")


def test_accepting_a_user_invitation_cannot_remove_the_last_administrator(client, db_session):
    admin, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, admin.email, role="user")
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (409, "last_administrator")
    assert PostgresAccountRepository(db_session).get_account_by_id(admin.id).role is Role.ADMINISTRATOR


def _seed_squatter_content(db_session, account_id):
    accounts = PostgresAccountRepository(db_session)
    accounts.update_profile_names(account_id, first_name="Eve", last_name="Squatter")
    accounts.set_avatar(account_id, avatar_image=b"png", avatar_content_type="image/png")
    accounts.update_notification_preference(account_id, preference=NotificationPreference.BOTH)
    now = datetime.now(timezone.utc)
    chats = PostgresChatRepository(db_session)
    chat = chats.create_session(session_token="squatter-chat", jurisdiction="DE", language="de",
                                created_at=now, account_id=account_id)
    chats.create_message(session_id=chat.id, role=ChatMessageRole.USER, content="Hallo?",
                         answer_type=None, created_at=now)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(account_id=account_id, work_id=work.id)
    PostgresNotificationRepository(db_session).create(
        account_id=account_id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=None,
        trigger_document_id=None, trigger_jurisdiction=None, may_process=None,
        may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.flush()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_accepting_resets_credentials_and_content_of_an_unverified_account(client, db_session):
    """
    Someone pre-registers the invited address and keeps the session. The
    rightful recipient accepts: the squatter loses session and password, the
    role goes only to the session the link created, and nothing the squatter
    left in the account remains (ADR-030).
    """
    _, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, "victim@vde.example", role="administrator",
                    locale="en")
    client.post("/v1/accounts/register", json={"email": "victim@vde.example", "password": "attacker pw"})
    squatter = client.post("/v1/accounts/login",
                           json={"email": "victim@vde.example", "password": "attacker pw"})
    squatter_token = squatter.json()["session_token"]
    assert client.get("/v1/accounts/session", headers=_bearer(squatter_token)).status_code == 200
    squatted = PostgresAccountRepository(db_session).get_account_by_email("victim@vde.example")
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=squatted.id, google_subject_id="squatter-google-subject",
    )
    now = datetime.now(timezone.utc)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=squatted.id, purpose=AccountTokenPurpose.PASSWORD_RESET, token="squatter-reset",
        created_at=now, expires_at=now + timedelta(hours=1),
    )
    _seed_squatter_content(db_session, squatted.id)

    accepted = client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert accepted.status_code == 200
    assert client.get("/v1/accounts/session", headers=_bearer(squatter_token)).status_code == 401
    relogin = client.post("/v1/accounts/login",
                          json={"email": "victim@vde.example", "password": "attacker pw"})
    assert relogin.status_code == 401
    fresh = client.get("/v1/accounts/session", headers=_bearer(accepted.json()["session_token"]))
    assert (fresh.status_code, fresh.json()["role"]) == (200, "administrator")

    account = PostgresAccountRepository(db_session).get_account_by_email("victim@vde.example")
    assert account.password_hash is None
    assert (account.first_name, account.last_name, account.avatar_image) == (None, None, None)
    assert account.avatar_content_type is None
    assert account.notification_preference is NotificationPreference.NONE
    assert account.locale == "en"
    for table in ("account_token", "account_google_identity", "chat_session", "watchlist",
                  "notification"):
        count = db_session.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE account_id = :a"), {"a": account.id}
        ).scalar_one()
        assert count == 0, table
    audit = db_session.execute(
        sa.text("SELECT details::text FROM admin_audit_log WHERE action = 'invitation_accepted' "
                "AND target_account_id = :a"), {"a": account.id},
    ).scalars().all()
    assert len(audit) == 1
    assert '"credentials_reset": true' in audit[0]
    assert "victim@vde.example" not in audit[0]


def test_accepting_leaves_a_verified_account_untouched(client, db_session):
    _, headers = make_admin(db_session)
    existing = make_account(db_session, "verified@example.de", password="correct horse")
    PostgresAccountRepository(db_session).mark_email_verified(existing.id, datetime.now(timezone.utc))
    PostgresAccountRepository(db_session).update_profile_names(
        existing.id, first_name="Vera", last_name="Owner",
    )
    db_session.flush()
    login = client.post("/v1/accounts/login",
                        json={"email": "verified@example.de", "password": "correct horse"})
    old_token = login.json()["session_token"]
    token = _invite(client, headers, db_session, "verified@example.de", role="administrator")

    assert client.post("/v1/accounts/invitations/accept", json={"token": token}).status_code == 200

    old = client.get("/v1/accounts/session", headers=_bearer(old_token))
    assert (old.status_code, old.json()["role"]) == (200, "administrator")
    assert client.post("/v1/accounts/login",
                       json={"email": "verified@example.de", "password": "correct horse"}).status_code == 200
    audit = db_session.execute(
        sa.text("SELECT details::text FROM admin_audit_log WHERE action = 'invitation_accepted' "
                "AND target_account_id = :a"), {"a": existing.id},
    ).scalar_one()
    assert '"credentials_reset": false' in audit and "verified@example.de" not in audit
    kept = PostgresAccountRepository(db_session).get_account_by_id(existing.id)
    assert (kept.first_name, kept.last_name, kept.locale) == ("Vera", "Owner", "de")


def test_a_google_signed_in_colleague_is_not_reset_on_accept(client, db_session):
    from normly_accounts.google_oauth import GoogleProfile
    from tests.test_google_login import _callback

    _, headers = make_admin(db_session)
    signed_in = _callback(client, db_session, GoogleProfile(
        subject_id="colleague-sub", email="colleague@vde.example", email_verified=True,
    ), "colleague")
    google_session = signed_in.json()["session_token"]
    account_id = signed_in.json()["account"]["id"]
    PostgresAccountRepository(db_session).update_profile_names(
        account_id, first_name="Carla", last_name="Colleague",
    )
    db_session.flush()
    token = _invite(client, headers, db_session, "colleague@vde.example", role="administrator")

    assert client.post("/v1/accounts/invitations/accept", json={"token": token}).status_code == 200

    old = client.get("/v1/accounts/session", headers=_bearer(google_session))
    assert (old.status_code, old.json()["role"], old.json()["first_name"]) == (
        200, "administrator", "Carla",
    )
    assert PostgresAccountGoogleIdentityRepository(db_session).has_google_identity(account_id)
