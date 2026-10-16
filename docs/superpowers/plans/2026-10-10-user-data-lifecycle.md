# Lifecycle of user data (Part B) — Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anonymous chats are no longer stored, periods for sessions/tokens/accounts/notifications are enforced automatically, histories can be deleted, the export is complete, and deletions survive a restore (deletion log, replay in the rollback).

**Architecture:** New module `normly_core/retention.py` (periods as constants), new repository methods and the pipeline command `cleanup-user-data`; migration 0035 (`deletion_log`); changes in the chat service and in the frontend; export in the accounts service completed; core commands `export-deletions`/`replay-deletions` and an extension of `normly-deploy rollback`; timer script `scripts/normly-cleanup`. Spec: `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 Core/ORM, Alembic, pytest + testcontainers; Next.js/React (Vitest); Bash (fake harness in `scripts/tests`), systemd.

**Prerequisite:** PR #19 (tombstone backup, ADR-026, rollback preliminary phase) is merged into `main`; this plan is implemented on the `main` that results from it.

## Global Constraints

- Periods (binding, named constants in `normly_core/retention.py`, one place): `ACCOUNT_SESSION_GRACE = 7 days` after `expires_at`; `ACCOUNT_TOKEN_GRACE = 24 hours` after `expires_at` **or** `used_at`; `UNVERIFIED_ACCOUNT_MAX_AGE = 30 days` after `created_at` (only abandoned registrations = unverified, without a Google link and without an account session, 30 days after creation; Google and password accounts in use remain, even without verification); `READ_NOTIFICATION_MAX_AGE = 60 days` (previous value, `read_at` set); `UNREAD_NOTIFICATION_MAX_AGE = 365 days`; `DELETION_LOG_MAX_AGE = 90 days`. Anonymous chats: every `chat_session` without `account_id` is deleted (existing old data).
- Anonymous chat: without a valid account identity, **no** database access of a writing kind (no session, no message, no citation); answer without `session_token`; a chat token sent along without a valid account identity is ignored; with a valid account, behavior unchanged.
- Deletion log: table `deletion_log(kind, entity_id, deleted_at)`, `kind ∈ {"account","chat_session"}`, primary key `(kind, entity_id)`, **no** personal data, written in the same transaction as every deletion (account deletion incl. cleanup of abandoned registrations, deleting a history); `ON CONFLICT DO NOTHING`; part of `USER_TABLES` (after `notified_retirement`), covered by the fail-closed FK test; no foreign key (the IDs point to rows that are already deleted).
- Rights classification remains the only gate; no SQL in `normly_core/exchange/`, `graph/domain.py` and in the routers/services (repository layer only, ADR-006); new Protocol methods without a `get_`/`list_` prefix, unless they take `jurisdiction` (guard in `core/tests/graph/test_architecture.py`; exceptions with a rationale only if unavoidable).
- Idempotency: every cleanup and replay step is repeatable without a differing result. The cleanup command and the replay print only counters/ID counts, never contents.
- Export: no password hash, no tokens (neither account session, chat session nor one-time tokens), no bookkeeping tables.
- Language: code/commits English; ADRs/spec/plan/SRS/CLAUDE.md German; `docs/guide/*` English (ADR-020). License header AGPL-3.0-or-later in new files. No secrets/real names in tests.
- Commits: Conventional Commits, `git commit -s` (Signed-off-by of the human), trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; **never** `git config`; no push/PR without asking first. ShellCheck with `koalaman/shellcheck:v0.9.0` (CI version). The machine has limited memory: run test commands **one after the other**, the complete core suite at most once per task at the end; never mix script tests (`.venv/bin/pytest scripts/tests`) and core tests in one run.

## File overview

| File | Change |
|---|---|
| `core/src/normly_core/retention.py` | new: period constants |
| `core/migrations/versions/0035_create_deletion_log.py`, `graph/postgres/orm.py`, `graph/domain.py`, `graph/postgres/repositories.py` | `deletion_log`, writing the log, cleanup and deletion methods |
| `core/src/normly_core/exchange/tables.py` | `deletion_log` in `USER_TABLES` |
| `core/src/normly_core/pipeline/cli.py` | `cleanup-user-data` |
| `chat/src/normly_chat/routers/chat.py`, `routers/sessions.py`, `session_resolution.py`, `schemas.py` | anonymous without storage, DELETE endpoints |
| `frontend/src/app/api/chat/**`, `components/chat/**`, `lib/session-cookies.ts` | no chat cookie for anonymous chats, delete buttons, BFF routes |
| `accounts/src/normly_accounts/routers/account_management.py`, `schemas.py` | export completed |
| `core/src/normly_core/exchange/deletions.py`, `exchange/__main__.py` | `export-deletions`, `replay-deletions` |
| `scripts/normly-deploy`, `scripts/normly-cleanup`, `deploy/systemd/normly-cleanup.{service,timer}`, `docker/python.Dockerfile` | rollback extension, timer, image files |
| `docs/adr/README.md`, `docs/guide/operations.md`, `docs/guide/self-hosting.md`, specs | ADR-027, operations |

---

### Task 1: Core — periods, deletion log, cleanup command

**Files:**
- Create: `core/src/normly_core/retention.py`, `core/migrations/versions/0035_create_deletion_log.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (`DeletionLogORM`), `graph/domain.py` (Protocols), `graph/postgres/repositories.py`, `core/src/normly_core/exchange/tables.py`, `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/retention/test_cleanup_user_data.py` (new), `core/tests/graph/test_deletion_log.py` (new), additional tests in existing files (`test_account_sessions_and_deletion.py`, `core/tests/exchange/test_tables.py`, `core/tests/pipeline/test_cli.py`)

**Interfaces:**
- Produces:
  - `retention` constants (see Global Constraints) as `datetime.timedelta`.
  - `DeletionLogRepository` (Protocol + `PostgresDeletionLogRepository`): `record(*, kind: str, entity_id: uuid.UUID, deleted_at: datetime) -> None` (ON CONFLICT DO NOTHING), `entries_since(since: datetime) -> list[tuple[str, uuid.UUID, datetime]]` (**note** `entries_since` does not start with `get_`/`list_`), `delete_older_than(cutoff: datetime) -> int`.
  - Repository methods (names freely chosen, but without a `get_`/`list_` prefix; each with a `cutoff`/`now` parameter, return value: number of deleted rows): sessions `delete_sessions_expired_before`, tokens `delete_tokens_done_before`, abandoned registrations `delete_unverified_accounts_created_before` (the condition including the NOT EXISTS exclusions is checked again under a `FOR UPDATE` lock) (uses the same cascade as `delete_account` and writes one log entry `account` per account), notifications `delete_unread_before` (in addition to `delete_read_before`), anonymous chats `delete_anonymous_chat_sessions` (cascade citations → messages → session; **no** log entry, because anonymous data never need to belong to a restore? — yes, they do: they are in old backups and reappear after a rollback; so write one entry `chat_session` per deleted anonymous session), deleting a chat history `delete_chat_session(session_id, account_id) -> bool` (own only; logged) and `delete_chat_sessions_for_account(account_id) -> int` (logged per session).
  - `delete_account(account_id)` additionally writes `deletion_log(kind="account", entity_id=account_id)` in the same transaction; it deletes the account's chats as before (the account's chat sessions get **no** entry of their own, the `account` entry covers them).
  - CLI `python -m normly_core.pipeline cleanup-user-data`: enforces all periods with `datetime.now(timezone.utc)` (incl. `delete_read_before` with `READ_NOTIFICATION_MAX_AGE`), commits at the end, prints one line `sessions=<n> tokens=<n> unverified_accounts=<n> notifications_read=<n> notifications_unread=<n> anonymous_chats=<n> deletion_log=<n>`; `cleanup-notifications` remains unchanged.
- Behavior: order in the command: deletions first, then prune `deletion_log`. Abandoned registrations: `email_verified_at IS NULL AND created_at < now - 30d AND NOT EXISTS account_google_identity AND NOT EXISTS account_session` (sessions disappear 7 days after expiry, so an account unused for ~37 days counts as abandoned). Tokens: `expires_at < now - 24h OR used_at < now - 24h`. Sessions: `expires_at < now - 7d`. Unread notifications: `read_at IS NULL AND created_at < now - 365d`. Boundaries strict (`<`).

- [ ] **Step 1: Write failing tests** (fixtures as in `core/tests/graph/test_account_sessions_and_deletion.py` and `core/tests/notifications/`; check the real signatures of the repositories with grep before writing and adapt the tests to the parameters, not their assertion): per period one test with rows just **before** and just **after** the boundary (only the old ones disappear), idempotency (second run deletes 0), verified accounts and accounts with verification untouched, cascade when deleting an abandoned registration (without session/Google; accounts with a Google link or a session remain) (chats, tokens, sessions, watches, notifications, bookkeeping, avatar) and log entry `account`, old anonymous chats (session without `account_id` deleted together with messages and citations, account sessions remain, log entry `chat_session`), `delete_chat_session` (own → True; someone else's/unknown → False and nothing deleted; logged), `delete_chat_sessions_for_account`, `delete_account` writes `deletion_log`, `PostgresDeletionLogRepository` (record idempotent, `entries_since` time boundary, `delete_older_than`), CLI output line and commit; `test_tables.py`: `deletion_log` in `USER_TABLES` and the fail-closed FK test stays green; `test_architecture.py` green; ORM↔migration consistency and determinism green.
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/retention tests/graph/test_deletion_log.py -q` — Expected: FAIL (missing modules/methods).
- [ ] **Step 3: Implementation** as above. Migration `0035` (style and revision IDs of its neighbors, `revision = "0035"`, `down_revision = "0034"`): table `deletion_log` with `kind` (string, CHECK `kind IN ('account','chat_session')`), `entity_id` (UUID), `deleted_at` (timestamptz, NOT NULL), primary key `(kind, entity_id)`, index on `deleted_at`; `downgrade` drops the table.
- [ ] **Step 4:** focused tests (`tests/retention tests/graph tests/exchange tests/pipeline -q`, one at a time), then the complete core suite once (`cd core && ../.venv/bin/pytest tests -q`).
- [ ] **Step 5: Commit** `feat(retention): deletion log, retention constants and cleanup-user-data` (with `-s` and trailer).

### Task 2: Chat — anonymous without storage, deleting histories

**Files:**
- Modify: `chat/src/normly_chat/routers/chat.py`, `routers/sessions.py`, `session_resolution.py`, `schemas.py`; `frontend/src/app/api/chat/route.ts`, `frontend/src/app/api/chat/sessions/route.ts` (+ new routes `frontend/src/app/api/chat/sessions/[id]/route.ts`), `frontend/src/lib/session-cookies.ts`, `frontend/src/components/chat/chat-history-sidebar.tsx`, `frontend/src/lib/i18n/{de,en}.json`
- Test: `chat/tests/…` (adapt/extend the existing chat tests), `frontend/tests/unit/…` (sidebar, cookie logic, BFF routes)

**Interfaces:**
- Consumes: `delete_chat_session`, `delete_chat_sessions_for_account` from Task 1.
- Produces: `POST /v1/chat` with an optional `session_token` in the response (`None` for anonymous); `DELETE /v1/chat/sessions/{session_id}` (Bearer account token required; response 204 on success, 404 for someone else's/an unknown ID, 401 without a valid account); `DELETE /v1/chat/sessions` (all of one's own; 200 with `{"deleted": <n>}`); frontend: `DELETE /api/chat/sessions/[id]` and `DELETE /api/chat/sessions`; a delete button per history with a confirmation dialog and "Delete all histories" in the sidebar; i18n keys in de/en.

- [ ] **Step 1: Failing tests** — chat service: anonymous request (no `Authorization`) → response 200 with answer text, `session_token` is `None`, **no** new rows in the database in `chat_session`, `chat_message`, `chat_message_citation`; anonymous request with a `session_token` of an account session sent along → no appending, no write accesses; a request with an invalid account token behaves like an anonymous one; a request with a valid account creates session/messages/citations as before (existing tests stay green); `resolve_session`: no more `link_account` for anonymous sessions (the test that checked the linking on sign-in is removed/replaced, with the rationale in the report); DELETE endpoints (own history deleted incl. messages/citations and log entry, someone else's → 404 without change, without token → 401, "all" deletes only one's own). Frontend (Vitest): `api/chat/route.ts` sets **no** chat cookie for a response without `session_token` and deletes an existing one (`maxAge: 0`), session cookie behavior for accounts unchanged; sidebar: the delete button calls the BFF route after confirmation and removes the entry; "Delete all"; error case (response not ok) leaves the list unchanged.
- [ ] **Step 2:** run focused (`cd chat && ../.venv/bin/pytest -q`; `cd frontend && npx vitest run tests/unit/<file>` — if `frontend/node_modules` is missing, first `cd frontend && npm ci`; commands one at a time) — Expected: FAIL.
- [ ] **Step 3: Implementation.** `chat.py`: resolve the identity first; without an identity, call neither `resolve_session` nor `create_message`/`add_citation`, `ChatResponse.session_token = None`; `session_resolution.py` remains for accounts (without the `link_account` branch for `account_id is None`; if `session.account_id` does not match the identity → new session as before). `schemas.py`: `session_token: str | None`. Frontend: set the cookie only for a string token, otherwise delete it; adapt the `CHAT_COOKIE_MAX_AGE_SECONDS` comment (now only for accounts).
- [ ] **Step 4:** complete suites once: `cd chat && ../.venv/bin/pytest -q`; `cd frontend && npx vitest run` and `npx tsc --noEmit`.
- [ ] **Step 5: Commit(s)** `feat(chat): do not store anonymous chats; let users delete their chat history` (with `-s` and trailer).

### Task 3: Completing the export

**Files:**
- Modify: `accounts/src/normly_accounts/routers/account_management.py`, `accounts/src/normly_accounts/schemas.py`, repository methods in `core/src/normly_core/graph/postgres/repositories.py`/`graph/domain.py` (read methods for readable document IDs and citations; names without a `get_`/`list_` prefix, or with `jurisdiction` if needed and then deliberately in `JURISDICTION_EXEMPT_READS` with a rationale)
- Test: `accounts/tests/test_account_export.py` (adapt and extend the existing export tests)

**Interfaces:**
- Produces (response shape, binding): `ExportChatSession`: `id` (UUID) instead of `session_token`, `jurisdiction`, `language`, `created_at`, `messages`; `ExportChatMessage`: `role`, `content`, `answer_type: str | None`, `created_at`, `citations: list[ExportCitation]`; `ExportCitation`: `document: ExportDocumentRef`, `segment_id: UUID | None`; `ExportDocumentRef`: `id`, `origin_issuer`, `origin_number`, `edition`, `part`; `ExportWatchlistEntry`: `work_id`, `created_at`, `documents: list[ExportDocumentRef]` (all documents of the work, including retired ones); `ExportNotification` unchanged. No `session_token`, no tokens, no hash.
- The read methods are **unchecked** (without the rights gate), because they only return IDs (publisher, number, edition, part) of one's own data, never content; give the rationale in the docstring.

- [ ] **Step 1: Failing tests** — the export contains `answer_type` per chat message and citations with a readable document reference (also for a retired document/tombstone: the ID stays readable, `segment_id` is `None` after a withdrawal), the watchlist names document references of the work, the chat session token does not occur (search in the serialized JSON for the token value), access by others and missing sign-in (401) as before, no password hash/token fields (search for `password`, `token` in the keys of the response), one person's export contains no data of another.
- [ ] **Step 2:** `cd accounts && ../.venv/bin/pytest tests/test_account_export.py -q` — Expected: FAIL.
- [ ] **Step 3: Implementation** as above. The frontend (`export-section.tsx`) remains unchanged (it serializes the response 1:1); check this and confirm it in the report.
- [ ] **Step 4:** `cd accounts && ../.venv/bin/pytest -q` (complete), `cd core && ../.venv/bin/pytest tests/graph -q`.
- [ ] **Step 5: Commit** `feat(accounts): complete the personal data export` (with `-s` and trailer).

### Task 4: Replaying deletions in the rollback, cleanup timer

**Files:**
- Create: `core/src/normly_core/exchange/deletions.py`, `scripts/normly-cleanup`, `deploy/systemd/normly-cleanup.service`, `deploy/systemd/normly-cleanup.timer`, `core/tests/exchange/test_deletions.py`, `scripts/tests/test_cleanup.py`
- Modify: `core/src/normly_core/exchange/__main__.py` (`export-deletions`, `replay-deletions`), `scripts/normly-deploy`, `docker/python.Dockerfile` (COPY of `scripts/normly-cleanup`), `scripts/tests/conftest.py` (additive only), rollback tests in `scripts/tests/`

**Interfaces:**
- Consumes: `PostgresDeletionLogRepository.entries_since`, `PostgresAccountRepository.delete_account`, `delete_chat_session` (Task 1).
- Produces:
  - `deletions.build_document(entries, *, created_at) -> str` / `parse_document(text) -> list[(kind, UUID)]`; JSON: `{"format": 1, "created_at": "<ISO UTC>", "entries": [{"kind": "account"|"chat_session", "entity_id": "<uuid>", "deleted_at": "<ISO UTC>"}, ...]}` sorted by `deleted_at`, `kind`, `entity_id`; `parse_document` raises `ValueError` for a wrong version/structure/unknown `kind`.
  - CLI: `python -m normly_core.exchange export-deletions --since <ISO-8601 with time zone>` → JSON on stdout (only the document); `python -m normly_core.exchange replay-deletions` reads JSON from stdin, applies every deletion (account: `delete_account` if present; chat: `delete_chat_session` without the ownership check via an internal method **only for the replay** `delete_chat_session_by_id`), writes the log in doing so, commits, prints `replayed deletions: <n> applied, <m> already gone`; invalid input → exit 1, nothing changed; `replay-deletions --check` needs **no** database, exit 0 (shows that the image knows the command).
  - `scripts/normly-cleanup`: like `normly-backup` (loads `.env` via `normly-env.sh`, `NORMLY_COMPOSE` default `docker compose -f $NORMLY_DIR/current/compose.yaml --project-directory $NORMLY_DIR/current`) and calls `$COMPOSE run --rm --no-deps -T pipeline cleanup-user-data`; pass the command's exit code through; timer daily at 04:00 UTC with `Persistent=true`, service `Type=oneshot`.
  - `normly-deploy rollback` (final behavior, see spec "Implementation" 6): In the **preliminary phase** (after the tombstone preliminary phase, before banner and confirmation), read the deletions directly from the database via host `psql` (`-v since=…`) and host `python3` (no startable image needed; filter `deleted_at` > backup time minus 1 hour; the core command `export-deletions` remains for manual use). Before the DROP, the list is written to `$STATE/rollback-deletions.json` (0600), and a renewed run merges it with the fresh export (the file is deleted after a successful `up`). `normly-cleanup`/`normly-backup` set `NORMLY_IMAGE_TAG` from `state/current_tag` (time taken from the base name `YYYYMMDDTHHMMSSZ-...` and converted to ISO-8601 UTC via python3; the safety margin lies in the script, the core stays strictly "later than"; error or invalid document → `die "... nothing was changed"`), result in `$WORK/deletions.json`; if the table `deletion_log` is missing (`to_regclass`), an empty list. Run `replay-deletions --check` with the **previous** release (only exit code 2 = not supported; any other error → abort before the banner). After `down` and before the DROP, a **second export** (`$WORK/deletions-final.json`, same rules; error → abort, services stopped, database unchanged; restart note with `NORMLY_IMAGE_TAG=<tag>`); this document is applied after `pg_restore` (and after `import-tombstones`) with `replay-deletions < "$WORK/deletions-final.json"`. Not supported and list not empty → banner line with the count and the first 20 IDs ("previous release cannot replay deletions; re-delete these by hand after the rollback …"), the complete list (only if the second export contains entries) in `$STATE/rollback-pending-deletions.json` (0600; removed at the start of every rollback), the rollback continues after confirmation; list empty → no replay call. An error during the replay after `DESTRUCTIVE=1` counts like any other error (restore note, lock released, state unchanged). `normly-cleanup` skips its run as long as `state/deploy.lock` exists.

- [ ] **Step 1: Failing tests** — core: export (time boundary: an entry exactly at the time is not output, after it it is; document valid; stdout only), replay (account present → deleted and logged; account missing → "already gone"; chat session; idempotency; invalid document → exit 1 without change; `--check` without a database), end-to-end rollback simulation (scenario: account A with a chat and a watch is deleted after the backup time → export the log, reset user data to the state of the backup [re-insert rows from a copy saved before the deletion], replay → account A and its chats are deleted again, the log contains the entry). Scripts (fake harness): order in the rollback (`export-deletions` before banner/prompt/`down`/DROP; replay after `pg_restore`, after `import-tombstones`), an error during the export aborts before any change, previous image without the command (`replay-deletions --check` fails): the banner names the IDs and the rollback continues after confirmation, list empty: no replay call, replay error after the DROP: restore note; `normly-cleanup`: call of the pipeline command, exit code passed through. Existing tests green (harness additive only).
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/exchange/test_deletions.py -q`, then in the repo root `.venv/bin/pytest scripts/tests -q` — Expected: FAIL.
- [ ] **Step 3: Implementation** as above; ShellCheck `docker run --rm -v "$PWD":/mnt -w /mnt koalaman/shellcheck:v0.9.0 scripts/normly-deploy scripts/normly-backup scripts/normly-env.sh scripts/normly-cleanup` clean; add the Dockerfile COPY and `docker buildx build --check --target pipeline -f docker/python.Dockerfile .` without warnings.
- [ ] **Step 4:** `cd core && ../.venv/bin/pytest tests/exchange tests/graph -q`; `.venv/bin/pytest scripts/tests -q`.
- [ ] **Step 5: Commit** `feat(rollback): replay deletions after a restore; add the cleanup timer` (with `-s` and trailer).

### Task 5: Documentation

**Files:** `docs/adr/README.md` (ADR-027, register), `docs/guide/operations.md`, `docs/guide/self-hosting.md` (cleanup command), `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md` (status), `docs/srs/…` (references only if a matching REQ exists)

- [ ] **Step 1: ADR-027** "Lifecycle of user data" (German, format of the neighboring ADRs): context (inventory), decision (principle, data inventory as a table per table with purpose, personal data, period, deletion path; anonymous chat without storage; chats with an account until deletion; periods (accounts: only abandoned registrations = unverified, without a Google link and without an account session, 30 days after creation; accounts in use remain even without verification); export; deletion log and replay), rationale, rejected (period also for account chats; anonymous sessions with short-term storage; cryptographic erasure per account in backups; asynchronous export), consequences/open (after-effect in backups: Flex 30 days, own backups roughly two months, pre-rollout up to three releases; deletion log 90 days; expert review of the periods; a previous release without the replay command needs manual re-deletion; the linking "anonymous → account on sign-in" is deliberately dropped; tombstone retention from ADR-026 remains open; privacy policy out of scope).
- [ ] **Step 2: `docs/guide/operations.md`** (English): cleanup (install/enable the timer, table of periods, `cleanup-user-data` manually), rollback (deletions are read/re-applied, behavior with an old image), restore test (additional steps `export-deletions`/`replay-deletions`), emergency restore from Flex (instructions: back up/export the deletion log before the restore, then `replay-deletions`), note on the maximum after-effect in backups. `self-hosting.md`: cleanup command and anonymous behavior, briefly.
- [ ] **Step 3:** set the spec status to "implemented", update the ADR register rows (open items).
- [ ] **Step 4:** docs build as in CI (docker `python:3.12`, `pip install "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0"`, `zensical build`, line `3 issues found`; with `--user "$(id -u):$(id -g)"`, a writable HOME and the venv under `/tmp`; afterwards remove `site/` and `.cache/`).
- [ ] **Step 5: Commit** `docs: ADR-027 user data lifecycle, operations guide` (with `-s` and trailer).

## Self-review against the spec

| Spec section | Task |
|---|---|
| 1 Anonymous chat without storage | Task 2 (chat, frontend), Task 1 (old data in the cleanup command) |
| 2 Cleanup command and timer | Task 1 (command), Task 4 (script, timer) |
| 3 Deleting histories | Task 1 (repository), Task 2 (endpoints, UI) |
| 4 Completing the export | Task 3 |
| 5 Deletion log | Task 1 (table, writing, pruning), Task 4 (export/replay) |
| 6 Rollback | Task 4 |
| ADR-027, operations guide | Task 5 |

**Risks:** The replay must run against the schema of the **previous** release (hence the check of the command in the previous image); the core's deletion functions may know tables that are missing in the older schema — the replay runs in the previous image with its code and schema; frontend tests need `npm ci` (memory); a real `docker compose run -T` with stdin/stdout remains part of the live acceptance.

---

## Extension: advance warning before deleting abandoned registrations

**Reason (final review, I1 and owner decision 2026-10-10):** The rule "unverified, older than 30 days, without a Google link, without an account session" also deleted password accounts that were used and then paused, without any announcement. Decision: **No account is deleted silently; it takes an advance warning e-mail with a deadline.** This task replaces the direct deletion with warn → deadline → delete and adapts ADR-027, the operations guide and the spec.

### Task 6: Advance warning e-mail for abandoned registrations

**Files:** migration `core/migrations/versions/0036_add_account_deletion_warned_at.py`; `core/src/normly_core/graph/postgres/orm.py` (`AccountORM.deletion_warned_at`); `graph/domain.py` (Account dataclass only if needed, Protocol); `graph/postgres/repositories.py`; `core/src/normly_core/retention.py` (`ACCOUNT_DELETION_NOTICE_PERIOD = 14 days`); `core/src/normly_core/pipeline/cli.py` (`cleanup-user-data`); tests in `core/tests/retention/`; docs (ADR-027, `docs/guide/operations.md`, spec).

**Behavior (binding):**
- "Abandoned" = `email_verified_at IS NULL` AND `created_at < now - UNVERIFIED_ACCOUNT_MAX_AGE (30 days)` AND no `account_google_identity` AND no `account_session` (unchanged; the existing helper method `_abandoned_registration_ids` remains the only source of the condition).
- Per run of `cleanup-user-data`, in this order:
  1. **Reset:** accounts with `deletion_warned_at` set that are no longer "abandoned" (verified, Google link or account session present) get `deletion_warned_at = NULL`.
  2. **Delete:** accounts that are "abandoned" and whose `deletion_warned_at < now - ACCOUNT_DELETION_NOTICE_PERIOD (14 days)` (strictly `<`) — with the existing cascade `delete_account` (log entry as before), with the existing re-check/lock (`FOR UPDATE` and a renewed check in the same statement, now including the `deletion_warned_at` condition).
  3. **Warn:** accounts that are "abandoned" and have `deletion_warned_at IS NULL`: e-mail to `account.email` via the existing `EmailSender` (`SmtpEmailSender` from the `NORMLY_SMTP_*` environment as in `notify-watchers`; `NullEmailSender` if no SMTP host is set). **Only if sending succeeded** is `deletion_warned_at = now` set. If sending fails, it stays NULL (the error is logged, the next run tries again), the run does not abort.
- **Never delete without a delivered warning:** With `NullEmailSender` (no SMTP), a warning is never set and so nothing is ever deleted (one test for this). No account is warned and deleted in the same run (order 1 → 2 → 3; an account warned in step 3 has `deletion_warned_at = now`).
- The e-mail: bilingual subject "Dein normly-Konto wird gelöscht / Your normly account will be deleted"; bilingual text (German, then English) with: the account was never verified and has not been used for a long time; it will be deleted on `<date = deletion_warned_at + 14 days, in ISO format YYYY-MM-DD>` if one does not sign in by then; sign-in URL `NORMLY_PUBLIC_BASE_URL` (environment variable, as the rest of the code uses it; if not set, no link, only the note "Melde dich bei normly an", i.e. sign in to normly); no further personal data apart from the recipient address; no token in the link.
- The summary line of `cleanup-user-data` is extended by `warnings_sent=<n>` (field at the position after `unverified_accounts=<n>`; number of warnings actually delivered); `unverified_accounts` still counts deleted accounts.
- The column `account.deletion_warned_at` (timestamptz, NULL) is part of the user data backup (data rows of the table `account`, automatically), is **not** exported and not shown to users; `delete_account` and the export are unchanged.
- The constants are in `retention.py`; ADR-027, the operations guide (section on cleanup: warn/deadline/delete sequence, SMTP prerequisite, what happens without SMTP, reset by signing in) and the spec ("unverified accounts" → "abandoned registrations with advance warning") are adapted; the false statement in ADR-027/the operations guide that a used account is "never" removed is replaced by the actual rule.

- [ ] **Step 1: Failing tests** (`core/tests/retention/`, fixtures as in the existing tests; a fake `EmailSender` that records calls and optionally fails): abandoned + not warned → mail to the right address (subject/text contain the date and are bilingual) and `deletion_warned_at` set; sending fails → NULL, no abort, no deletion; `NullEmailSender` → no warning, no deletion, even for a very old account; warned 13 days ago → remains; warned 15 days ago and still abandoned → deleted (cascade, log `account`); warned, then verified/Google/session → `deletion_warned_at` NULL and not deleted; boundary `deletion_warned_at == now - 14 days` → remains (strict); no account is warned and deleted in the same run; idempotency (second run: no second mail, no further deletion); the summary line with `warnings_sent`; ORM↔migration, determinism, `test_tables.py`, `test_architecture.py`, export test (no `deletion_warned_at` in the export).
- [ ] **Step 2:** `cd core && ../.venv/bin/pytest tests/retention -q` — Expected: FAIL.
- [ ] **Step 3: Implementation** as above (migration `0036`, `down_revision = "0035"`; repository methods without a `get_`/`list_` prefix; the CLI builds the `EmailSender` like `notify-watchers` from `NORMLY_SMTP_*`).
- [ ] **Step 4:** focused tests one at a time, then the complete core suite once.
- [ ] **Step 5: Commit** `feat(retention): warn by e-mail before deleting abandoned registrations` (with `-s` and trailer).

### Addendum to Task 6 (final review): sign-in as lasting activity

The final review found: only an existing `account_session` row counted as activity. If a warned person signed in and out again (the row is deleted), the account counted as abandoned again, and the warning was not reset. Decided (option A): migration `0037` adds `account.last_login_at`; `create_session` sets it on every sign-in path; "abandoned" additionally requires `last_login_at IS NULL OR last_login_at < now - 30 days`. The column is not exported. The warning mail gives the date as "frühestens am" / "at the earliest", because the daily run can shift the time by up to one day. The trap of `normly-deploy` also cleans up `.rollback-pending-deletions.new`.
