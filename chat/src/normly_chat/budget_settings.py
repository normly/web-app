# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Cost-cap configuration (issue #40). Read once at startup; an invalid value
fails startup instead of silently running without a cap.

The defaults are starting points, not measured values -- see the design spec
(docs/superpowers/specs/2026-10-22-llm-cost-caps-design.md) for how they are
derived from a measurement of the real model.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_DEFAULTS = {
    "NORMLY_LLM_MAX_OUTPUT_TOKENS": 1024,
    "NORMLY_CHAT_MAX_MESSAGE_CHARS": 2000,
    "NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": 10,
    "NORMLY_CHAT_QUOTA_REGISTERED_DAILY": 30,
    "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": 500_000,
    "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": 10_000_000,
    "NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS": 2_000_000,
    "NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS": 40_000_000,
}
_RECIPIENTS_VAR = "NORMLY_LLM_BUDGET_ALERT_RECIPIENTS"


@dataclass(frozen=True)
class PoolBudget:
    daily_tokens: int
    monthly_tokens: int


@dataclass(frozen=True)
class BudgetSettings:
    max_output_tokens: int
    max_message_chars: int
    anonymous_daily_quota: int
    registered_daily_quota: int
    pools: Mapping[str, PoolBudget]
    alert_recipients: tuple[str, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> BudgetSettings:
        def positive(name: str) -> int:
            raw = environ.get(name)
            if raw is None:
                return _DEFAULTS[name]
            try:
                value = int(raw)
            except ValueError:
                raise ValueError(f"{name} must be a positive integer, got {raw!r}") from None
            if value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {raw!r}")
            return value

        def pool(prefix: str) -> PoolBudget:
            daily_var = f"NORMLY_LLM_BUDGET_{prefix}_DAILY_TOKENS"
            budget = PoolBudget(
                daily_tokens=positive(daily_var),
                monthly_tokens=positive(f"NORMLY_LLM_BUDGET_{prefix}_MONTHLY_TOKENS"),
            )
            if budget.daily_tokens > budget.monthly_tokens:
                raise ValueError(f"{daily_var} must not exceed the monthly budget")
            return budget

        recipients = tuple(
            address.strip()
            for address in environ.get(_RECIPIENTS_VAR, "").split(",")
            if address.strip()
        )
        return cls(
            max_output_tokens=positive("NORMLY_LLM_MAX_OUTPUT_TOKENS"),
            max_message_chars=positive("NORMLY_CHAT_MAX_MESSAGE_CHARS"),
            anonymous_daily_quota=positive("NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY"),
            registered_daily_quota=positive("NORMLY_CHAT_QUOTA_REGISTERED_DAILY"),
            pools={"anonymous": pool("ANONYMOUS"), "registered": pool("REGISTERED")},
            alert_recipients=recipients,
        )
