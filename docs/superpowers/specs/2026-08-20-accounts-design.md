# Design: Accounts — Email/Password, Google Login and Magic Link (v1)

**Date:** 2026-08-20
**Status:** for review
**Sub-project:** fourth of several for implementing the normly MVP (free core)

## Context

The first three sub-projects (data model & reference graph schema, ingestion pipeline,
backend API) built a populated reference graph and a public read API usable
anonymously. The already approved but deferred LLM chat design
(`2026-08-20-llm-chat-design.md` — the numbering will still be adjusted if needed, see the note
there) initially provided for purely anonymous sessions. The owner wants real
account functionality from the start, not retrofitted later — this sub-project
delivers it before the chat builds on it.

REQ-ACC-004 lists exhaustively what an account is needed for: higher quotas,
saved histories, uploads, licensed content, offline use, paid
services. REQ-INT-003 requires SSO for organizations (OAuth2/SAML) as well as "email or with Google"
as further login paths. SRS section 3.3.2 additionally names MFA and magic link/OTP as
security topics. Taken together, that is too large for one sub-project.

**Decided with the owner:**

1. Scope: email/password registration (bcrypt-hashed passwords), Google OAuth login,
   and magic-link login (passwordless login via an email link; SRS 3.3.2's "conceivable" is
   implemented here). Generic organization SSO (OAuth2/SAML for arbitrary
   third-party identity providers) and MFA remain separate, later sub-projects.
2. Architecture: a separate top-level package `accounts/`, separate tables in the existing
   `core` schema. Other services (in future `chat/`, later uploads) check session tokens against
   `accounts/` instead of duplicating auth logic.
3. Session mechanics: server-side, opaque session tokens (DB lookup) — the same pattern as
   the anonymous `session_token` in the LLM chat design, revocable immediately (logout, blocking), no
   JWT.
4. Email sending (verification, password reset): an EU provider or a self-operated
   SMTP relay on STACKIT — consistent with CLAUDE.md's "No US services for operations"
   (SendGrid/Mailgun/AWS SES are US providers). The concrete provider is a later,
   swappable deployment decision behind an abstraction layer.
5. Anonymous use remains fully possible for free content (ADR-017/
   REQ-ACC-001) — this sub-project adds an option, it replaces nothing.

## Goal of this sub-project

Users can register and sign in via email/password, a Google account or a passwordless magic
link. Other
services can check a session token against an endpoint of this service and receive the
associated account identity. Password reset and email verification work
via EU/self-hosted email sending.

## Non-goals

- **Organization SSO** (REQ-INT-003, OAuth2/SAML for third-party identity providers) — a separate,
  later sub-project; separate configuration effort per organization.
- **Multi-factor authentication** (SRS 3.3.2) — a later security extension; the
  data model does not structurally block adding it later.
- **Login attempt limiting/brute-force protection** — a separate infrastructure decision, same
  rationale as the rate limiting already deferred in the previous sub-projects
  (REQ-SEC-004).
- **Quota increase for signed-in accounts, account-bound histories/bookmark lists themselves.**
  This sub-project only delivers the account foundation (registration, login, session check);
  which functions an account concretely unlocks is decided by the respective
  domain sub-projects (chat, uploads, …) that consume `accounts/`'s session check.
- **Account deletion/DSGVO (the EU General Data Protection Regulation) access request/export.** Important, but a separate topic with its own
  requirements — not specified here.

## Architecture

### Package structure

Two approaches were weighed:

1. **Separate `accounts/` directory, separate tables, separate HTTP service.**
2. Part of `api/` — rejected: breaks `api/`'s already reviewed "read-only" property
   (registration/login are write accesses), same rationale as in the LLM chat design.

**Decided: approach 1.**

```
accounts/
  pyproject.toml        # eigenes Paket, hängt von normly_core ab
  src/normly_accounts/
    main.py              # FastAPI-App, mountet /v1/accounts
    dependencies.py       # DB-Session, SMTP-Client, Google-OAuth-Client
    security.py            # Passwort-Hashing (bcrypt), Token-Erzeugung
    schemas.py               # Pydantic-Modelle
    email.py                  # EmailSender-Abstraktion + SMTP-Implementierung
    routers/
      registration.py          # Registrierung, E-Mail-Verifizierung
      login.py                   # Login, Logout, Passwort-Reset
      google.py                    # Google-OAuth-Flow
      session.py                    # Token-Validierung für andere Dienste
  tests/
```

Other services call `GET /v1/accounts/session` like an ordinary HTTP endpoint —
no direct Python import, the same dogfooding principle as planned between `chat/` and `api/`.

### Data model (new tables in the existing `core` schema)

| Table | Columns | Purpose |
|---|---|---|
| `account` | `id` (PK), `email` (unique), `password_hash` (nullable), `email_verified_at` (nullable), `created_at` | Core identity |
| `account_session` | `id` (PK), `account_id` (FK), `session_token` (unique, opaque), `created_at`, `expires_at` | Active sessions |
| `account_google_identity` | `account_id` (FK), `google_subject_id` (unique) | Link between Google account ↔ normly account |
| `account_token` | `id` (PK), `account_id` (FK), `purpose` (`password_reset`/`email_verification`/`magic_link`), `token` (unique, opaque, single-use), `created_at`, `expires_at`, `used_at` (nullable) | Single-use tokens for reset/verification/magic link |

Sessions expire 30 days after last use (`expires_at` is extended on every successful
`/session` check — a "sliding window", not a hard fixed date), so that active users
are not logged out in the middle of use, while inactive sessions do not stay valid
indefinitely.

`password_hash` is nullable — an account created exclusively via Google or magic link
has none. Registration allows immediate login without completed
email verification; `email_verified_at` records the status for later, stricter gates
(YAGNI: no blocking in this sub-project) — an account created via magic link counts
as verified immediately, since the login process itself already proves access to the email.
`account_token` covers password reset, email verification and magic link via a
`purpose` field instead of three almost identical tables; the validity period differs per
`purpose` (magic link short, 15 minutes — meant to be used immediately; reset and
verification longer, see Test concept).

Repository access follows the same pattern as everywhere in the project: Protocol in `domain.py`,
Postgres implementation in `repositories.py`, Alembic migration for the four tables.

## Endpoints (v1)

| Endpoint | Purpose |
|---|---|
| `POST /v1/accounts/register` | Email + password → create account, send verification mail, return session |
| `POST /v1/accounts/login` | Email + password → session |
| `POST /v1/accounts/logout` | Revoke session |
| `POST /v1/accounts/password-reset/request` | Email → send reset mail |
| `POST /v1/accounts/password-reset/confirm` | Token + new password → change password |
| `GET /v1/accounts/verify-email?token=` | Complete email verification |
| `GET /v1/accounts/google/login` | Redirect to Google's consent screen |
| `GET /v1/accounts/google/callback` | Process Google's response, create/link account, return session |
| `POST /v1/accounts/magic-link/request` | Email → send magic-link mail |
| `POST /v1/accounts/magic-link/confirm` | Token → create account (if new) or sign in, return session |
| `GET /v1/accounts/session` | Token validation for other services |

### Google OAuth flow

Standard authorization code flow. `google/login` redirects to Google's consent screen.
`google/callback` exchanges the received code for a Google profile (email,
`subject_id`) — creates a new account for an unknown `subject_id`, or links
`account_google_identity` to an existing account with the same email address, if
one exists. Creates a session. The redirect behavior after the callback (where the browser
is sent) is deliberately left to the frontend side — API-first, as in all
previous sub-projects.

### Magic link flow

`magic-link/request` accepts an email address and — regardless of whether
an account already exists for it — sends an `account_token` with `purpose=magic_link` by mail
(the response does not reveal whether the address is known, the same enumeration protection as for
login). If no account exists yet for this email, one is created at the `confirm` step
(symmetrical to Google's behavior) instead of a separate error — magic link is thus both
a login and a registration path. `magic-link/confirm` accepts the token as a
POST body parameter, not as a GET query parameter — deliberately, so that merely opening
the link through email-client link previews/scanners does not accidentally consume the token;
the frontend reads the token from the URL and sends it via POST.

## Error handling

| Case | Behavior |
|---|---|
| Email already registered | 409 — UX requires this information at registration |
| Login with wrong credentials | 401, generic message — no distinction between "email unknown" vs. "password wrong" (enumeration protection) |
| Expired/invalid/already used reset, verification or magic-link token | 400 |
| Google OAuth rejected/failed | 400, error state in the redirect |
| Unknown/expired `session_token` at `/session` | 401 |
| Email sending (SMTP) unreachable | 503, no detail leak; the registration/reset request itself does NOT fail — account/token are created, mail sending is caught up separately or logged (see Open items: no retry mechanism in this sub-project) |
| Database connection down | 503, no detail leak |

## Test concept

- Real PostgreSQL (Testcontainer pattern as everywhere in the project).
- Real bcrypt hashing — no mocking needed, fast enough for tests.
- **Google OAuth**: only the token exchange/profile retrieval against Google's API is
  mocked in a targeted way (one HTTP call, not our own linking/account logic) — a real
  Google test connection cannot sensibly be established in an automated suite, same
  rationale as for the DB-down test in the backend API sub-project.
- **Email sending** behind the `EmailSender` abstraction — tests use a
  test implementation that records sent mails instead of sending real mails.
- Registration → login → logout end-to-end against real session tables.
- Password reset and verification tokens: expiry, single use (`used_at`),
  invalid/expired tokens explicitly tested.
- Google account linking: a new Google account creates a new normly account; Google login with
  an address already registered via email/password links instead of duplicating.
- Magic link: `request` for unknown and known email addresses returns the same response
  (enumeration protection); `confirm` with a valid token creates a new,
  already verified account for an unknown email; `confirm` with an expired or already used token
  fails; a second `confirm` attempt with the same token after successful first
  use also fails (single use).
- `GET /v1/accounts/session`: a valid token returns `account_id`, an expired/unknown
  token returns 401 — this is the contract that future services (`chat/` and others)
  rely on.

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| REQ-ACC-004 | Delivers the account foundation on which functions requiring an account later build |
| REQ-INT-003 (subset) | Email/password and Google login; organization SSO is follow-up work |
| SRS 3.3.2 (magic link/OTP) | Passwordless login via single-use, short-lived email tokens implemented |
| ADR-017 / REQ-ACC-001 | Anonymous use remains possible unchanged — an account is an additional option, not a prerequisite |
| CLAUDE.md "No US services for operations" | Email sending via an EU/self-hosted SMTP relay instead of a US transactional email service |
| SRS 3.3.2 (password hashing) | bcrypt for `account.password_hash` |

## Open items / follow-up work

- **Organization SSO** (OAuth2/SAML for third-party identity providers) and **MFA** — separate,
  later sub-projects.
- **Login attempt limiting/brute-force protection** — a separate infrastructure decision, like the
  rate limiting already deferred in the previous sub-projects.
- **No retry mechanism for failed email sending.** If the SMTP relay is down when
  sending a verification or reset mail, this is currently only logged —
  no queue/no automatic retry. Sufficient for the start; to be added as soon as
  it becomes a real problem.
- **Account deletion, DSGVO access request/export** — a separate topic, not specified here.
- **Concrete email provider/SMTP configuration** — a later deployment decision, analogous
  to the previous sub-projects (e.g. database hosting, LLM provisioning).
- **The LLM chat design must be updated** as soon as this sub-project is in place:
  `chat_session` should then optionally be able to link a real `account_id`
  (`GET /v1/accounts/session` returns the identity); anonymous use additionally remains
  available.
