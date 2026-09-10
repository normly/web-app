# Notification Cleanup — Design

## Problem

`notification` rows are created by `PostgresNotificationRepository.create()`
(`core/src/normly_core/graph/postgres/repositories.py:934`) whenever a
watched work changes, and never deleted. There is no retention policy and no
cleanup mechanism, so the table grows without bound as long as an account
keeps watching works.

## Goals

- Bound the table's growth with a simple, opportunistic cleanup mechanism,
  matching this codebase's existing idiom for this kind of problem
  (`PostgresRateLimitRepository.delete_buckets_before`,
  `OAuthStateRepository`'s state cleanup in `google.py`'s `create_state`
  path).
- Never delete a notification the account hasn't seen yet, regardless of its
  age.
- Keep the GDPR export (`ExportAccountFields`, fixed in the 2026-09-09
  maintenance batch to include notifications) meaningful: a user's export
  should reflect what they'd actually see in their own inbox, not artifacts
  that would otherwise have already been cleaned up.

## Design

### Policy

- Only **read** notifications (`read_at IS NOT NULL`) are eligible for
  deletion. Unread notifications are exempt regardless of age — a user who
  hasn't logged in for months must not lose notifications they haven't seen
  yet.
- Retention period: **60 days** after `created_at`, for read notifications.
  Chosen as a fixed code constant (not a per-account setting, not an env
  var) — there is no product requirement driving a different value per
  account or deployment, and hardcoding keeps the mechanism trivial to
  reason about. Documented in the constant's own definition as an adjustable
  starting point, not a carefully-derived number.

This means: a notification is deleted once it has been marked read **and**
is older than 60 days since creation — not 60 days since it was read. A
notification read on day 1 and a notification read on day 59 are both
eligible starting on day 60 of their own creation. This keeps the rule to a
single predicate (`read_at IS NOT NULL AND created_at < cutoff`) rather than
two different clocks, and matches the export goal above: nothing is deleted
before a user who reads notifications promptly would have had 60 days to
see it in their own history.

### Repository

New method on `PostgresNotificationRepository`
(`core/src/normly_core/graph/postgres/repositories.py`), placed after the
existing `mark_read`:

```python
def delete_read_before(self, cutoff: datetime) -> int:
    # Only read notifications are ever eligible -- an account that hasn't
    # logged in for months must not lose notifications it hasn't seen yet,
    # regardless of age. Mirrors PostgresRateLimitRepository's
    # delete_buckets_before opportunistic-cleanup idiom.
    result = self._session.execute(
        sa.delete(NotificationORM).where(
            NotificationORM.read_at.is_not(None),
            NotificationORM.created_at < cutoff,
        )
    )
    return result.rowcount
```

Returns the deleted row count (matching `run_adapter`/`backfill_document_embeddings`'s
existing convention of CLI commands printing a summary count), unlike
`delete_buckets_before` which returns nothing — the CLI command below needs
something to report.

### CLI

New subcommand `cleanup-notifications` in
`core/src/normly_core/pipeline/cli.py`, following the exact shape of the
existing `backfill-document-embeddings` subcommand (no arguments, one
`session.commit()` after the repository call, one summary line):

```python
subparsers.add_parser("cleanup-notifications")
```

```python
elif args.command == "cleanup-notifications":
    cutoff = datetime.now(timezone.utc) - timedelta(days=_NOTIFICATION_RETENTION_DAYS)
    deleted = PostgresNotificationRepository(session).delete_read_before(cutoff)
    session.commit()
    print(f"notifications_deleted={deleted}")
```

`_NOTIFICATION_RETENTION_DAYS = 60` defined as a module-level constant in
`cli.py`, next to the other pipeline-level constants, with a comment stating
it's a starting point pending real usage data.

This is a **new CLI subcommand**, not opportunistic cleanup folded into an
existing command's own run (the alternative considered and rejected): unlike
rate-limit buckets (touched on every request, so piggy-backing cleanup onto
`record_and_check` is nearly free) or OAuth state (touched on every login
attempt), there's no existing per-request code path that naturally owns
notification cleanup. A dedicated subcommand matches `notify-watchers`'s own
precedent — externally invoked (cron or manual), no in-process scheduler
exists anywhere in this codebase, and this project's `CLAUDE.md` doesn't
mandate one.

## Out of scope

- No scheduler/cron setup itself — this design adds the command; wiring it
  into an actual periodic trigger (STACKIT cron job, systemd timer, etc.) is
  an operational concern outside this codebase's scope, same as
  `notify-watchers` today.
- No per-account or per-notification-type retention override.
- No soft-delete / archival — deleted rows are gone, matching the "keep the
  export honest" goal (an archived-but-hidden row would make the export
  logic have to know about a second visibility state).

## Testing

- Repository: `delete_read_before` — a read notification older than the
  cutoff is deleted; a read notification newer than the cutoff is kept; an
  unread notification older than the cutoff is kept; returns the correct
  count.
- CLI: an integration-style test invoking `main(["cleanup-notifications"])`
  against a seeded database (following the existing `backfill-document-embeddings`
  CLI test's pattern, if one exists — otherwise following `notify-watchers`'s
  own CLI test), asserting the printed summary line and post-call row count.

## Addendum: the `notified_edge` bookkeeping table

The implementation's own final whole-branch review found that this design,
as originally written above, was unsafe: `notify-watchers`
(`core/src/normly_core/notifications/detection.py`) used the `notification`
table itself as its only memory of "has this account already been notified
about this specific edge?" for the `NEW_EDITION`/`NATIONAL_ADOPTION` trigger
types. Once `delete_read_before` could delete a read notification, the next
`notify-watchers` run lost that memory and re-created the notification —
re-sending the email under an `EMAIL`/`BOTH` preference — for a change that
had already been handled, every retention period, for as long as the watch
existed.

The `RIGHTS_CHANGE` trigger type was never at risk: it already has its own
dedicated bookkeeping table, `rights_notification_baseline`, kept
deliberately separate from `notification` for exactly this reason. The fix
applies the same separation to the two edge-triggered types: a new,
permanent table `notified_edge` (`core/src/normly_core/graph/postgres/orm.py`,
migration `0030_create_notified_edge.py`) records `(account_id, work_id,
trigger_type, trigger_edge_id)` the moment a notification is created, and
`notify-watchers` checks that table — not `notification` — before deciding
whether an edge is new. `notified_edge` rows are never touched by
`delete_read_before` or `cleanup-notifications`; they are deleted only when
the owning account itself is deleted (`PostgresAccountRepository.delete_account`),
the same lifecycle `rights_notification_baseline` already follows.

With this in place, `delete_read_before`'s eligibility rule above is
unchanged and now safe for every trigger type: deleting a read, aged-out
notification can no longer cause a duplicate.
