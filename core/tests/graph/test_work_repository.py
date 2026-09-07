# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import WorkCreatedVia, WorkStatus
from normly_core.graph.postgres.orm import WorkORM
from normly_core.graph.postgres.repositories import PostgresWorkRepository


def test_create_work_defaults_to_active(db_session):
    repo = PostgresWorkRepository(db_session)

    work = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)

    assert work.status == WorkStatus.ACTIVE
    assert work.merged_into_work_id is None
    assert work.created_via == WorkCreatedVia.AUTO_MATCHED


def test_get_work_returns_none_for_unknown_id(db_session):
    repo = PostgresWorkRepository(db_session)

    assert repo.get_work(uuid.uuid4()) is None


def test_get_work_returns_the_active_work(db_session):
    repo = PostgresWorkRepository(db_session)
    work = repo.create_work(created_via=WorkCreatedVia.MANUAL)

    found = repo.get_work(work.id)

    assert found == work


def test_get_work_redirects_through_a_merged_work(db_session):
    repo = PostgresWorkRepository(db_session)
    target = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)
    source = repo.create_work(created_via=WorkCreatedVia.AUTO_MATCHED)

    # Task 4 adds the real merge operation (resolve_work_merge_case). Here we
    # only need a merged Work to exist to prove get_work()'s read-side
    # redirect works -- so the merge is set up directly via the ORM.
    orm = db_session.get(WorkORM, source.id)
    orm.status = WorkStatus.MERGED
    orm.merged_into_work_id = target.id
    db_session.flush()

    found = repo.get_work(source.id)

    assert found.id == target.id
    assert found.status == WorkStatus.ACTIVE
