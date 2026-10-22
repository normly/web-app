# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_chat.budget_settings import BudgetSettings, PoolBudget


def test_defaults_apply_when_nothing_is_set():
    settings = BudgetSettings.from_env({})

    assert settings.max_output_tokens == 1024
    assert settings.max_message_chars == 2000
    assert settings.anonymous_daily_quota == 10
    assert settings.registered_daily_quota == 30
    assert settings.pools["anonymous"] == PoolBudget(daily_tokens=500_000, monthly_tokens=10_000_000)
    assert settings.pools["registered"] == PoolBudget(daily_tokens=2_000_000, monthly_tokens=40_000_000)
    assert settings.alert_recipients == ()


def test_values_are_read_from_the_environment():
    settings = BudgetSettings.from_env({
        "NORMLY_LLM_MAX_OUTPUT_TOKENS": "800",
        "NORMLY_CHAT_MAX_MESSAGE_CHARS": "1500",
        "NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": "5",
        "NORMLY_CHAT_QUOTA_REGISTERED_DAILY": "50",
        "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": "1000",
        "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": "20000",
        "NORMLY_LLM_BUDGET_REGISTERED_DAILY_TOKENS": "3000",
        "NORMLY_LLM_BUDGET_REGISTERED_MONTHLY_TOKENS": "60000",
        "NORMLY_LLM_BUDGET_ALERT_RECIPIENTS": " lead-a@example.org, lead-b@example.org ,",
    })

    assert settings.max_output_tokens == 800
    assert settings.max_message_chars == 1500
    assert settings.anonymous_daily_quota == 5
    assert settings.registered_daily_quota == 50
    assert settings.pools["anonymous"] == PoolBudget(daily_tokens=1000, monthly_tokens=20000)
    assert settings.pools["registered"] == PoolBudget(daily_tokens=3000, monthly_tokens=60000)
    assert settings.alert_recipients == ("lead-a@example.org", "lead-b@example.org")


@pytest.mark.parametrize("value", ["0", "-3", "abc", ""])
def test_a_non_positive_or_non_numeric_value_fails_naming_the_variable(value):
    with pytest.raises(ValueError, match="NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY"):
        BudgetSettings.from_env({"NORMLY_CHAT_QUOTA_ANONYMOUS_DAILY": value})


def test_a_daily_budget_above_the_monthly_budget_fails():
    with pytest.raises(ValueError, match="NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS"):
        BudgetSettings.from_env({
            "NORMLY_LLM_BUDGET_ANONYMOUS_DAILY_TOKENS": "200",
            "NORMLY_LLM_BUDGET_ANONYMOUS_MONTHLY_TOKENS": "100",
        })
