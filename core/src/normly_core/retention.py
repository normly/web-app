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
#: no Google link and no account session at all (any expiry). Accounts in use
#: without verification (Google, password login) are never purged.
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
