# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import (
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _save(repo, email, *, role=Role.USER, publisher_id=None, token="t1", expires_at=None):
    return repo.save_invitation(
        email=email, role=role, publisher_id=publisher_id, locale="de", token=token,
        invited_by=None, created_at=NOW, expires_at=expires_at or NOW + timedelta(days=7),
    )


def test_saving_twice_for_the_same_address_replaces_the_invitation(db_session):
    repo = PostgresInvitationRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(name="VDE Verlag", created_at=NOW)
    first = _save(repo, "Partner@vde-verlag.de", token="old")
    second = _save(repo, "partner@vde-verlag.de", role=Role.PUBLISHER,
                   publisher_id=publisher.id, token="new")

    assert second.id == first.id
    assert (second.role, second.publisher_id, second.token) == (Role.PUBLISHER, publisher.id, "new")
    assert repo.get_invitation_by_token("old") is None
    assert repo.get_invitation_by_email("PARTNER@vde-verlag.de").id == first.id


def test_renew_issues_a_new_token_and_expiry(db_session):
    repo = PostgresInvitationRepository(db_session)
    invitation = _save(repo, "renew@example.de", token="before")
    renewed = repo.renew_invitation(invitation.id, token="after", expires_at=NOW + timedelta(days=9))

    assert (renewed.token, renewed.expires_at) == ("after", NOW + timedelta(days=9))
    assert repo.get_invitation_by_token("before") is None
    assert repo.renew_invitation(uuid.uuid4(), token="x", expires_at=NOW) is None


def test_delete_and_expiry_cleanup(db_session):
    repo = PostgresInvitationRepository(db_session)
    kept = _save(repo, "kept@example.de", token="k", expires_at=NOW - timedelta(days=29))
    _save(repo, "gone@example.de", token="g", expires_at=NOW - timedelta(days=31))
    withdrawn = _save(repo, "withdrawn@example.de", token="w")

    assert repo.delete_invitation(withdrawn.id) is True
    assert repo.delete_invitation(withdrawn.id) is False
    assert repo.delete_expired_before(NOW - timedelta(days=30)) == 1
    assert repo.get_invitation(kept.id) is not None
