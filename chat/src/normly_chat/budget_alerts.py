# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Budget alert mail to the Lead Maintainers (issue #40)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from normly_core.notifications.email import EmailSender

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetAlert:
    pool: str
    # "YYYY-MM" for a monthly threshold, "YYYY-MM-DD" for daily exhaustion.
    period: str
    threshold: int
    total_tokens: int
    budget_tokens: int
    resets_at: datetime


class BudgetAlerter:
    """
    Recipients come from NORMLY_LLM_BUDGET_ALERT_RECIPIENTS on the VM, never
    from the repository. A failing relay must never fail the user's request,
    so every error is logged and swallowed -- the same fail-soft rule as
    notify-watchers.
    """

    def __init__(self, sender: EmailSender, recipients: tuple[str, ...]):
        self._sender = sender
        self._recipients = recipients

    def send(self, alert: BudgetAlert) -> None:
        subject = f"[normly] LLM budget: {alert.pool} pool at {alert.threshold} % ({alert.period})"
        body = (
            f"The {alert.pool} cost pool reached {alert.threshold} % of its budget "
            f"for {alert.period}.\n\n"
            f"Used: {alert.total_tokens} tokens\n"
            f"Budget: {alert.budget_tokens} tokens\n"
            f"Resets at: {alert.resets_at.isoformat()}\n\n"
            "At 100 % the chat answers AI questions of this pool with a limit notice "
            "until the reset. Budgets are set with the NORMLY_LLM_BUDGET_* variables."
        )
        if not self._recipients:
            logger.warning("budget alert without recipients: %s", subject)
            return
        for recipient in self._recipients:
            try:
                self._sender.send(to=recipient, subject=subject, body=body)
            except Exception:
                logger.exception("budget alert to a recipient failed: %s", subject)
