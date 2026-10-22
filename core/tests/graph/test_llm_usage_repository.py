# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from normly_core.graph.domain import LlmPoolTotals
from normly_core.graph.postgres.orm import (
    LlmBudgetAlertORM,
    LlmQuestionCountORM,
    LlmTokenUsageORM,
)
from normly_core.graph.postgres.repositories import PostgresLlmUsageRepository

_NOW = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)


def test_add_tokens_accumulates_and_returns_day_and_month_totals(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 21), input_tokens=100, output_tokens=50)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 22), input_tokens=10, output_tokens=5)

    totals = repo.add_tokens(
        pool="anonymous", day=date(2026, 10, 22), input_tokens=20, output_tokens=5,
    )

    assert totals == LlmPoolTotals(day_tokens=40, month_tokens=190)


def test_pool_totals_ignore_other_pools_and_previous_months(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.add_tokens(pool="anonymous", day=date(2026, 9, 30), input_tokens=1000, output_tokens=0)
    repo.add_tokens(pool="registered", day=date(2026, 10, 22), input_tokens=500, output_tokens=0)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 1), input_tokens=7, output_tokens=0)

    assert repo.pool_totals(pool="anonymous", day=date(2026, 10, 22)) == LlmPoolTotals(
        day_tokens=0, month_tokens=7,
    )


def test_record_question_counts_per_key_and_day_and_reports_the_limit(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    day = date(2026, 10, 22)

    assert repo.record_question(key="account:a", day=day, limit=2) == (1, True)
    assert repo.record_question(key="account:a", day=day, limit=2) == (2, True)
    assert repo.record_question(key="account:a", day=day, limit=2) == (3, False)
    assert repo.record_question(key="account:b", day=day, limit=2) == (1, True)
    assert repo.record_question(key="account:a", day=date(2026, 10, 23), limit=2) == (1, True)
    assert repo.question_count(key="account:a", day=day) == 3
    assert repo.question_count(key="account:unknown", day=day) == 0


def test_claim_alert_succeeds_only_once_per_pool_period_and_threshold(db_session):
    repo = PostgresLlmUsageRepository(db_session)

    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW) is True
    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW) is False
    assert repo.claim_alert(pool="anonymous", period="2026-10", threshold=80, now=_NOW) is True
    assert repo.claim_alert(pool="registered", period="2026-10", threshold=50, now=_NOW) is True


def test_delete_expired_removes_only_old_rows(db_session):
    repo = PostgresLlmUsageRepository(db_session)
    repo.record_question(key="k", day=date(2026, 10, 20), limit=5)
    repo.record_question(key="k", day=date(2026, 10, 21), limit=5)
    repo.add_tokens(pool="anonymous", day=date(2026, 9, 1), input_tokens=1, output_tokens=0)
    repo.add_tokens(pool="anonymous", day=date(2026, 10, 1), input_tokens=1, output_tokens=0)
    repo.claim_alert(
        pool="anonymous", period="2026-08", threshold=50,
        now=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    repo.claim_alert(pool="anonymous", period="2026-10", threshold=50, now=_NOW)

    repo.delete_expired(question_before=date(2026, 10, 21), usage_before=date(2026, 9, 12))

    assert db_session.execute(sa.select(LlmQuestionCountORM.day)).scalars().all() == [
        date(2026, 10, 21),
    ]
    assert db_session.execute(sa.select(LlmTokenUsageORM.day)).scalars().all() == [
        date(2026, 10, 1),
    ]
    assert db_session.execute(sa.select(LlmBudgetAlertORM.period)).scalars().all() == ["2026-10"]


def test_concurrent_questions_and_alert_claims_are_counted_exactly(migrated_engine):
    # Real commits from parallel sessions: the atomicity under concurrency is
    # the point, which the rolled-back db_session fixture cannot show.
    key = f"concurrency:{uuid.uuid4()}"
    period = f"test-{uuid.uuid4().hex[:4]}"
    day = date(2026, 10, 22)

    def record(_):
        with Session(migrated_engine) as session:
            PostgresLlmUsageRepository(session).record_question(key=key, day=day, limit=100)
            session.commit()

    def claim(_):
        with Session(migrated_engine) as session:
            claimed = PostgresLlmUsageRepository(session).claim_alert(
                pool="anonymous", period=period, threshold=100, now=_NOW,
            )
            session.commit()
            return claimed

    try:
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(record, range(20)))
            claims = list(pool.map(claim, range(10)))

        with Session(migrated_engine) as session:
            assert PostgresLlmUsageRepository(session).question_count(key=key, day=day) == 20
        assert claims.count(True) == 1
    finally:
        with Session(migrated_engine) as session:
            session.execute(sa.delete(LlmQuestionCountORM).where(LlmQuestionCountORM.key == key))
            session.execute(sa.delete(LlmBudgetAlertORM).where(LlmBudgetAlertORM.period == period))
            session.commit()
