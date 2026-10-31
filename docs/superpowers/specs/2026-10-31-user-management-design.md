# User management (admin panel) — design

Issue: [#60](https://github.com/normly/web-app/issues/60) · Branch:
`feature/60-user-management` · Status: approved in brainstorming 2026-10-31

## Problem

Accounts exist, but nobody can manage them. There is no role model at all:
`Account` has no role field and no endpoint checks for an administrator.
Publishers cannot be given access to anything beyond the base functions,
abusive accounts cannot be blocked (REQ-SEC-004), and there is no overview of
who has an account. Every later partner feature (usage analytics, deliveries
under REQ-PART-001, billing under REQ-PART-003) depends on a working role
model.

## Goal

A server-side role model and a *User management* page in the web app, shown
in the sidebar only to administrators. Roles are checked on every request on
the server; the UI only hides what the server would refuse anyway.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | One or several roles per account? | Exactly one: `user`, `publisher` or `administrator`. Publisher and administrator include everything a user can do. An administrator is never bound to a publisher. |
| 2 | Where does the publisher list come from? | New table `publisher`. An entry is the **contract partner** whose content usage the publisher role may later see (e.g. DIN Media, not necessarily the issuing body). Administrators create entries inline in the invitation dialog; no separate management page. `source.publisher` stays free text for now. |
| 3 | How is a role bound? | Only through the invitation link, which proves control of the mailbox. A role is **never** granted because an e-mail address matches. Inviting an address that already has an account is allowed; its role changes only when the link is used. A blocked account cannot be invited. |
| 4 | What can *Edit* change directly? | Downgrade to `user` and change the publisher, both effective immediately. Upgrading to publisher or administrator requires an invitation. Blocking is likewise immediate. Name and e-mail of other accounts are not editable. |
| 5 | How does a block work? | Reason from a fixed list (`bulk_retrieval`, `abuse`, `terms_violation`, `other`), no free text. All sessions end, every sign-in path is refused. The person receives a neutral e-mail with a contact address but without the reason. The sign-in page shows "account blocked, contact: …". |
| 6 | Audit log content and retention? | Every administrative action; account IDs only, no e-mail addresses, no foreign keys so entries survive account deletion. Retention 2 years. |
| 7 | Remove account | Same deletion path as self-deletion (ADR-027, cascade plus `deletion_log`). Confirmation by typing the e-mail address. A neutral e-mail informs the person; it is sent once the deletion is committed, so no mail announces a deletion that failed. For abuse, block instead: a removed address can register again. |
| 8 | Invitation e-mail | Language chosen in the dialog (default: admin UI language). States role, publisher if any, 7-day validity, button "Accept invitation". Sender is the instance name, not the administrator's name. Personal message: plain text, max. 500 characters, sent but never stored. |
| 9 | Open invitations | *Resend* issues a new token (old one invalid) and restarts the 7 days. *Withdraw* invalidates immediately. Expired invitations show as *Expired* and can be resent; cleanup deletes them 30 days after expiry. |
| 10 | Protection rules | The last administrator cannot be downgraded, blocked or removed. Nobody can downgrade, block or remove their own account through the panel. |
| 11 | First administrator | CLI command `grant-admin --email …`; the account must exist. Audit actor is "CLI". |
| 12 | Contact address | New optional `NORMLY_CONTACT_EMAIL`; without it the block and removal e-mails link the imprint. |
| 13 | Table engine | No TanStack Table. Search, sort and paging run on the server, so its client-side row models would sit unused. shadcn `table` and `pagination` plus a small column definition suffice. |
| 14 | Delivery | One spec, two PRs against `develop`: backend plus all documents first, then the frontend. |

Dropped from the issue and the mockup:

- "Users carry one or more roles" — replaced by decision 1.
- "Operator role" — the glossary reserves *operator* for whoever runs an
  instance; the role is called *administrator*.
- Sign-in method "SSO" — REQ-INT-003 is not implemented.
- "Role is bound on first login" — replaced by decision 3 (security gap).
- Sidebar entries *Analytics*, *Data sheets* and "Go to publisher view" — not
  part of this issue.
- The fixed text "normly team" on the administrator summary card.

## Architecture

Role, publisher binding and block live on `account`. The accounts service
gets the admin API under `/v1/admin/...`. A dependency
`require_role(Role.ADMINISTRATOR)` reads the role **from the database on every
request**, so a downgrade or block takes effect on the next request.
`GET /v1/accounts/session` additionally returns `role` and `publisher_id`; the
chat service and later services get the role through the session validation
they already perform per request.

Rejected: a separate admin service (another container, duplicated session
handling) and the role inside the session token or cookie (a downgrade or
block would only take effect at the next sign-in).

All database access goes through the repository layer in the core (ADR-006).

## Data model

Migration `0041`.

### `publisher` (new)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | primary key |
| `name` | text | unique, case-insensitive (unique index on `lower(name)`) |
| `created_at` | timestamptz | |

No delete through the UI; the foreign key from `account` restricts deletion
while an account references the entry.

### `account` (new columns)

| Column | Type | Notes |
|---|---|---|
| `role` | enum `account_role` | `user` / `publisher` / `administrator`, not null, default `user`; existing rows become `user` |
| `publisher_id` | uuid, nullable | FK `publisher.id`, `ON DELETE RESTRICT` |
| `blocked_at` | timestamptz, nullable | |
| `block_reason` | enum `block_reason`, nullable | `bulk_retrieval` / `abuse` / `terms_violation` / `other` |

Check constraints: `(role = 'publisher') = (publisher_id IS NOT NULL)`;
`(blocked_at IS NULL) = (block_reason IS NULL)`.

### `account_invitation` (new)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | primary key |
| `email` | text | as entered (normalized by `EmailStr` like every other endpoint); **unique** case-insensitively (unique index on `lower(email)`) |
| `role` | enum `account_role` | |
| `publisher_id` | uuid, nullable | FK `publisher.id`; same check constraint as on `account` |
| `locale` | text | `de` / `en` |
| `token` | text | unique; `secrets.token_urlsafe(32)`, stored like `account_token.token` |
| `invited_by` | uuid, nullable | FK `account.id`, `ON DELETE SET NULL` |
| `created_at` | timestamptz | |
| `expires_at` | timestamptz | `created_at` + 7 days, reset on resend |

A row exists only while the invitation is open or expired. Accepting or
withdrawing deletes it; the audit log keeps the record. The status is derived:
*invited* while `expires_at` is in the future, *expired* afterwards. A new
invitation to an address with an open or expired invitation replaces that row
(new token, role, publisher, locale, expiry).

### `admin_audit_log` (new)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | primary key |
| `occurred_at` | timestamptz | indexed (retention cleanup) |
| `action` | enum `admin_action` | see below |
| `actor_account_id` | uuid, nullable | `NULL` = CLI; no FK |
| `target_account_id` | uuid, nullable | no FK; indexed (export) |
| `target_invitation_id` | uuid, nullable | no FK |
| `target_publisher_id` | uuid, nullable | no FK |
| `details` | jsonb | before/after values: role, publisher ID, block reason, locale |

Actions: `invitation_created`, `invitation_resent`, `invitation_withdrawn`,
`invitation_accepted`, `role_changed`, `publisher_changed`,
`account_blocked`, `account_unblocked`, `account_removed`,
`publisher_created`, `administrator_granted_cli`.

No e-mail addresses in any column or in `details`. Once an account is
deleted, its ID can no longer be linked to a person — the same reasoning as
for `deletion_log` (ADR-027).

### Domain

New enums `Role`, `BlockReason`, `AdminAction`. `Account` gains `role`,
`publisher_id`, `blocked_at`, `block_reason`. New repository protocols
`PublisherRepository`, `InvitationRepository`, `AdminAuditRepository`; the
account list for the admin table is a repository method that combines
accounts and invitations in one query (UNION) so search, sort and paging stay
in the database.

### Retention (`core/src/normly_core/retention.py`)

- `INVITATION_EXPIRED_GRACE = timedelta(days=30)` — measured from `expires_at`.
- `ADMIN_AUDIT_RETENTION = timedelta(days=730)` — measured from `occurred_at`.

`cleanup-user-data` enforces both, idempotently, and prints the counters like
the existing steps.

## Backend

### Admin API (accounts service)

All endpoints require `require_role(Role.ADMINISTRATOR)`: 401 without a valid
session, 403 for other roles.

| Endpoint | Purpose |
|---|---|
| `GET /v1/admin/users?q=&role=&status=&sort=&order=&page=&page_size=` | Accounts and invitations in one list. `q` searches e-mail, first and last name (case-insensitive substring). `status` ∈ `active`, `invited`, `expired`, `blocked`. Sortable by every column; empty values sort last. `page_size` ∈ 10/20/50, default 10. Response: rows plus total count. |
| `GET /v1/admin/users/summary` | Total accounts and those signed in within 30 days (`last_login_at`); accounts per role; publishers with an account; open invitations; blocked accounts and the most frequent block reason. Invitations do not count as accounts. |
| `GET /v1/admin/publishers` | All publishers, ordered by name. |
| `POST /v1/admin/publishers` | `{name}` → 201; 409 `publisher_name_taken`. |
| `GET /v1/admin/invitations/check?email=` | `{existing_account, blocked, open_invitation, verified}` for the dialog hint; `verified` is false without an account, and the dialog warns that accepting resets an unverified account's sign-in data and content. |
| `POST /v1/admin/invitations` | `{email, role, publisher_id?, locale, message?}` → 201, sends the e-mail. 409 `account_blocked`. 400 when `publisher_id` is missing for `publisher` or present otherwise, names an unknown publisher, or the message exceeds 500 characters (the service answers every validation error with 400). |
| `POST /v1/admin/invitations/{id}/resend` | New token and expiry, sends the e-mail without a personal message. |
| `DELETE /v1/admin/invitations/{id}` | Withdraw → 204. |
| `PATCH /v1/admin/accounts/{id}` | `{role?, publisher_id?}`. Only `role: "user"` (downgrade) or a publisher change on a publisher account. 409 `upgrade_requires_invitation`, `last_administrator`, `self_action`. |
| `POST /v1/admin/accounts/{id}/block` | `{reason}`; deletes all sessions, sends the block e-mail. 409 `last_administrator`, `self_action`. |
| `POST /v1/admin/accounts/{id}/unblock` | Clears the block. |
| `DELETE /v1/admin/accounts/{id}` | Body `{confirm_email}` must match → 200 `{email_sent}`; deletes through the ADR-027 path, commits, then sends the removal e-mail. 409 `last_administrator`, `self_action`; 400 on mismatch. |
| `GET /v1/admin/role-matrix` | Rows and cells for "What the roles see", from `permissions.py`; the frontend translates the keys. |

E-mail sending follows the existing pattern: an SMTP failure does not roll
back the administrative action, but the response reports `email_sent: false`
so the UI can say so.

### Sign-in path changes

- **Session validation** (`GET /v1/accounts/session` and
  `get_current_account`) refuses blocked accounts, so the block also applies
  to the chat service and every other service.
- **Password login, magic-link confirmation, Google callback** return
  `403 account_blocked` for a blocked account.
- **Magic-link request and password-reset request** send no e-mail for a
  blocked account; the response stays as neutral as today (no account
  enumeration).

### Accepting an invitation

The e-mail link points to the frontend page `/invitation?token=…`, which shows
an *Accept invitation* button. Only the click sends
`POST /v1/accounts/invitations/accept {token}`. Unlike the magic-link page,
which confirms on load, this is an explicit action: the user consents to a
role, and link scanners cannot consume the token.

On accept, in one transaction:

1. Find the invitation by token; 410 `invitation_invalid` if unknown or
   expired.
2. Find the account by e-mail (same exact lookup as the magic link) or create it (no password). Set
   `email_verified_at` if empty — the click proves the mailbox.
3. 403 `account_blocked` if the account is blocked.
4. 409 `last_administrator` if the new role would remove the last
   administrator.
5. Set role and publisher, delete the invitation, write
   `invitation_accepted` (actor = the accepting account).
6. Create a session and set `last_login_at`, as the magic-link confirmation
   does; return the session token.

Afterwards the person can set a password or sign in with Google as usual;
Google links by e-mail address already.

### E-mails

Three new kinds in `core/src/normly_core/notifications/mail/texts.py`, German
and English, rendered with the existing base template:

- `invitation` — role, publisher name if any, validity, optional personal
  message (escaped, as its own paragraph), button to `/invitation?token=…`.
- `account_blocked` — neutral notice, contact address from
  `NORMLY_CONTACT_EMAIL` or the imprint link; no reason.
- `account_removed` — neutral notice, same contact rule.

Block and removal e-mails use the account's locale, bilingual when it is
unknown (as the deletion warning does).

### Permission matrix (`permissions.py`)

One definition per capability: key, per-role value (`yes`, `no`, `own`,
`aggregated_own`, `all`) and a `planned` flag. The admin guard and the matrix
endpoint both read it, so the dialog cannot drift from what the server
enforces. Columns: anonymous, user, publisher, administrator. Rows:

| Capability | Anonymous | User | Publisher | Administrator |
|---|---|---|---|---|
| Search and free content | yes | yes | yes | yes |
| Chat and history | no (tab only) | own | own | own |
| Chats of other users | no | no | no | no |
| Personal usage data of others | no | no | no | no |
| Usage and demand *(planned)* | no | no | own content, aggregated | all |
| Deliveries *(planned)* | no | no | own | all |
| Billing *(planned)* | no | no | own contract | all |
| User management and audit log | no | no | no | yes |

### CLI

`python -m normly_core.pipeline grant-admin --email <address>` sets the role
to `administrator` (clearing a publisher binding), writes
`administrator_granted_cli` with actor `NULL`, and fails with a clear message
if the account does not exist or is blocked. Idempotent.

### Export (ADR-027 access request)

`GET /v1/accounts/export` additionally contains role, publisher name, block
status and reason, and the audit entries whose `target_account_id` is the
account (action, time, before/after values — without `actor_account_id`).

## Frontend

### Session and sidebar

`AccountSummary` gains `role` and `publisherId`. `AppShell` renders a second
sidebar group *Administrator* with the entry *User management* (icon `Users`)
only when `role === "administrator"`.

### Routes

- `/admin/users` — the page. The middleware redirects to `/login` without a
  session cookie; a non-administrator gets 403 from the backend and sees a
  "no access" state.
- `/api/admin/*` — BFF pass-through routes, same pattern as `/api/account/*`.
- `/invitation` — accept page with states *ready*, *accepting*, *expired or
  invalid*, *blocked*, *success* (redirect to `/`).
- `/login` — shows the blocked notice with the contact address on
  `account_blocked`.

### Components (`frontend/src/components/admin/`)

| File | Content |
|---|---|
| `summary-cards.tsx` | Four cards: accounts (active in 30 days), publishers (publishers, open invitations), administrators, blocked (most frequent reason). |
| `users-toolbar.tsx` | Role tabs with counts, status dropdown, search (300 ms debounce). |
| `users-table.tsx` | shadcn `table` with a local column definition (key, header, sortable, cell renderer); all columns left-aligned; sort buttons with `aria-sort`; shadcn `pagination` with rows per page. Columns: account, first name, last name, sign-in (e-mail, Google or both), role, publisher, last sign-in, account since, status. |
| `row-actions.tsx` | Menu by status — active: edit, block, remove; blocked: edit, unblock, remove; invited/expired: resend, withdraw. On the own row, everything that would hit `self_action` is disabled. |
| `invite-dialog.tsx` | E-mail, role, publisher (shown and required only for publisher, with "+ New publisher…"), language, personal message. Hint from the check endpoint when an account exists; error when it is blocked. One short help text instead of the four process steps. |
| `edit-dialog.tsx` | Downgrade to user; change publisher. |
| `block-dialog.tsx` | Reason from the fixed list. |
| `remove-dialog.tsx` | Confirmation by typing the e-mail address. |
| `role-matrix-dialog.tsx` | "What the roles see" from `/api/admin/role-matrix`, planned rows marked. |

Filter, search, sort and page live in the URL query, so reload and the back
button work. New shadcn components: `card`, `select`, `label`,
`alert-dialog`. No new table library. All strings under `admin.*` in `de.json`
and `en.json`. Badges carry text, not only colour. On narrow screens the table
scrolls horizontally inside its container; the page itself does not.

## Testing

Backend (pytest, `accounts/tests` and `core/tests` patterns):

- Every `/v1/admin/*` endpoint: 401 anonymous, 403 for `user` and
  `publisher`; an administrator downgraded or blocked loses access on the next
  request.
- Invitation: create, replace, resend (old token invalid), withdraw; accept
  for a new address (account verified and signed in) and for an existing
  account (role changes only on accept); 410 expired; 403 blocked; a
  self-registered account with the invited address does **not** receive the
  role without the link.
- Protection rules: last administrator, own account, upgrade through PATCH,
  removal with a wrong confirmation address.
- Block: sessions deleted; password, magic link and Google refused; reset and
  magic-link requests send nothing; the chat service rejects the session.
- Audit: exactly one entry per action, no e-mail address, entries survive
  account deletion.
- List: search, filters, sort and paging across accounts and invitations;
  summary counts.
- Cleanup and export: both retention periods; export contains role and audit
  entries without the actor.
- Migration upgrade and downgrade; existing accounts become `user`.
- E-mails: the three new kinds render in German, English and bilingual.

Frontend (vitest): sidebar visibility per role; action menu per status and
the disabled own row; invitation dialog field rules; removal confirmation;
sort and filter state in the URL. Playwright end-to-end: administrator invites
a publisher → link from the test mailbox → accept → role visible in the table
→ block → sign-in refused.

## Documentation

- **ADR-030** — role model, publisher as contract partner, invitation with
  consent, immediate downgrade and block, audit log.
- **SRS** — new REQ-ACC-006 (roles and administration); REQ-ACC-004 amended
  with "role-bound administrative and partner functions"; requirement index
  in `docs/srs/README.md`.
- **ADR-017** — the exhaustive account list gains the same item. `AGENTS.md`
  only links REQ-ACC-004 and needs no change (`CLAUDE.md` no longer exists on
  `develop`).
- **ADR-027** — data inventory gains `publisher`, `account_invitation`,
  `admin_audit_log` and the two retention periods.
- **Glossary** — the three roles; *publisher (contract partner)* versus
  *publisher* as issuing body.
- `docs/reference/accounts.md` — admin API and invitation accept.
- Operations guide — `grant-admin`, `NORMLY_CONTACT_EMAIL`.

## Delivery

1. **PR 1** (`feature/60-user-management` → `develop`): migration, domain,
   repositories, admin API, sign-in changes, invitation accept, e-mails, CLI,
   cleanup, export, all documentation. Complete and testable on its own.
2. **PR 2** (follow-up branch off `develop` after PR 1 is merged): frontend
   including the end-to-end test.

## Out of scope

- Usage analytics, deliveries, billing and data sheets for publishers.
- SSO (REQ-INT-003).
- Automatic blocking by anomaly detection (REQ-SEC-004); this issue provides
  the manual block it will reuse.
- Managing publishers beyond creating them (rename, delete).
- Bulk actions, column visibility, CSV export of the table.
