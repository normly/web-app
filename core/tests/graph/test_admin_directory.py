# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import BlockReason, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAdminDirectoryRepository,
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _seed(db_session):
    accounts = PostgresAccountRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(
        name="DIN Media", created_at=NOW
    )
    admin = accounts.create_account(email="ops@normly.example", password_hash="x")
    accounts.set_role(admin.id, role=Role.ADMINISTRATOR, publisher_id=None)
    partner = accounts.create_account(email="lizenzen@dinmedia.example", password_hash=None)
    accounts.set_role(partner.id, role=Role.PUBLISHER, publisher_id=publisher.id)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=partner.id, google_subject_id="g-partner"
    )
    crawler = accounts.create_account(email="crawler@mailbox.example", password_hash="x")
    accounts.block_account(crawler.id, reason=BlockReason.BULK_RETRIEVAL, blocked_at=NOW)
    accounts.update_profile_names(admin.id, first_name="Jonas", last_name="Keller")
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=admin.id, session_token="s-admin", created_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=29),
    )
    invitations = PostgresInvitationRepository(db_session)
    invitations.save_invitation(
        email="partner@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id,
        locale="de", token="inv-open", invited_by=admin.id, created_at=NOW,
        expires_at=NOW + timedelta(days=7),
    )
    invitations.save_invitation(
        email="late@example.de", role=Role.USER, publisher_id=None, locale="en",
        token="inv-expired", invited_by=admin.id, created_at=NOW - timedelta(days=9),
        expires_at=NOW - timedelta(days=2),
    )
    return admin, partner, crawler, publisher


def _list(db_session, **kwargs):
    params = dict(query=None, role=None, status=None, sort="email", descending=False,
                  page=1, page_size=50, now=NOW)
    params.update(kwargs)
    return PostgresAdminDirectoryRepository(db_session).list_users(**params)


def test_lists_accounts_and_invitations_together(db_session):
    _seed(db_session)
    page = _list(db_session)

    assert page.total == 5
    by_email = {row.email: row for row in page.rows}
    assert by_email["lizenzen@dinmedia.example"].sign_in_methods == ("google",)
    assert by_email["lizenzen@dinmedia.example"].publisher_name == "DIN Media"
    assert by_email["ops@normly.example"].sign_in_methods == ("email",)
    assert by_email["crawler@mailbox.example"].status == "blocked"
    assert by_email["crawler@mailbox.example"].block_reason is BlockReason.BULK_RETRIEVAL
    assert by_email["partner@vde.example"].status == "invited"
    assert by_email["partner@vde.example"].kind == "invitation"
    assert by_email["partner@vde.example"].created_at is None
    assert by_email["late@example.de"].status == "expired"


def test_filters_search_sort_and_paging(db_session):
    _seed(db_session)
    assert [r.email for r in _list(db_session, role=Role.PUBLISHER).rows] == [
        "lizenzen@dinmedia.example", "partner@vde.example",
    ]
    assert [r.email for r in _list(db_session, status="expired").rows] == ["late@example.de"]
    assert [r.email for r in _list(db_session, query="kell").rows] == ["ops@normly.example"]
    # LIKE wildcards in the search are literal characters
    assert _list(db_session, query="%").total == 0

    newest_login_first = _list(db_session, sort="last_login_at", descending=True)
    assert newest_login_first.rows[0].email == "ops@normly.example"  # NULLs last

    second_page = _list(db_session, page=2, page_size=2)
    assert second_page.total == 5
    assert len(second_page.rows) == 2


def test_summary(db_session):
    _seed(db_session)
    summary = PostgresAdminDirectoryRepository(db_session).summarize(
        now=NOW, active_since=NOW - timedelta(days=30)
    )

    assert summary.accounts_total == 3
    assert summary.accounts_active == 1
    assert summary.accounts_by_role == {Role.USER: 1, Role.PUBLISHER: 1, Role.ADMINISTRATOR: 1}
    assert summary.publishers_with_accounts == 1
    assert summary.open_invitations == 1
    assert summary.blocked == 1
    assert summary.most_frequent_block_reason is BlockReason.BULK_RETRIEVAL


def test_lock_active_administrator_ids_ignores_blocked_ones(db_session):
    admin, _, _, _ = _seed(db_session)
    accounts = PostgresAccountRepository(db_session)
    second = accounts.create_account(email="second-admin@example.de", password_hash=None)
    accounts.set_role(second.id, role=Role.ADMINISTRATOR, publisher_id=None)
    accounts.block_account(second.id, reason=BlockReason.OTHER, blocked_at=NOW)

    assert accounts.lock_active_administrator_ids() == [admin.id]
    accounts.unblock_account(second.id)
    assert set(accounts.lock_active_administrator_ids()) == {admin.id, second.id}


def test_delete_sessions_for_account(db_session):
    admin, _, _, _ = _seed(db_session)
    sessions = PostgresAccountSessionRepository(db_session)
    assert sessions.delete_sessions_for_account(admin.id) == 1
    assert sessions.get_session_by_token("s-admin") is None
