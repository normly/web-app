# Design: Watchlist/notification (Normtracker foundation, part 4/5)

## Context

Sub-projects 1–3 as well as two subsequently inserted prerequisite
sub-projects (edition change detection, edition-aware identity
resolution) are merged. With that, EUR-Lex and DGUV now reliably create
real `REPLACES` edges with correct work assignment — the main trigger
for this sub-project exists and works, even with unsorted
or bundled ingestion.

Currently nothing of watchlist/notification exists: the bell icon in the
header (`frontend/src/components/page-header.tsx`) is purely decorative
(always shows "no notifications"), there is no favorites concept
anywhere in the frontend, and auth/email sending live exclusively in the
`accounts/` service — the service that owns Works/Documents/Edges/Rights
(`api/`) currently has no auth. `accounts/` moreover has no
database models of its own: all tables (`Account`, `AccountSession`,
etc.) live in `core/`'s shared ORM layer (`core/src/normly_core/
graph/postgres/orm.py`), and all services (`accounts/`, `api/`, `chat/`)
connect to the same physical Postgres database via the same
environment variable (`NORMLY_DATABASE_URL`). A new watchlist table
can therefore have a real foreign key to `work.id`.

So far this project has deliberately had no scheduler (ingestion is
CLI-only, rate-limit bucket cleanup happens opportunistically instead of via
a cron job) and no event/hook mechanism in the graph. A
periodic detection job therefore needs a new CLI subcommand,
triggered externally — no new scheduler in the code itself.

## Goal of this sub-project

1. Users can mark a work as a favorite via a heart icon on the document detail
   page (= add it to the watchlist).
2. In the profile settings, users set whether and how they want to be notified about
   changes to their favorited works:
   not at all, only in the software, only by email, or both.
3. A new, externally triggered CLI job detects three kinds of change to
   a watched work — new edition, new national version,
   rights classification change — and creates one notification per watcher for every real,
   not yet processed change.
4. Depending on the preference, an email is sent and/or the
   notification appears in the (so far purely decorative) bell icon in the
   header, which gets real data for this for the first time.

## Non-goals

- **No retry/queue for failed email sending.** Stays with the
  existing fail-soft convention (best effort, `try/except`, no
  further attempt) — the same convention that magic link/password reset
  already use today.
- **No push notifications** (browser or mobile) — only an in-app
  popover and email.
- **No digest summary** ("weekly summary of several
  changes in one email"). Every change is its own notification
  and its own email.
- **No automatic cleanup of old `Notification` entries.** Left
  for a later sub-project.

## Architecture

### Data model (everything in the shared `core/` ORM)

**`account.notification_preference`** — new column on the existing
`AccountORM`. Python enum `NotificationPreference` (`NONE`, `IN_APP`,
`EMAIL`, `BOTH`), mapped via `sa.Enum(..., native_enum=False,
create_constraint=True, values_callable=_enum_values)` — the same pattern
as `WorkStatus`/`LegalBasisCategory`. Default `NONE`: no silent opt-in
into existing email delivery.

**`WatchlistORM`** — new table, the favorites list:
```
id: uuid, primary key
account_id: uuid, FK account.id
work_id: uuid, FK work.id
created_at: datetime
UniqueConstraint(account_id, work_id)
```

**`NotificationORM`** — new table, serves both as a dedup log ("has
this change already been processed for this watcher?") and as the
data source for the in-app feed:
```
id: uuid, primary key
account_id: uuid, FK account.id
work_id: uuid, FK work.id
trigger_type: enum (NEW_EDITION, NATIONAL_ADOPTION, RIGHTS_CHANGE)
trigger_edge_id: uuid | None, FK edge.id  -- gesetzt für NEW_EDITION/NATIONAL_ADOPTION
trigger_document_id: uuid | None, FK document.id  -- gesetzt für RIGHTS_CHANGE
trigger_jurisdiction: str | None  -- gesetzt für RIGHTS_CHANGE
created_at: datetime
read_at: datetime | None  -- In-App-Gelesen-Status, NULL = ungelesen
emailed_at: datetime | None  -- NULL = nicht per Mail zugestellt
UniqueConstraint(account_id, work_id, trigger_type, trigger_edge_id)
  -- für NEW_EDITION/NATIONAL_ADOPTION; RIGHTS_CHANGE nutzt eine separate
  -- Eindeutigkeits-Prüfung, siehe Trigger-Erkennung
```

### Trigger detection: `notify-watchers` CLI subcommand

Newly registered in `core/src/normly_core/pipeline/cli.py`, same
`argparse` subcommand style as `ingest`/`backfill-document-embeddings`,
uses the same engine/session already built in `main()`. Triggered externally via
cron/systemd timer/STACKIT scheduler — no new scheduler in the
code.

Per run, for every `WatchlistORM` entry (one account, one watched
work):

1. **`NEW_EDITION`/`NATIONAL_ADOPTION`**: all `REPLACES`/`WITHDRAWN_BY`
   or `ADOPTED_FROM` edges, respectively, whose `to_document_id` belongs to a Document
   of this work. `EdgeORM.created_at` already exists as a
   column, but is not exposed on the `Edge` domain dataclass —
   it is added, together with a new `EdgeRepository` method that
   lists edges for a work since a point in time (or simply all of them, see below).
   For every edge found: does a
   `Notification` entry with exactly `(account_id, work_id, trigger_type,
   trigger_edge_id)` already exist? If not → new entry.
2. **`RIGHTS_CHANGE`**: `RightsClassificationORM.classified_at` is set anew on
   *every* reclassification, even without a change in
   content (the upsert logic always overwrites the field). A pure
   timestamp comparison would therefore trigger a false notification on every re-ingestion with
   unchanged values. The job
   therefore compares the actual rights fields (`may_process`,
   `may_index_fulltext`, `may_cite_passages`, `may_export_free`) against
   the values recorded with the last `Notification` entry for this
   `(account_id, work_id, trigger_document_id, trigger_jurisdiction)`
   (for this, the four bool values are stored as columns of their own
   on `NotificationORM`, not looked up
   separately) — a new entry is created only on a real deviation.
3. For every newly created `Notification` entry: if the account's
   `notification_preference` is `EMAIL` or `BOTH`,
   an email is sent (see below) and `emailed_at` is set. Otherwise
   `emailed_at` stays `NULL`. `read_at` is always `NULL` on creation.
   If an account preference is `NONE`, no `Notification` entry
   is created for this work at all (no data junk for
   users who want nothing).

No need for a "since when" timestamp cutoff: on every run the job scans
all currently relevant edges/classifications per
watched work and relies on the `Notification` table itself
for dedup — robust against missed or repeated runs, consistent with
this project's idempotency principle.

### Email sending

The `EmailSender` protocol as well as `SmtpEmailSender`/`RecordingEmailSender`
(currently in `accounts/src/normly_accounts/email.py`) move to `core/`
— pure infrastructure without accounts-specific logic, and the new
CLI job (which lives in `core/`) must not depend on `accounts/`.
From now on, `accounts/` imports the classes from `core/`; all
existing call sites (`registration.py`, `magic_link.py`,
`password_reset.py`, `email_change.py`) stay unchanged, and their
existing tests must stay green unchanged.

New notification emails follow the existing style: plain text in
German, one link, no attachment, wrapped in `try/except` (an SMTP error
must not abort the job — best effort, no retry).

### Frontend: favoriting + profile setting

**Heart icon** on the document detail page (`frontend/src/app/
documents/[id]/document-detail-content.tsx`, from sub-project 3) — a new
toggle button that calls a new, authenticated `POST`/`DELETE
/v1/accounts/watchlist` endpoint in `accounts/` (body: `work_id`).
Shows filled/empty depending on whether the current work is already on the
signed-in user's watchlist (a new `GET
/v1/accounts/watchlist/{work_id}` check or part of the document detail
response — the detail is left to the implementation plan).

**Profile setting**: a new section in the existing `profile-overlay.tsx`
(dialog with tab navigation, `SECTIONS` list) that sets `notification_
preference` via the existing `PATCH /v1/accounts/profile` endpoint
(whose `UpdateProfileRequest`/`AccountResponse` are extended by the new field,
the same `model_fields_set` partial-update pattern as
for `first_name`/`last_name`).

### Frontend: real in-app notifications

A new `useNotifications` hook (same pattern as the existing
`useAccountSession` hook: `fetch` on mount, `useState`, manual
refresh function), backed by new `GET /v1/accounts/notifications`
(list) and `PATCH /v1/accounts/notifications/{id}` endpoints (mark as
read, sets `read_at`). The existing bell icon in
`page-header.tsx` (currently a static `Popover` shell with
`t("nav.noNotifications")`) renders the real list from now on — no new
design, just real data instead of the static line.

## Tests

- `core/`: repository tests for `WatchlistRepository`/
  `NotificationRepository`; CLI job tests (real Postgres via
  testcontainers) for all three trigger types, including: no
  false positive on `RIGHTS_CHANGE` when a re-ingestion classifies the same
  rights values again; dedup (a second run over
  unchanged data creates no duplicate `Notification` entries);
  `notification_preference == NONE` creates no entry at all.
  `SmtpEmailSender`/`RecordingEmailSender` tested after the move at
  their new location in `core/`.
- `accounts/`: endpoint tests for watchlist add/remove, profile update with
  `notification_preference`, notifications list/mark as read.
  Existing email tests (`registration.py` etc.) stay green unchanged,
  since only the import path changes.
- `frontend/`: heart icon interaction (toggle, filled/empty state),
  new profile settings section, `useNotifications` hook plus
  bell popover with real (mocked) data instead of the static
  line.
