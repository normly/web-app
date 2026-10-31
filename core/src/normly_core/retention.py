# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Retention periods for user data. The one place they are defined; the
`cleanup-user-data` command and its documentation both refer to these names.
"""

from datetime import timedelta

#: Expired account sessions are kept this long after `expires_at`.
ACCOUNT_SESSION_GRACE = timedelta(days=7)

#: One-time tokens are kept this long after `expires_at` or `used_at`.
ACCOUNT_TOKEN_GRACE = timedelta(hours=24)

#: Abandoned registrations, measured from `created_at`: email never verified,
#: no Google link and no account session at all (any expiry), not blocked and
#: role `user`. Accounts in use without verification (Google link, password
#: login) are never purged.
UNVERIFIED_ACCOUNT_MAX_AGE = timedelta(days=30)

#: Read notifications, measured from `created_at`.
READ_NOTIFICATION_MAX_AGE = timedelta(days=60)

#: Unread notifications, measured from `created_at`.
UNREAD_NOTIFICATION_MAX_AGE = timedelta(days=365)

#: Deletion-log entries; must cover the longest backup retention.
DELETION_LOG_MAX_AGE = timedelta(days=90)

#: Notice between the warning e-mail and the deletion of an abandoned
#: registration.
ACCOUNT_DELETION_NOTICE_PERIOD = timedelta(days=14)

#: LLM cost-cap question counters, measured in UTC days: today and yesterday
#: are kept, older rows deleted. They embed a caller address (ADR-029).
LLM_QUESTION_COUNT_RETENTION = timedelta(days=1)

#: LLM cost-cap token usage per pool and day, and the budget alerts sent,
#: measured in UTC days; covers the running month and the previous one's end.
LLM_USAGE_RETENTION = timedelta(days=40)

#: Expired invitations, measured from `expires_at`; open ones are never touched.
INVITATION_EXPIRED_GRACE = timedelta(days=30)

#: Administrative audit entries, measured from `occurred_at` (ADR-030).
ADMIN_AUDIT_RETENTION = timedelta(days=730)
