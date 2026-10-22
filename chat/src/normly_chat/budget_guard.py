# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Admission and booking for the LLM cost caps (issue #40, ADR-029).

STACKIT bounds only the speed of spending, so normly bounds the total:
two cost pools (anonymous, registered) with a daily and a monthly token
budget, and a daily quota of AI answers per caller. Only synthesis
questions reach the guard; graph answers never cost anything (ADR-008).

Every check and every booking runs in its own short transaction that
commits immediately: a count must survive the request even when the
request fails afterwards, the same reasoning as api/'s rate limiter.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from normly_core import retention
from normly_core.graph.domain import LlmPoolTotals, LlmUsageRepository

from normly_chat.budget_alerts import BudgetAlert
from normly_chat.budget_settings import BudgetSettings
from normly_chat.llm_result import LlmResult

POOL_ANONYMOUS = "anonymous"
POOL_REGISTERED = "registered"

_MONTHLY_THRESHOLDS = (50, 80, 100)
# The per-address ceiling for anonymous questions, as a multiple of the
# anonymous daily quota: several callers may share one address (NAT).
_ADDRESS_QUOTA_FACTOR = 3


def next_day_start(now: datetime) -> datetime:
    today = now.astimezone(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc)


def next_month_start(now: datetime) -> datetime:
    today = now.astimezone(timezone.utc).date()
    if today.month == 12:
        return datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(today.year, today.month + 1, 1, tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BudgetExhausted(Exception):
    def __init__(self, reason: str, resets_at: datetime, anonymous: bool):
        super().__init__(reason)
        self.reason = reason
        self.resets_at = resets_at
        self.anonymous = anonymous


@dataclass(frozen=True)
class QuotaStatus:
    used: int
    limit: int
    resets_at: datetime
    pool_exhausted: bool
    pool_resets_at: datetime | None


class BudgetGuard:
    def __init__(
        self,
        repositories: Callable[[], AbstractContextManager[LlmUsageRepository]],
        settings: BudgetSettings,
        alerter,
        now: Callable[[], datetime] = _utc_now,
    ):
        self._repositories = repositories
        self._settings = settings
        self._alerter = alerter
        self._now = now

    def _quota(self, pool: str) -> int:
        if pool == POOL_ANONYMOUS:
            return self._settings.anonymous_daily_quota
        return self._settings.registered_daily_quota

    def _pool_exhaustion(self, pool: str, totals: LlmPoolTotals, now: datetime):
        """(reason, resets_at) when the pool is spent, else None."""
        budget = self._settings.pools[pool]
        if totals.day_tokens >= budget.daily_tokens:
            return "pool_daily_exhausted", next_day_start(now)
        if totals.month_tokens >= budget.monthly_tokens:
            return "pool_monthly_exhausted", next_month_start(now)
        return None

    def admit(self, *, pool: str, user_key: str, address_key: str | None = None) -> None:
        now = self._now()
        today = now.date()
        with self._repositories() as repository:
            exhaustion = self._pool_exhaustion(
                pool, repository.pool_totals(pool=pool, day=today), now,
            )
            if exhaustion is None:
                _, allowed = repository.record_question(
                    key=user_key, day=today, limit=self._quota(pool),
                )
                # Only questions the caller's own quota admits count against
                # the address, so one caller's refusals spare its neighbours.
                if allowed and address_key is not None:
                    _, allowed = repository.record_question(
                        key=address_key, day=today,
                        limit=self._quota(pool) * _ADDRESS_QUOTA_FACTOR,
                    )
                # Opportunistic; cleanup-user-data applies the same periods.
                repository.delete_expired(
                    question_before=today - retention.LLM_QUESTION_COUNT_RETENTION,
                    usage_before=today - retention.LLM_USAGE_RETENTION,
                )
        anonymous = pool == POOL_ANONYMOUS
        if exhaustion is not None:
            reason, resets_at = exhaustion
            raise BudgetExhausted(reason, resets_at, anonymous)
        if not allowed:
            raise BudgetExhausted("quota_exhausted", next_day_start(now), anonymous)

    def pool_available(self, pool: str) -> bool:
        now = self._now()
        with self._repositories() as repository:
            totals = repository.pool_totals(pool=pool, day=now.date())
        return self._pool_exhaustion(pool, totals, now) is None

    def book(self, *, pool: str, result: LlmResult) -> None:
        now = self._now()
        budget = self._settings.pools[pool]
        candidates = []
        with self._repositories() as repository:
            totals = repository.add_tokens(
                pool=pool, day=now.date(),
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            )
            for threshold in _MONTHLY_THRESHOLDS:
                if totals.month_tokens * 100 >= budget.monthly_tokens * threshold:
                    candidates.append(BudgetAlert(
                        pool=pool, period=now.strftime("%Y-%m"), threshold=threshold,
                        total_tokens=totals.month_tokens, budget_tokens=budget.monthly_tokens,
                        resets_at=next_month_start(now),
                    ))
            if totals.day_tokens >= budget.daily_tokens:
                candidates.append(BudgetAlert(
                    pool=pool, period=now.strftime("%Y-%m-%d"), threshold=100,
                    total_tokens=totals.day_tokens, budget_tokens=budget.daily_tokens,
                    resets_at=next_day_start(now),
                ))
            claimed = [
                alert for alert in candidates
                if repository.claim_alert(
                    pool=pool, period=alert.period, threshold=alert.threshold, now=now,
                )
            ]
        # Sent after the claim is committed, so a slow relay holds no lock.
        for alert in claimed:
            self._alerter.send(alert)

    def status(self, *, pool: str, user_key: str) -> QuotaStatus:
        now = self._now()
        with self._repositories() as repository:
            used = repository.question_count(key=user_key, day=now.date())
            totals = repository.pool_totals(pool=pool, day=now.date())
        limit = self._quota(pool)
        exhaustion = self._pool_exhaustion(pool, totals, now)
        return QuotaStatus(
            # Rejected questions are counted too; the view shows at most the limit.
            used=min(used, limit), limit=limit, resets_at=next_day_start(now),
            pool_exhausted=exhaustion is not None,
            pool_resets_at=exhaustion[1] if exhaustion is not None else None,
        )
