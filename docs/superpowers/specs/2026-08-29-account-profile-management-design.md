# Profile management — Design

Sub-project 3 of the frontend, the last of the three planned sub-projects. Sub-project 1
(app shell + chat) and sub-project 2 (reference graph search/browsing) are
complete and merged into `main`. This document describes account/
profile management: changing the email address, setting/changing the password, viewing and
revoking sessions, data export, account deletion.

## Decided with the owner

1. **Scope of functions:** change email, view/revoke sessions, delete account
   (the three items originally sketched in sub-project 1's spec), plus setting/changing
   the password (closes a gap that was found — `accounts/` already supports
   password reset, but the frontend has no connection for it yet), plus
   data export under Art. 20 GDPR (DSGVO) (not explicitly required by any requirement, but
   appropriate for an account with personal data).
2. **Account deletion:** hard delete — the account AND all linked data
   (chat sessions/messages) are removed, not just the account link set to
   `NULL`. This implements the GDPR right to erasure most consistently.
3. **Data export scope:** account master data (email, creation date, linked
   Google identity) plus the complete chat history (all of the user's own sessions with
   messages) — covers the personal data actually stored.
4. **Avatar image:** stored directly in Postgres as `bytea`, not via
   STACKIT Object Storage — the latter does not exist anywhere in the project yet; even
   the ingestion pipeline deliberately defers that connection to a later
   deployment decision; the avatar image should not preempt this architecture decision.
   Resized server-side to 256×256, no new
   dependency needed (`Pillow` already comes with `core/`). No dedicated
   retrieval endpoint — part of the existing `AccountResponse` as a Base64 data URL.
5. **First/last name:** optional, entered only afterwards via `/account`
   — **not** part of registration, so as not to touch REQ-ACC-001's principle of
   low registration hurdles and to leave the already merged
   registration form from sub-project 1 unchanged. Serves primarily
   the initials placeholder display when no avatar image is set.

## Architecture

Ten new `accounts/` endpoints (all authenticated via `Authorization: Bearer
<session-token>`) plus a new frontend page `/account` following the same
BFF pattern as the previous sub-projects — no direct client access to
`accounts/`.

### Backend (`accounts/`)

**Email change** — two-step, reuses the existing
verification mechanism (`AccountToken`/`EmailSender`):

- `POST /v1/accounts/email/change` (authenticated, `{new_email: str}`) — creates
  an `AccountToken` with the new purpose `AccountTokenPurpose.EMAIL_CHANGE`,
  uses the token's already existing `email` field for the new address (no
  schema change needed), sends the confirmation link to the **new** address.
  If `new_email` is already assigned to another account: 409 (authenticated
  action, no enumeration risk as with anonymous registration).
- `GET /v1/accounts/email/confirm?token=` — on click: `Account.email` is switched
  only now, token marked as consumed (`consume_token`). Analogous to the
  existing `verify-email` pattern.
- **Why two-step:** prevents silent account takeover with a compromised
  session (an attacker with a stolen token could otherwise immediately switch the email to
  an address of their own and lock out the real owner) and catches
  typos in the new address before they take effect.

**Set/change password:**

- `POST /v1/accounts/password` (authenticated, `{current_password: str | None,
  new_password: str}`) — if a `password_hash` already exists,
  `current_password` is checked against `verify_password` (401 if missing or
  wrong); for passwordless accounts (first sign-in via Google or magic link,
  `password_hash IS NULL`) the check is skipped, since the valid session itself
  already proves the identity and nothing exists to compare against. Uses
  `hash_password`/`set_password_hash`, the same already existing building blocks as
  the password reset flow.

**Sessions:**

- New repository method `list_sessions_for_account(account_id) ->
  list[AccountSession]` (not present so far — only `get_session_by_token`
  exists).
- New repository method `revoke_session_by_id(session_id, account_id) -> bool`
  (instead of the existing token-based `revoke_session`) — checks server-side
  that the session really belongs to the calling account before it is removed;
  prevents guessing other accounts' session IDs.
- `GET /v1/accounts/sessions` → `[{id, created_at, expires_at, is_current: bool}]`
  — `is_current` by comparing the session ID with the bearer token currently in use,
  so that the UI can label "This device".
- `DELETE /v1/accounts/sessions/{session_id}` — signs out another session; if
  the user's own active session is affected, the response reports this explicitly so that the
  frontend also deletes the local cookie (otherwise the browser would be left with a
  token that is already invalid server-side).

**Account deletion:**

- `DELETE /v1/accounts/me` (authenticated, `{password: str | None}` for confirmation if a
  password exists; for passwordless accounts the frontend instead checks
  that the user has typed her own email address exactly into a
  confirmation field before the request is even sent —
  server-side no additional check is needed for passwordless accounts, since
  the valid session already proves the identity) — new repository method
  `delete_account(account_id)` deletes explicitly
  in dependency order: `chat_message_citation` → `chat_message` →
  `chat_session` → `account_token`/`account_session`/`account_google_identity` →
  `account`. The existing foreign key relationship on `chat_session.account_id`
  is presumably `SET NULL` (matching the anonymous-session behavior) rather than
  `CASCADE` — checked during implementation; if so, the
  repository method takes over the deletion order explicitly instead of relying on
  database cascade.

**Name and avatar image:**

- New `Account` columns: `first_name: str | None`, `last_name: str | None`,
  `avatar_image: bytes | None`, `avatar_content_type: str | None`.
- `AccountResponse` extended by `first_name`, `last_name`,
  `avatar_data_url: str | None` (Base64 data URL, e.g.
  `data:image/jpeg;base64,...`, `None` if no image is set).
- `PATCH /v1/accounts/profile` (authenticated, `{first_name: str | None,
  last_name: str | None}`) — both fields optional and clearable independently of
  each other (submitted empty = reset to `None`).
- `POST /v1/accounts/avatar` (authenticated, multipart upload, upper limit
  5 MB before resizing) — validates the format (JPEG/PNG/WebP), resizes
  with `Pillow` to 256×256, stores `avatar_image` + `avatar_content_type`.
- `DELETE /v1/accounts/avatar` — resets both columns to `None`.
- **Initials placeholder logic** (frontend-side, derived from the already existing
  fields, no server rendering needed): if `first_name`/
  `last_name` are set, the first letters of both fields; if only one is set,
  its first letter; if none is set, the first letter of the
  email address.

**Export:**

- `GET /v1/accounts/export` (authenticated) → JSON:
  ```json
  {
    "account": {
      "email": "...", "created_at": "...", "email_verified": true,
      "google_linked": false, "first_name": "...", "last_name": "...",
      "avatar_data_url": "..."
    },
    "chat_sessions": [
      {
        "session_token": "...", "jurisdiction": "DE", "language": "de",
        "created_at": "...",
        "messages": [
          {"role": "user", "content": "...", "created_at": "..."},
          {
            "role": "assistant", "content": "...", "created_at": "...",
            "citations": [{"document_id": "...", "segment_id": null}]
          }
        ]
      }
    ]
  }
  ```
  No need for pagination in the first iteration (YAGNI) — noted as an open
  item in case usage with very long histories makes it relevant.

### Frontend

**New page `/account`** (server/client split pattern like `/search` and
`/documents/[id]`): sections for name (first/last name, optional) and
avatar image (upload with preview + "Remove" button), change email, set/change
password, active sessions (list with "This device" label and
sign-out button per row), data export (download button), account deletion (with
confirmation). `AppHeader`'s plain-text email display so far is linked to `/account`
and additionally shows the avatar image or the initials placeholder.

**Password reset connection** (the gap that was found — `accounts/` already supports it,
the frontend so far does not): no separate tab in `AuthDialog`, but rather
a "Forgot password?" link in `LoginForm` that switches to a
request/confirmation view — matches the usual position of this
flow and avoids an additional, rarely used tab.

**New BFF route handlers** (same proxy pattern, correctly encoded from the
start — after the path traversal fix found in sub-project 1, this is built
cleanly from the beginning): `POST /api/account/email`, `GET /api/account/email/confirm`,
`POST /api/account/password`, `PATCH /api/account/profile`,
`POST /api/account/avatar`, `DELETE /api/account/avatar`,
`GET /api/account/sessions`, `DELETE /api/account/sessions/[id]`,
`DELETE /api/account`, `GET /api/account/export`,
`POST /api/auth/password-reset/request`, `POST /api/auth/password-reset/confirm`.

**i18n:** new `account` namespace for all labels/error messages of
this page, plus additions to the existing `auth` namespace for the
forgot-password flow.

## Data flow

**Email change cycle:**
```
/account → POST /api/account/email {new_email}
  → accounts/ creates AccountToken(purpose=EMAIL_CHANGE, email=new_email), sends mail
User clicks the link → GET /api/account/email/confirm?token=
  → Account.email is switched, token consumed
```

**Session sign-out cycle:**
```
/account → GET /api/account/sessions → list, each entry labeled with is_current
Click "Abmelden" on a row → DELETE /api/account/sessions/{id}
  → if is_current: the frontend also deletes the local normly_account_session cookie
```

## Error handling

| Case | Behavior |
|---|---|
| New email already taken | 409, clear error message |
| Current password wrong (change/delete) | 401, generic error message |
| Session not found/someone else's | 404 |
| Export with a very long history | No need for pagination in the first iteration; open item |
| Avatar upload too large / wrong format | 400, clear error message with the allowed formats and upper limit |

## Test concept

- **`accounts/`:** pytest per new endpoint and new repository method —
  in particular a cascade deletion test that actually checks that
  chat messages/citations are deleted too, not just the account itself; a
  test confirming that session X cannot be signed out by account Y
  (someone else's session ID); tests for the avatar upload (file too large, wrong
  format, successful resize to 256×256) and for independently
  resetting first/last name.
- **`frontend/`:** BFF route and component tests following the established pattern,
  Playwright extension with email change and account deletion as an
  end-to-end flow.

## Relation to requirements and ADRs

| Requirement/ADR | Relation |
|---|---|
| REQ-ACC-004 (functions requiring an account) | Makes "saved histories" viewable, exportable and deletable for the first time, not just storable — the same exhaustive list, no new account requirement |
| ADR-017 (anonymous use without an account requirement) | Justified among other things by "Without an account, no personal data arises that would have to be protected" — with an account, this sub-project delivers exactly this protection (access, erasure, portability) after the fact |
| CLAUDE.md "Everything persisted is encrypted" | Account deletion removes the data completely, not just a reference to it |

## Open items

- Multi-factor authentication — named as an outlook in SRS section 3.3.2,
  not built here.
- No rate limiting on the new `accounts/` endpoints — fits the
  current state (`accounts/` currently has no rate limiting at all, unlike
  `api/` since sub-project 2); a separate future topic, if relevant.
- No export pagination for very long chat histories.
- No audit log for account deletions or email changes.
