# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.postgres.repositories import PostgresAccountRepository


def test_update_profile_names_sets_both_fields(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="a@example.de", password_hash=None)

    repo.update_profile_names(account.id, first_name="Jamie", last_name="Weber")

    updated = repo.get_account_by_id(account.id)
    assert updated.first_name == "Jamie"
    assert updated.last_name == "Weber"


def test_update_profile_names_can_clear_a_field(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="b@example.de", password_hash=None)
    repo.update_profile_names(account.id, first_name="Jamie", last_name="Weber")

    repo.update_profile_names(account.id, first_name="Jamie", last_name=None)

    updated = repo.get_account_by_id(account.id)
    assert updated.first_name == "Jamie"
    assert updated.last_name is None


def test_set_avatar_then_get_account_returns_it(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="c@example.de", password_hash=None)

    repo.set_avatar(account.id, avatar_image=b"\xff\xd8\xff", avatar_content_type="image/jpeg")

    updated = repo.get_account_by_id(account.id)
    assert updated.avatar_image == b"\xff\xd8\xff"
    assert updated.avatar_content_type == "image/jpeg"


def test_clear_avatar_resets_both_fields(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="d@example.de", password_hash=None)
    repo.set_avatar(account.id, avatar_image=b"\xff\xd8\xff", avatar_content_type="image/jpeg")

    repo.clear_avatar(account.id)

    updated = repo.get_account_by_id(account.id)
    assert updated.avatar_image is None
    assert updated.avatar_content_type is None


def test_a_freshly_created_account_has_no_name_or_avatar(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="e@example.de", password_hash=None)

    assert account.first_name is None
    assert account.last_name is None
    assert account.avatar_image is None
    assert account.avatar_content_type is None
