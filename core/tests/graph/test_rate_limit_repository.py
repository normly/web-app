# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import sqlalchemy as sa

from normly_core.graph.postgres.orm import RateLimitBucketORM
from normly_core.graph.postgres.repositories import PostgresRateLimitRepository


def test_record_and_check_allows_requests_within_the_limit(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        assert repo.record_and_check(key="1.2.3.4", window_start=window, limit=3) is True


def test_record_and_check_rejects_once_the_limit_is_exceeded(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="1.2.3.4", window_start=window, limit=3)

    assert repo.record_and_check(key="1.2.3.4", window_start=window, limit=3) is False


def test_record_and_check_counts_different_keys_independently(db_session):
    repo = PostgresRateLimitRepository(db_session)
    window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="anon-a:1.2.3.4", window_start=window, limit=3)

    # A different key (e.g. a different anon_id from the same address) starts
    # its own count, unaffected by the first key's usage.
    assert repo.record_and_check(key="anon-b:1.2.3.4", window_start=window, limit=3) is True


def test_record_and_check_treats_different_windows_independently(db_session):
    repo = PostgresRateLimitRepository(db_session)
    first_window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    second_window = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)

    for _ in range(3):
        repo.record_and_check(key="1.2.3.4", window_start=first_window, limit=3)

    assert repo.record_and_check(key="1.2.3.4", window_start=second_window, limit=3) is True


def test_delete_buckets_before_removes_only_expired_windows(db_session):
    repo = PostgresRateLimitRepository(db_session)
    old_window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    recent_window = datetime(2026, 1, 1, 12, 20, tzinfo=timezone.utc)
    repo.record_and_check(key="1.2.3.4", window_start=old_window, limit=3)
    repo.record_and_check(key="1.2.3.4", window_start=recent_window, limit=3)

    repo.delete_buckets_before(datetime(2026, 1, 1, 12, 10, tzinfo=timezone.utc))

    remaining = db_session.execute(
        sa.select(RateLimitBucketORM.window_start).where(RateLimitBucketORM.key == "1.2.3.4")
    ).scalars().all()
    assert remaining == [recent_window]
