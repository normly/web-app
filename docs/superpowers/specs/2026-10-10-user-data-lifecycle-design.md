# Design: Lifecycle of user data (Part B)

As of: 2026-10-10 · Status: implemented. Follows
`docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md` (Part A:
user references on knowledge base import). Requires PR #19 (tombstone backup
in the rollback).

## Goal and occasion

Personal data should be stored only if an account needs it,
and only for as long as the purpose exists (data minimization, storage limitation);
data subjects should be able to view and delete their data; a deletion should
also survive a restore from backups. The inventory
(2026-10-10) showed gaps:

- Anonymous chats are stored (`chat_session`/`chat_message`, cookie
  `normly_session` with a 90-day lifetime) and never deleted, although the server
  does not need them to answer (every question is answered on its own).
- `account_session` and `account_token` are never deleted (the expiry time is
  only checked); abandoned registrations stay forever.
- Unread notifications are never deleted.
- There is no way to delete individual chat histories.
- The rollback restores user data from the backup time: accounts and histories
  deleted in the meantime reappeared.
- The existing export (`GET /v1/accounts/export`) is incomplete: the
  watchlist names only `work_id`, citations are missing, and the chat session token
  (a secret) is in the export.

This design is not legal advice. The periods are decisions of the
project and should be reviewed by a data-protection professional.

## Decisions (chosen by the owner)

| Data | Rule |
|---|---|
| Anonymous chats | are **not stored** server-side |
| Chats with an account | until deleted by the person (per history or all) or by account deletion; no automatic period |
| `account_session` | deleted 7 days after expiry |
| `account_token` | deleted 24 hours after expiry or use |
| abandoned registrations (`email_verified_at` empty, no Google link, no account session, not even an expired one, no sign-in within the last 30 days via `account.last_login_at`) | warned by e-mail 30 days after creation, deleted 14 days after that together with tokens and chats (advance warning, see below); accounts in use (Google, password sign-in) never, even without verification |
| `notification` read / unread | 60 days / 12 months after creation |
| `notified_edge`, `notified_retirement`, `rights_notification_baseline` | until account deletion (prevent duplicate notifications) |
| `oauth_state`, `rate_limit_bucket` | unchanged (1 hour / 10 minutes) |
| Avatar | deleted with the account or on removal |
| Access request | existing JSON export, completed (see below) |
| Backups | after-effect limited (Flex 30 days, own backups roughly two months); a deletion log re-applies deletions after a restore |

## Implementation

**1. Anonymous chat without storage.** `POST /v1/chat` without a valid account token
writes nothing to the database, answers without `session_token` (the field becomes
optional), the frontend no longer sets a chat cookie and removes an existing one;
the conversation lives only in the browser tab. With a valid account, the behavior stays
as before. The linking "attach the anonymous session to the account on sign-in"
(`resolve_session`) is dropped; a chat token without a valid account is ignored
(today it would attach to an account session, even with the person signed out).
Existing anonymous histories are deleted by the cleanup command: every `chat_session` without
`account_id`.

**2. Cleanup command `cleanup-user-data`.** New pipeline command
(`python -m normly_core.pipeline cleanup-user-data`) that enforces the periods of the table
via repository methods (including the previous 60 days for read
notifications), is idempotent and prints only counters. Periods are
named constants in one place (`normly_core/retention.py`). A small script
`scripts/normly-cleanup` and a systemd timer (daily) run it on the VM,
as with the backup. `cleanup-notifications` remains as a command.

**3. Deleting histories.** `DELETE /v1/chat/sessions/{id}` (own only; someone else's or
an unknown ID returns 404) and `DELETE /v1/chat/sessions` (all of one's own); delete button
and "Delete all" in the sidebar with confirmation; BFF routes in the frontend.

**4. Completing the export.** `GET /v1/accounts/export` gets: readable
document IDs for the watchlist (publisher, number, edition, also for
retired documents, from the tombstone), citations per chat message (document
given as a readable document ID) and `answer_type`; the `session_token` of the chat sessions
is dropped (a secret, not the person's data) and is replaced by the session ID.
Password hash, tokens and bookkeeping remain excluded.

**5. Deletion log.** Table `deletion_log` (kind `account` or `chat_session`,
ID, time; **no** personal data, only IDs;
primary key kind+ID). Written in the same transaction as every
deletion (account deletion, deleting a history, cleanup of abandoned registrations);
pruned after 90 days (longer than the longest backup period). Part of the
user data backup (`USER_TABLES`). Commands in the core (`python -m
normly_core.exchange`): `export-deletions --since <ISO-timestamp>` writes the
entries as JSON to stdout; `replay-deletions` reads them from stdin and applies them
via the normal deletion functions (idempotent; in doing so writes to the
log again); `replay-deletions --check` checks without a database whether the image
knows the command.

**6. Rollback.** `normly-deploy rollback`: In the preliminary phase (before banner, confirmation,
stop), the deletions since the backup time are read **directly from the
database** (host `psql` with `-v since=…` and host `python3`; no
startable release image needed) (first export; error → abort without change; format
checked by the shared checker `normly_check_deletions`). The time is the
timestamp from the base name **minus one hour** (safety margin in the script; the
core command keeps its strict "later than" meaning): a deletion applied twice
is harmless, because the entity is already missing and UUIDs are never
reused. If the table `deletion_log` is missing (release before this feature), an empty
list is assumed. Before the DROP, the list to be repeated is written to
`$STATE/rollback-deletions.json` (0600); a renewed run after an
error after the DROP merges it with the fresh export (union by
kind and ID, earliest time; a damaged file aborts before any
change) and deletes it only after a successful start. `normly-cleanup` and
`normly-backup` set `NORMLY_IMAGE_TAG` from `state/current_tag` (without the file
they do not run). The first export feeds the banner, the
decision on `replay-deletions --check` and the early check. After the services are
stopped and before the DROP, a **second export** follows (same image, same
time, same checker); if it fails, the rollback aborts, the services
are stopped, the database is unchanged. **This second document** is applied after
`pg_restore` (and after the tombstone restore) by the **previous** image
(`replay-deletions`). The `--check` counts as "not supported" only on exit code 2 (unknown command),
any other error aborts before banner and confirmation. If
the previous image does not know the command (release before this feature), the banner reports
the count and the first 20 IDs; the complete list then lies in
`$STATE/rollback-pending-deletions.json` (0600, survives the cleanup of `$WORK`;
it applies only to the run that wrote it and is removed at the start of every
rollback; if nothing is left at the end of the second export, no file is created)
and must be deleted again by hand (the confirmation remains mandatory). The same
applies in the restore test and for an emergency restore from the Flex backup
(operations guide). `normly-cleanup` skips its run as long as
`state/deploy.lock` exists.

## Safeguards

- Tests: anonymous chat writes nothing (database unchanged, no `session_token`,
  no cookie); account chat as before; chat token without an account is ignored;
  cleanup command per period (boundaries, idempotency, old anonymous histories, verified
  accounts untouched, cascade when deleting an account); deleting a history (own,
  someone else's, all; writes the log); export (contents, exclusions, access by others,
  tombstone IDs); `deletion_log` on `delete_account`; log export/replay
  (time boundary, idempotency, format); rollback script (order: log before the
  deletion, replay after the restore; failure cases; previous image without the
  command); frontend (chat without cookie, delete buttons, export).
- Migration `0035`: `deletion_log` (user data group, covered by the fail-closed test).
- Documentation: ADR-027 (data inventory per table with purpose, personal data,
  period, deletion path; effect in backups with the actual maximum periods;
  note on the expert review), operations guide (timer, cleanup, rollback step,
  restore, emergency restore), spec status.

## Advance warning before deleting abandoned registrations (extension)

Owner decision (2026-10-10): an account whose registration was completed
is never deleted silently. Abandoned registrations (unverified, older than
30 days, without a Google link, without an account session) are first
warned by e-mail (`account.deletion_warned_at`, new column, migration 0036). 14 days after
the warning they are deleted if they then still meet all conditions;
sign-in, verification or a Google link reset the warning. Without
configured SMTP sending (`NullEmailSender`) or if sending fails,
nothing is ever deleted. The warning is bilingual (German/English) and contains
only the date and the sign-in URL.

## Non-goals

- Privacy policy and record of processing activities as legal texts.
- Deleting inactive accounts after a period (with advance warning by e-mail).
- Asynchronous export via e-mail link, administration interface for operators.
- Cryptographic erasure per account in backups.

## Open items

- Expert review of the periods (data protection).
- Session metadata (`account_session`): contains no IP/user agent today; if that
  changes, the data inventory and the period must be reassessed.
- Retention of tombstones (from Part A) remains open and belongs here as soon as
  it is decided whether IDs of retired documents are limited in time.
