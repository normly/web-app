# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest

from normly_core.graph.domain import LlmPoolTotals

from normly_chat.budget_guard import (
    POOL_ANONYMOUS, POOL_REGISTERED, BudgetExhausted, BudgetGuard, QuotaStatus,
    next_day_start, next_month_start,
)
from normly_chat.budget_settings import BudgetSettings, PoolBudget
from normly_chat.llm_result import LlmResult

_NOW = datetime(2026, 10, 22, 9, 30, tzinfo=timezone.utc)


class _InMemoryUsageRepository:
    def __init__(self):
        self.tokens: dict[tuple[str, date], int] = {}
        self.questions: dict[tuple[str, date], int] = {}
        self.alerts: set[tuple[str, str, int]] = set()
        self.expired_calls = []

    def add_tokens(self, *, pool, day, input_tokens, output_tokens):
        self.tokens[(pool, day)] = self.tokens.get((pool, day), 0) + input_tokens + output_tokens
        return self.pool_totals(pool=pool, day=day)

    def pool_totals(self, *, pool, day):
        month = [
            total for (p, d), total in self.tokens.items()
            if p == pool and d.replace(day=1) == day.replace(day=1) and d <= day
        ]
        return LlmPoolTotals(day_tokens=self.tokens.get((pool, day), 0), month_tokens=sum(month))

    def record_question(self, *, key, day, limit):
        count = self.questions.get((key, day), 0) + 1
        self.questions[(key, day)] = count
        return count, count <= limit

    def question_count(self, *, key, day):
        return self.questions.get((key, day), 0)

    def claim_alert(self, *, pool, period, threshold, now):
        if (pool, period, threshold) in self.alerts:
            return False
        self.alerts.add((pool, period, threshold))
        return True

    def delete_expired(self, *, question_before, usage_before):
        self.expired_calls.append((question_before, usage_before))


class _RecordingAlerter:
    def __init__(self):
        self.alerts = []

    def send(self, alert):
        self.alerts.append(alert)


def _settings(**pools):
    return BudgetSettings(
        max_output_tokens=100, max_message_chars=2000,
        anonymous_daily_quota=2, registered_daily_quota=3,
        pools={
            POOL_ANONYMOUS: pools.get("anonymous", PoolBudget(daily_tokens=1000, monthly_tokens=10_000)),
            POOL_REGISTERED: pools.get("registered", PoolBudget(daily_tokens=1000, monthly_tokens=10_000)),
        },
        alert_recipients=(),
    )


def _guard(repo, settings=None, alerter=None, now=_NOW):
    @contextmanager
    def repositories():
        yield repo

    return BudgetGuard(
        repositories, settings or _settings(), alerter or _RecordingAlerter(), now=lambda: now,
    )


def test_reset_times_are_the_next_utc_day_and_month():
    assert next_day_start(_NOW) == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert next_month_start(_NOW) == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert next_month_start(datetime(2026, 12, 5, tzinfo=timezone.utc)) == datetime(
        2027, 1, 1, tzinfo=timezone.utc,
    )


def test_admit_counts_questions_up_to_the_pool_quota():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)

    guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")
    guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")
    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_ANONYMOUS, user_key="anon:1.2.3.4")

    assert raised.value.reason == "quota_exhausted"
    assert raised.value.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert raised.value.anonymous is True
    # The registered quota (3) is separate from the anonymous one (2).
    for _ in range(3):
        guard.admit(pool=POOL_REGISTERED, user_key="account:a")


def test_admit_refuses_when_the_daily_pool_budget_is_spent_without_counting_the_question():
    repo = _InMemoryUsageRepository()
    repo.tokens[(POOL_ANONYMOUS, _NOW.date())] = 1000
    guard = _guard(repo)

    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    assert raised.value.reason == "pool_daily_exhausted"
    assert raised.value.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert repo.questions == {}
    # The other pool is untouched by the anonymous pool's exhaustion.
    guard.admit(pool=POOL_REGISTERED, user_key="account:a")


def test_admit_refuses_when_the_monthly_pool_budget_is_spent():
    repo = _InMemoryUsageRepository()
    repo.tokens[(POOL_REGISTERED, date(2026, 10, 1))] = 10_000
    guard = _guard(repo)

    with pytest.raises(BudgetExhausted) as raised:
        guard.admit(pool=POOL_REGISTERED, user_key="account:a")

    assert raised.value.reason == "pool_monthly_exhausted"
    assert raised.value.resets_at == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert raised.value.anonymous is False


def test_admit_runs_retention_with_two_days_of_questions_and_forty_days_of_usage():
    repo = _InMemoryUsageRepository()
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    assert repo.expired_calls == [(date(2026, 10, 21), date(2026, 9, 12))]


def test_a_new_day_starts_a_fresh_quota():
    repo = _InMemoryUsageRepository()
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")
    _guard(repo).admit(pool=POOL_ANONYMOUS, user_key="anon:x")

    _guard(repo, now=datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)).admit(
        pool=POOL_ANONYMOUS, user_key="anon:x",
    )


def test_book_adds_input_and_output_tokens_to_the_pool():
    repo = _InMemoryUsageRepository()
    _guard(repo).book(
        pool=POOL_ANONYMOUS,
        result=LlmResult(text="a", input_tokens=30, output_tokens=12, truncated=False),
    )

    assert repo.tokens == {(POOL_ANONYMOUS, _NOW.date()): 42}


def test_book_sends_each_crossed_threshold_once():
    repo = _InMemoryUsageRepository()
    alerter = _RecordingAlerter()
    guard = _guard(repo, alerter=alerter)
    repo.tokens[(POOL_ANONYMOUS, date(2026, 10, 1))] = 4_900

    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 100, 0, False))   # 5000 = 50 %
    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 10, 0, False))    # still 50 %
    guard.book(pool=POOL_ANONYMOUS, result=LlmResult("a", 890, 0, False))   # day 1000 = 100 %, month 5900

    assert [(a.period, a.threshold) for a in alerter.alerts] == [
        ("2026-10", 50), ("2026-10-22", 100),
    ]
    daily = alerter.alerts[1]
    assert daily.total_tokens == 1000
    assert daily.budget_tokens == 1000
    assert daily.resets_at == datetime(2026, 10, 23, tzinfo=timezone.utc)


def test_book_sends_all_monthly_thresholds_crossed_in_one_step():
    repo = _InMemoryUsageRepository()
    alerter = _RecordingAlerter()
    settings = _settings(anonymous=PoolBudget(daily_tokens=10_000, monthly_tokens=10_000))
    _guard(repo, settings=settings, alerter=alerter).book(
        pool=POOL_ANONYMOUS, result=LlmResult("a", 10_000, 0, False),
    )

    assert sorted((a.period, a.threshold) for a in alerter.alerts) == [
        ("2026-10", 50), ("2026-10", 80), ("2026-10", 100), ("2026-10-22", 100),
    ]


def test_pool_available_reflects_both_budgets():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)
    assert guard.pool_available(POOL_REGISTERED) is True

    repo.tokens[(POOL_REGISTERED, _NOW.date())] = 1000
    assert guard.pool_available(POOL_REGISTERED) is False


def test_status_reports_used_limit_and_resets():
    repo = _InMemoryUsageRepository()
    guard = _guard(repo)
    guard.admit(pool=POOL_REGISTERED, user_key="account:a")

    assert guard.status(pool=POOL_REGISTERED, user_key="account:a") == QuotaStatus(
        used=1, limit=3, resets_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        pool_exhausted=False, pool_resets_at=None,
    )


def test_status_caps_used_at_the_limit_and_reports_an_exhausted_pool():
    repo = _InMemoryUsageRepository()
    repo.questions[("account:a", _NOW.date())] = 7
    repo.tokens[(POOL_REGISTERED, date(2026, 10, 1))] = 10_000

    status = _guard(repo).status(pool=POOL_REGISTERED, user_key="account:a")

    assert status.used == 3
    assert status.pool_exhausted is True
    assert status.pool_resets_at == datetime(2026, 11, 1, tzinfo=timezone.utc)
