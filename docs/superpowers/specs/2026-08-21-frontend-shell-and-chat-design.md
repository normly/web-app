# Design: Frontend Shell and Chat Interface (v1)

**Date:** 2026-08-21
**Status:** approved
**Sub-project:** sixth of several for implementing the normly MVP (free core) — first of three
frontend sub-projects

## Context

Five backend services are built and merged: `core/` (library), `api/` (read-only
reference graph API), `accounts/` (registration/login/session/Google OAuth/magic link),
`chat/` (structural questions + RAG synthesis over the reference graph, session identity with
optional account linking). No user interface exists yet at all — all services have
so far been reachable exclusively via HTTP.

The overall scope "frontend" breaks down into three independent areas: chat, reference graph search/
browsing, account/profile management. Agreed with the owner: these are implemented as three
sequential sub-projects within **one** Next.js application (one shell,
several areas/routes — no separate deployment per area). This sub-project is the
first: shell plus chat interface, the case that according to SRS chapter 3.1.1 (`REQ-UI-001` to
`REQ-UI-005`) is the most precisely specified and central on the product side.

**Decided with the owner:**

1. Scope of this sub-project: Next.js shell (routing, PWA basis, theming/white-label,
   WCAG basis) **and** the chat interface according to `REQ-UI-001`–`005`, **plus** a minimal
   login entry point (email/password, magic link, Google), so that sessions can be linked to the
   account from the start. Search/browsing of the reference graph (sub-project 2) and
   profile management/account settings (sub-project 3) are separate, later sub-projects.
2. Styling: Tailwind CSS + shadcn/ui. shadcn/ui delivers components as code in the repository
   (no runtime service, no conflict with "No US services for operations" (or build)) and builds
   on Radix UI primitives, which already bring keyboard operation, ARIA attributes and focus management
   — a direct advantage for `REQ-UI-004` (WCAG 2.1 AA).
3. Backend connection: all three services (`api/`, `accounts/`, `chat/`) run in production behind
   the same reverse proxy under path prefixes — from the browser's point of view the same origin as
   the frontend. No CORS configuration needed.
4. Session token storage: httpOnly cookies instead of `localStorage`. Next.js route handlers
   (`/app/api/*`) receive login/chat responses on the server side and set the token as an
   httpOnly cookie — client-side JavaScript never sees the raw token, more robust against
   XSS token theft.
5. Push notifications: deliberately **not** part of this (or a nearby) sub-project.
   Real web push delivery in the browser standard necessarily runs via the respective
   vendor push service (Google FCM for Chrome/Android, Apple APNs for Safari/iOS) — this is
   not a choice on our side but how the web push standard technically works, and
   collides with "No US services for operations". The service
   worker needed for `REQ-MOB-001` anyway is, however, already created now (app shell caching, installability) — a later
   push handler could be added there without changing the basic structure. See Open
   items.
6. UI labeling bilingual DE/EN from the start (clarified afterwards, originally planned as
   follow-up work) — cookie-based instead of a URL prefix, see "Internationalization
   (DE/EN)" below.

## Goal of this sub-project

An installable, DE/EN-bilingual chat web interface customizable under its own configuration:
text input, answer display with loading state, source linking per answer,
several switchable chat sessions with history, WCAG 2.1 AA compliant — fully usable
without an account (`REQ-ACC-001`), with an optional login that binds the session to the account and thus
enables cross-device history.

## Non-goals

- **Reference graph search/browsing independent of the chat** (against `api/`, without an LLM) — a separate,
  directly following sub-project (no. 2).
- **Profile management/account settings** (change email, view/sign out sessions, delete
  account) — a separate, later sub-project (no. 3). `accounts/` does not yet offer any
  endpoints for this today (only registration/login/logout/password reset/Google OAuth/magic link/
  session check) — sub-project 3 presumably needs additional `accounts/` work,
  not only frontend.
- **Push notifications** — see "Decided with the owner" item 5.
- **Complete offline reading of content.** This sub-project delivers only the
  basic PWA installability (app shell caching) — chat itself necessarily needs a
  live connection to the LLM and is not offline-capable. Offline access to already retrieved
  free content (`REQ-MOB-001`'s actual offline promise) belongs to sub-project 2, where
  document content actually appears in the UI.
- **Native application** (`REQ-MOB-002`) — commercial layer, a separate, much later
  sub-project, tied to licensed offline full texts.
- **Rate limiting/quota for anonymous use** (`REQ-ACC-003`) — a separate
  infrastructure decision, as noted in several places in the backend sub-projects,
  not part of the scope here. As long as it does not exist, use in this sub-project is
  effectively unlimited.
- **Languages beyond German/English.** The UI labeling is DE/EN
  bilingual from the start (see "Internationalization (DE/EN)" below) — further languages are
  follow-up work, no general translation mechanism for arbitrary languages in this
  sub-project.

## Architecture

### Package structure

New top-level directory `frontend/`, Next.js (App Router, TypeScript), `output:
"standalone"` (matches CLAUDE.md's rule "No platform-specific primitives — everything must run in
the container behind any reverse proxy").

```
frontend/
  package.json
  next.config.ts          # output: "standalone"
  tailwind.config.ts
  public/
    manifest.webmanifest    # name, icons, theme color -- from the same configuration as theming
  src/
    app/
      layout.tsx             # skeleton, theming provider, service worker registration
      page.tsx                # main chat view ("/")
      chats/
        page.tsx                # chat history ("/chats")
      api/
        chat/route.ts            # route handler -> chat/ POST /v1/chat, sets/reads cookie
        auth/
          login/route.ts           # -> accounts/ POST /v1/accounts/login
          register/route.ts        # -> accounts/ POST /v1/accounts/register
          magic-link/
            request/route.ts        # -> accounts/ POST /v1/accounts/magic-link/request
            confirm/route.ts        # -> accounts/ POST /v1/accounts/magic-link/confirm
          google/
            login/route.ts          # -> accounts/ GET /v1/accounts/google/login (Redirect)
            callback/route.ts       # -> accounts/ GET /v1/accounts/google/callback
          session/route.ts         # -> accounts/ GET /v1/accounts/session (session check)
    components/
      chat/                    # input, message list, loading indicator, citation chip
      auth/                    # login/registration dialog
      ui/                      # shadcn/ui components (generated, in the repo)
    lib/
      config.ts                # theming/white-label configuration, read at runtime
      backend-clients.ts       # server-side fetch wrappers for accounts/ and chat/
      i18n/
        provider.tsx              # React context, reads the normly_locale cookie
        de.json
        en.json
    public/sw.ts or service-worker.ts  # app-shell caching, no push handler
  tests/
    unit/                    # Vitest + React Testing Library
    e2e/                      # Playwright, against real chat/+accounts/ processes
```

### Theming/white-label configuration

`REQ-UI-001` requires that colors, typography and logo are configurable per instance without
changing the source code. Implementation: a configuration file/environment variables
read at startup (not burned into the build, since `output: "standalone"` is meant to deliver a single
image for any number of instances — a rebuild per instance would contradict the
shipping principle from ADR-010). CSS variables (read by Tailwind) plus a logo path
are injected into the page from this configuration in `layout.tsx`.

### Internationalization (DE/EN)

The UI labeling (buttons, labels, error messages, dialog texts) is
bilingual (German/English) from the start — independent of `chat/`'s own `language` parameter, which
only controls the language in which the LLM *answers*. The two are related (the UI language
sensibly determines the initial value for `chat/`'s `language` field), but are two separate
settings: a German-language interface can still display an English chat answer
if the user explicitly chooses so in the chat (if sub-project 1 offers a dedicated
language switch for the answer language in the chat — otherwise it simply follows the
UI language).

**No URL prefix** (`/de/...`, `/en/...`) — the language is a cookie value
(`normly_locale`), not a route. This fits the existing cookie-based pattern
(session token) and avoids duplicate routes for an app that mostly runs behind
cookie/login state. A switch in the header changes the language without a
page reload; without a cookie set, the `Accept-Language` header of the first
request determines the initial value (fallback German if it cannot be assigned unambiguously).

Translations exist as simple key-value dictionaries (`lib/i18n/de.json`,
`lib/i18n/en.json`), read via a React context provider in `layout.tsx` — for two
languages and pure UI chrome text (no complex pluralization/number formatting
foreseeable), a heavyweight i18n library (e.g. `next-intl` with
locale-routing middleware) is not needed and would mainly introduce routing complexity that
is not needed here (see "Decided with the owner" on doing without
URL prefixes). Every new UI component routes its strings through this provider, never as a
hard-coded string — tests (component tests) cover that both language dictionaries are complete for
the same component (no missing key in either of the two languages).

### Backend connection as a BFF (backend for frontend)

No direct client-side call of `accounts/`/`chat/`. Instead: Next.js route
handlers under `/app/api/*` receive the request from the browser, pass it on server-side
to the respective backend service (via an internal network call, addressed via
environment variables such as `NORMLY_ACCOUNTS_BASE_URL`/`NORMLY_CHAT_BASE_URL` — the same pattern
as `chat/`'s own connection to `api/`/`accounts/`), and translate the response into an
httpOnly cookie (`normly_session` for the anonymous `chat_session`, `normly_account_session` for
the account session — separate, since a `chat_session` also exists without an account). Follow-up requests
read the cookie server-side from the request and attach it as `session_token`/
`Authorization` header to the backend call — the browser never handles a raw token.

In production, `frontend/`, `api/`, `accounts/`, `chat/` sit behind a shared reverse
proxy under path prefixes — the same origin as the frontend, no CORS configuration needed.
In development/in tests, resolution instead goes directly against the respective service
addresses.

### Page and component structure

- **`/` — main chat view.** Text input (submit via button or Enter, `REQ-UI-002`),
  message history with role distinction (user/assistant), a visual loading indicator
  while the answer is awaited, per answer one or more citation chips with a link to the
  original source location (free) or the publisher's point of purchase (paid, `REQ-UI-003`).
- **`/chats` — chat history (`REQ-UI-005`).** List of past sessions, sorted by
  creation date, a click reopens the session (continuation in the `/` chat with
  the history loaded). Visible/usable only for signed-in accounts — a purely anonymous,
  device-side session has no "list" retrievable across devices, only the one running
  session in the cookie. This matches `chat/`'s design (`account_id` linking is a
  prerequisite for "viewing several sessions") and is no contradiction to `REQ-ACC-001`,
  since chat itself remains fully usable without an account — only the history overview across
  several sessions requires an account.
- **Login/registration dialog** (modal, not a page of its own) — reachable via a
  header button, chat remains fully usable before and after. Tabs/switch for
  email+password login, registration, magic link request, "Sign in with Google" button.

## Data flow

**Chat cycle:**
```
User sends a message
-> POST /app/api/chat (Next.js Route Handler)
   reads the normly_session cookie (if present) and the normly_account_session cookie
   (if present, as an Authorization: Bearer header)
-> POST {CHAT_BASE_URL}/v1/chat with {session_token, jurisdiction, language, message}
   + optional Authorization header
<- response: {session_token, answer, answer_type, citations}
   route handler sets/updates the normly_session cookie from the response
-> response to the UI: show the message, resolve citations to links
   (one read call per citation against GET {API_BASE_URL}/v1/documents/{id} -- provides
   publisher/point of purchase for REQ-UI-003's linking)
```

**Login cycle (email/password, analogous for magic link):**
```
User submits the login form
-> POST /app/api/auth/login -> POST {ACCOUNTS_BASE_URL}/v1/accounts/login
<- {session_token, account} or 401 (generic, no enumeration leak)
   route handler sets the normly_account_session cookie
-> the next chat request attaches this token as an Authorization header
   chat/ links the running chat_session to the account (see the chat/ design,
   "Session identity and account linking") -- the previous history is kept
```

**Google OAuth cycle:** The browser is redirected directly (not via the route handler) to
`/app/api/auth/google/login`, which forwards by redirect to
`accounts/`'s own `GET /v1/accounts/google/login` (which in turn redirects to Google);
the way back lands on `/app/api/auth/google/callback`, which receives the `accounts/` response,
sets the cookie and redirects back to the chat view.

## Error handling

| Case | Behavior |
|---|---|
| `chat/` unreachable (503) | Route handler passes 503 through; UI shows an error message with a retry option, no silent loading hang |
| Login/registration with invalid data (400/401) | Error message from the generic `accounts/` response directly in the dialog, no technical details |
| Session cookie expired/unknown during a chat | No error state — the next request simply gets a new anonymous session from `chat/`, matches `chat/`'s own behavior |
| Citation resolution (document fetch for the link) fails | The answer is still displayed, only without a clickable source link — degradation, not a blocker |
| Google OAuth declined/failed | `accounts/`'s own 400 response is displayed in the dialog as a generic error message |

## Test concept

- **Component tests** (Vitest + React Testing Library): chat interaction (input, sending,
  loading state, display), login dialog (all four paths), citation linking — against mocked
  route handler responses, fast and isolated.
- **End-to-end test** (Playwright), consistent with the test philosophy established in the backend sub-projects
  (real services instead of mocks where practicable): full cycle — ask a
  question, see the answer incl. source link, optionally sign in, leave the session and continue it via
  `/chats` — against real, actually running `chat/` and `accounts/` processes (analogous to
  `chat/`'s own `test_structural_end_to_end.py` pattern: no Ollama needed for the
  login/history part of the test, a separate, Ollama-gated test covers the real
  synthesis answer path where available).
- **WCAG conformance** (`REQ-UI-004`): automated check via `axe-core` in the
  Playwright run, plus a manual keyboard/screen reader spot check before completion of the
  sub-project.
- **PWA installability**: manual test — manifest and service worker lead to a
  valid Lighthouse PWA score or actual installability in a Chromium browser.
- **Dictionary completeness** (DE/EN): one component test per dictionary checks that
  `de.json` and `en.json` contain exactly the same set of keys — prevents a
  language switch that leaves individual strings untranslated.

## Relation to requirements and ADRs

| Requirement/ADR | Coverage in this design |
|---|---|
| `REQ-UI-001` | Standalone chat interface, theming/logo via runtime configuration, runs without external dependencies |
| `REQ-UI-002` | Text input with Enter/button, loading indicator, complete question-answer cycle |
| `REQ-UI-003` | Citation chips per answer, linking to the original source location or point of purchase |
| `REQ-UI-004` | Tailwind + shadcn/ui (Radix basis) as the structural foundation, `axe-core` check in the E2E test |
| `REQ-UI-005` | `/chats` history, sorting by date, continuability, performant even with many sessions (pagination if needed — see Open items) |
| `REQ-ACC-001` | Chat fully usable without an account; login is an optional addition, not a prerequisite |
| `REQ-ACC-004` | "saved histories" is explicitly on the exhaustive list of functions requiring an account — restricting `/chats` to signed-in accounts is thus spec-compliant, not mere interpretation |
| `REQ-MOB-001` | Web app manifest + service worker for app shell caching, installability |
| `REQ-MOB-003` | Offline/caching access exclusively via the service worker as the abstraction layer, no scattered direct storage accesses in the application logic |
| ADR-010 (shipping) | `output: "standalone"`, one image for any number of instances, theming at runtime instead of in the build |
| CLAUDE.md "multilingualism planned" | DE/EN UI labeling from the start, see "Internationalization (DE/EN)" — brought forward instead of being treated as follow-up work |

## Open items / follow-up work

- **Push notifications** — see "Decided with the owner" item 5. The
  conflict of goals with "No US services" remains unresolved and would, if needed, have to be weighed deliberately with the
  owner (e.g. as an explicitly documented exception), not silently
  worked around.
- **Reference graph search/browsing** (sub-project 2) and **profile management** (sub-project 3,
  presumably needs new `accounts/` endpoints) — both separate, subsequent sub-projects.
- **Rate limiting/quota for anonymous use** (`REQ-ACC-003`) — not yet built, neither
  here nor in the backend; the chat interface currently shows no quota display because there is
  no quota counting.
- **Pagination of the chat history** — `REQ-UI-005` requires performant usability even with
  many sessions; the concrete pagination/loading strategy is not specified in detail
  here and will be made concrete in the implementation plan.
- **Languages beyond DE/EN** — the dictionary pattern is extensible to further languages,
  but not part of this sub-project.
