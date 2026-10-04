# normly frontend

Next.js App Router shell and chat UI (`standalone` output, installable PWA).
For the full design rationale see
`docs/superpowers/specs/2026-08-21-frontend-shell-and-chat-design.md`.

## Environment variables

When running via the repository's `compose.yaml`, the three `*_BASE_URL`
variables are set by Compose to the internal service names; only the
optional branding variables and `NORMLY_PUBLIC_BASE_URL` come from `.env`.

All variables are read at request time via `process.env` (not
`NEXT_PUBLIC_*`), so one built image can serve any number of differently
configured instances without a rebuild (ADR-010).

| Variable | Required | Default | Read by | Purpose |
|---|---|---|---|---|
| `NORMLY_API_BASE_URL` | yes | — (throws if unset) | `src/lib/backend-urls.ts` | Base URL of the `api/` service (document/citation lookups). |
| `NORMLY_ACCOUNTS_BASE_URL` | yes | — (throws if unset) | `src/lib/backend-urls.ts` | Base URL of the `accounts/` service (login, register, session, logout, Google OAuth). |
| `NORMLY_CHAT_BASE_URL` | yes | — (throws if unset) | `src/lib/backend-urls.ts` | Base URL of the `chat/` service. |
| `NORMLY_INSTANCE_NAME` | no | `"normly"` | `src/lib/config.ts` | Instance name shown in the header and page title. |
| `NORMLY_BRAND_COLOR_HSL` | no | `"222 89% 55%"` | `src/lib/config.ts` | Brand color, HSL triple without the `hsl()` wrapper (matches Tailwind's `hsl(var(--brand) / <alpha-value>)`). |
| `NORMLY_LOGO_PATH` | no | `null` (no logo, name only) | `src/lib/config.ts` | Path/URL to an instance logo, rendered in the header in place of the plain name. |

The three `*_BASE_URL` variables are validated lazily, per property: a route
that only ever calls `getBackendUrls().accounts` (e.g. `/api/auth/login`)
only requires `NORMLY_ACCOUNTS_BASE_URL` to be set, not all three.

## Deployment note: Google OAuth redirect URI

`accounts/`'s Google OAuth callback (`accounts/src/normly_accounts/routers/
google.py`) reads its own `NORMLY_GOOGLE_REDIRECT_URI`, defaulting to
`http://localhost:8000/v1/accounts/google/callback` (`accounts/`'s own
callback endpoint) if unset.

This is a separate setting, in `accounts/`'s deployment config -- not this
frontend's. It **must** be set to this frontend's own public URL plus
`/api/auth/google/callback` (e.g. `https://app.example.de/api/auth/google/
callback`), so that Google redirects the browser back through this
frontend's Route Handler, which sets the session token as an `httpOnly`
cookie (see `src/lib/session-cookies.ts`).

If `NORMLY_GOOGLE_REDIRECT_URI` is left at its default, or misconfigured to
point at `accounts/`'s own callback endpoint instead, Google redirects the
browser straight to `accounts/` after login. `accounts/`'s callback returns
the session token directly in a JSON response body, not a cookie -- silently
defeating this app's BFF token-confinement design for that one login path
(the token would be exposed to page JavaScript/history instead of staying
`httpOnly`).
