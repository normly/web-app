# Frontend Auth-Seiten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the anonymous-page `AuthDialog` modal (login/register/magic-link tabs in one dialog) with five real, full-page routes — `/login`, `/signup`, `/magic-link`, `/reset-password`, `/verify-email` — reusing the existing `LoginForm`/`RegisterForm`/`MagicLinkForm`/`ResetPasswordContent` logic components completely unchanged, and add the two small pieces of real functionality the current backend is missing to make two of these pages actually reachable from the emails that are supposed to link to them.

**Architecture:** Four of the five pages (`/login`, `/magic-link`, `/reset-password`, `/verify-email`) share one new `AuthSplitLayout` component (photo on the right, form on the left, full viewport height, no app chrome) built once in Task 3 and reused as-is by Tasks 5-7. `/signup` uses a different, centered-card layout (per the spec's own block choice) built directly in its own task. None of the five pages render `AppHeader`/`AppShell` — they're deliberately standalone, matching the reference blocks' own full-screen intent. Every form's actual submit logic stays in the existing `LoginForm`/`RegisterForm`/`MagicLinkForm`/`ResetPasswordContent` components, untouched — pages only supply the new visual shell and an `onSuccess` callback that navigates home instead of closing a dialog.

**Tech Stack:** No new frontend dependencies (the shadcnblocks reference blocks for `magic-link2`/`reset-password2`/`verify-email2` pull in `react-hook-form`+`zod`+a `field` primitive this codebase has never used — treated as layout-reference-only, same as `ai-chat-v2`/`settings-profile4` in earlier plans, not adopted). Backend: existing FastAPI/SQLAlchemy patterns already used by `password_reset.py`/`email_change.py`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`
  — this plan implements only the "### Auth-Seiten" section (lines
  144-170). It does NOT touch `AppShell`'s Chat/Suche nav, `PageHeader`,
  the chat page, the profile overlay, or Suche/Dokument-Detail.
- **Two small, deliberate backend touches, decided with the user up front
  — not scope creep, both confirmed explicitly:**
  1. `magic_link.py`'s and `registration.py`'s verification emails
     currently send a bare `f"...: token={token.token}"` string with no
     URL at all — unlike `password_reset.py`/`email_change.py`, which
     already build a real link via `NORMLY_PUBLIC_BASE_URL`. Without a
     fix, the two new pages this plan builds for those flows
     (`/magic-link`, `/verify-email`) would be unreachable from the
     actual email a real user receives. Task 1 fixes both emails to use
     the exact same `_public_base_url()` pattern the other two routers
     already use — no new endpoint, no auth-flow change, just a
     consistent link in an existing email.
  2. There is no backend endpoint to resend a verification email at all.
     The spec's own text for `/verify-email` describes a "resend" option
     on an invalid/expired link, which cannot exist without one. Task 1
     adds `POST /v1/accounts/verify-email/resend` (email in, generic
     enumeration-safe response out), mirroring `password-reset/request`'s
     existing shape exactly. This is the one place this plan's own
     Global Constraints allow "keine neuen Backend-Endpunkte" to bend —
     confirmed with the user, who chose to build the endpoint rather
     than ship a resend button with nothing behind it.
- **No new frontend form logic.** `LoginForm`, `RegisterForm`,
  `MagicLinkForm`, `ResetPasswordContent`'s inner form (all already
  built, already calling the existing BFF routes) keep their exact
  current internals — only their `onSuccess` callback's *behavior*
  changes (navigate home instead of closing a dialog), and only their
  *visual container* changes (a new page shell instead of
  `AuthDialog`/`DialogContent`). Do not rewrite their fetch calls, their
  state, or their validation.
- **No instance branding/logo on these pages.** Unlike `AppShell`'s
  sidebar (which shows the real `instanceName`/`logoPath`), the spec's
  own text for this section says nothing about branding elements on the
  auth pages, and the reference blocks' own logos are generic
  shadcnblocks demo marks, not something to adopt. Keep these five pages
  logo-free and chrome-free — an intentional simplification, not an
  oversight.
- **One shared decorative photo, hotlinked from shadcnblocks' own CDN**,
  reused across all four split-layout pages (`https://deifkwefumgah.cloudfront.net/shadcnblocks/image-set/placeholder/images/6-3x4.jpg`)
  — this app has no real photography of its own for these pages, and the
  spec explicitly calls for "Split mit Foto" layouts; treated the same
  way Plan 2 accepted a hotlinked demo logo for `application-shell2` as
  an interim, decorative-only asset. `alt=""` on the image (purely
  decorative, conveys nothing).
- **`/reset-password` REPLACES the existing route folder's page shell
  only** — `reset-password-content.tsx`'s own internals (token handling,
  the confirm-password fetch call) are untouched by this plan; only
  `page.tsx` changes, from `AppHeader` + plain `<main>` to the new
  `AuthSplitLayout`.
- **`AuthDialog` retires completely** once all five pages exist — Task 8
  removes it and repoints its two call sites (`AppShell`'s anonymous
  `NavUser` footer, `AppHeader`'s anonymous state) to
  `<Link href="/login">` instead. Check BOTH call sites — an earlier
  plan in this redesign shipped a dead link because only one of two
  `AppHeader`/`AppShell` call sites was updated when a similar retirement
  happened; do not repeat that.
- Every new/modified hand-written source file (frontend AND backend)
  keeps its existing license header convention: frontend files keep
  `SPDX-License-Identifier: AGPL-3.0-or-later` + `Copyright (C) 2026
  normly contributors`; backend Python files use the same two lines as
  `#`-comments (see any file in `accounts/src/normly_accounts/routers/`
  for the exact form).
- Every commit needs `git commit -s` (DCO `Signed-off-by: normly
  <anonymous-jw@pm.me>`) plus a separate `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` trailer for AI-executed work — never a second
  `Signed-off-by` line.
- No direct push to `main` — branch + PR against the `stackit` remote.
  **Ask the user for explicit confirmation before pushing the branch,
  opening the PR, or asking them to merge it** — each triggers a billed
  STACKIT CI run, and the user has asked to be asked every time.
- Tests: frontend Vitest unit tests in `frontend/tests/unit/*.test.tsx`
  (`npm test` from `frontend/`); backend pytest tests in
  `accounts/tests/*.py` (`cd accounts && .venv/bin/pytest` — the venv
  already exists on disk from earlier sessions, `postgresql+psycopg://`
  scheme, see project memory for exact invocation if `pytest` isn't on
  `PATH`). Playwright e2e stays out of scope for this plan's automated
  checks (same exclusion as Plans 1-4); retiring `AuthDialog` and
  `/reset-password`'s old shell likely affects existing e2e specs that
  interact with the login modal or that route — flag as a manual
  follow-up in the PR description, same pattern as `/chats`/`/account`'s
  retirement in earlier plans.
- Branch: create `frontend/auth-pages` off latest `main` (Plans 1-4 are
  merged; this plan only needs Plan 1, but branching off current `main`
  picks up everything already merged, which is fine).

---

### Task 1: Backend — real links in two emails, a resend endpoint

**Files:**
- Modify: `accounts/src/normly_accounts/routers/magic_link.py`
- Modify: `accounts/src/normly_accounts/routers/registration.py`
- Modify: `accounts/src/normly_accounts/routers/email_verification.py`
- Modify: `accounts/src/normly_accounts/schemas.py`
- Modify: `accounts/tests/test_magic_link.py`
- Modify: `accounts/tests/test_registration.py`
- Modify: `accounts/tests/test_email_verification.py`

**Interfaces:**
- Consumes: the existing `EmailSender`/`get_email_sender` dependency
  pattern, `PostgresAccountTokenRepository`/`PostgresAccountRepository`,
  `AccountTokenPurpose.EMAIL_VERIFICATION`/`.MAGIC_LINK` — all unchanged.
- Produces: `POST /v1/accounts/verify-email/resend` (new endpoint, body
  `{"email": "..."}`, always returns
  `{"status": "if_the_account_exists_and_is_unverified_an_email_was_sent"}`)
  — Task 2's new frontend BFF route calls this. `magic_link.py`'s and
  `registration.py`'s emails now contain real
  `{base_url}/magic-link?token=...` /
  `{base_url}/verify-email?token=...` links — Tasks 5 and 7's pages
  consume these query params exactly as `/reset-password` already does
  today.

- [ ] **Step 1: Write the failing test for the magic-link email's real link**

Add to `accounts/tests/test_magic_link.py` (check the file's existing
imports for `re` — add `import re` at the top if not already present,
matching `test_password_reset.py`'s own import):

```python
def test_magic_link_email_body_contains_an_absolute_link(client, email_sender):
    client.post("/v1/accounts/magic-link/request", json={"email": "linktest@example.de"})

    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    assert body.startswith(
        "Zum Anmelden: http://localhost:3000/magic-link?token="
    )
    assert match.group(1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd accounts && .venv/bin/pytest tests/test_magic_link.py -k contains_an_absolute_link -v`
Expected: FAIL — current body is `f"Zum Anmelden: token={token.token}"`, no
URL prefix.

- [ ] **Step 3: Fix `magic_link.py`'s email body**

In `accounts/src/normly_accounts/routers/magic_link.py`, add near the top
(after the existing imports, mirroring `password_reset.py`'s exact
helper):

```python
import os
```

(add to the existing `from datetime import ...` import line's neighbors —
check `import logging` is already there; add `import os` as its own line
right after it, matching import-ordering already used in
`password_reset.py`)

then add this function right after the module-level constants (after
`_MAGIC_LINK_TOKEN_LIFETIME = timedelta(minutes=15)`):

```python
def _public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")
```

then change the email body inside `request_magic_link`:

```python
            body=f"Zum Anmelden: token={token.token}",
```

to:

```python
            body=f"Zum Anmelden: {_public_base_url()}/magic-link?token={token.token}",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd accounts && .venv/bin/pytest tests/test_magic_link.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Write the failing test for the verification email's real link**

Add to `accounts/tests/test_registration.py` (add `import re` at the top
if not already present):

```python
def test_register_verification_email_contains_an_absolute_link(client, email_sender):
    client.post(
        "/v1/accounts/register",
        json={"email": "verifylink@example.de", "password": "correct horse battery staple"},
    )

    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    assert body.startswith(
        "Bitte bestätige deine E-Mail-Adresse: http://localhost:3000/verify-email?token="
    )
    assert match.group(1)
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd accounts && .venv/bin/pytest tests/test_registration.py -k contains_an_absolute_link -v`
Expected: FAIL.

- [ ] **Step 7: Fix `registration.py`'s email body**

In `accounts/src/normly_accounts/routers/registration.py`, add `import os`
near the top (alongside the existing `import logging`), and add the same
helper function after `_VERIFICATION_TOKEN_LIFETIME = timedelta(hours=48)`:

```python
def _public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")
```

Change:

```python
            body=f"Bitte bestätige deine E-Mail-Adresse: token={token.token}",
```

to:

```python
            body=(
                f"Bitte bestätige deine E-Mail-Adresse: "
                f"{_public_base_url()}/verify-email?token={token.token}"
            ),
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd accounts && .venv/bin/pytest tests/test_registration.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 9: Add the resend-verification request schema**

In `accounts/src/normly_accounts/schemas.py`, add near
`PasswordResetRequestRequest` (same file, any position — Python doesn't
care about declaration order across independent classes):

```python
class VerifyEmailResendRequest(BaseModel):
    email: EmailStr
```

- [ ] **Step 10: Write the failing tests for the resend endpoint**

Add to `accounts/tests/test_email_verification.py`:

```python
import re


def test_resend_verification_email_sends_a_new_token_for_an_unverified_account(
    client, email_sender, db_session,
):
    _register(client, "resend@example.de", "correct horse battery staple")
    email_sender.sent.clear()

    response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "resend@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 1
    body = email_sender.sent[0]["body"]
    match = re.search(r"token=([^&\s]+)", body)
    assert match is not None
    new_token = match.group(1)

    verify_response = client.get("/v1/accounts/verify-email", params={"token": new_token})
    assert verify_response.status_code == 200


def test_resend_verification_email_is_silent_for_an_already_verified_account(
    client, email_sender, db_session,
):
    _register(client, "already-verified@example.de", "correct horse battery staple")
    token = _verification_token(db_session, "already-verified@example.de")
    client.get("/v1/accounts/verify-email", params={"token": token})
    email_sender.sent.clear()

    response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "already-verified@example.de"}
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 0


def test_resend_verification_email_returns_the_same_response_for_an_unknown_address(client):
    known_response = client.post(
        "/v1/accounts/verify-email/resend", json={"email": "unknown@example.de"}
    )

    assert known_response.status_code == 200
    assert known_response.json() == {
        "status": "if_the_account_exists_and_is_unverified_an_email_was_sent"
    }
```

- [ ] **Step 11: Run them to verify they fail**

Run: `cd accounts && .venv/bin/pytest tests/test_email_verification.py -v`
Expected: FAIL — no `/v1/accounts/verify-email/resend` route exists yet
(404 on all three new tests).

- [ ] **Step 12: Implement the resend endpoint**

In `accounts/src/normly_accounts/routers/email_verification.py`, replace
the entire file content:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_email_sender, get_session
from normly_accounts.email import EmailSender
from normly_accounts.schemas import VerifyEmailResendRequest
from normly_accounts.security import generate_token

email_verification_router = APIRouter(prefix="/v1/accounts", tags=["email-verification"])

_VERIFICATION_TOKEN_LIFETIME = timedelta(hours=48)


def _public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")


@email_verification_router.get("/verify-email")
def verify_email(token: str, session: Session = Depends(get_session)) -> dict:
    consumed = PostgresAccountTokenRepository(session).consume_token(
        token, AccountTokenPurpose.EMAIL_VERIFICATION
    )
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    PostgresAccountRepository(session).mark_email_verified(
        consumed.account_id, datetime.now(timezone.utc)
    )
    return {"status": "email_verified"}


@email_verification_router.post("/verify-email/resend")
def resend_verification_email(
    payload: VerifyEmailResendRequest, session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account = PostgresAccountRepository(session).get_account_by_email(payload.email)
    if account is not None and account.email_verified_at is None:
        now = datetime.now(timezone.utc)
        token = PostgresAccountTokenRepository(session).create_token(
            account_id=account.id, purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
            token=generate_token(), created_at=now, expires_at=now + _VERIFICATION_TOKEN_LIFETIME,
        )
        try:
            email_sender.send(
                to=account.email, subject="Bestätige deine E-Mail-Adresse",
                body=(
                    f"Bitte bestätige deine E-Mail-Adresse: "
                    f"{_public_base_url()}/verify-email?token={token.token}"
                ),
            )
        except Exception:
            # Same rationale as every other best-effort send in this
            # codebase (password_reset.py, registration.py): the request
            # itself must not fail when SMTP is unreachable, and staying
            # silent here (rather than raising) avoids turning a delivery
            # outage into an account-enumeration side-channel between a
            # known-unverified address and an unknown one. Never log the
            # token itself.
            pass
    # Same response regardless of whether the account exists or is
    # already verified -- enumeration protection, same principle as
    # password-reset's own request endpoint.
    return {"status": "if_the_account_exists_and_is_unverified_an_email_was_sent"}
```

- [ ] **Step 13: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/pytest tests/test_email_verification.py -v`
Expected: PASS, all 6 tests (3 existing + 3 new).

- [ ] **Step 14: Run the full backend test suite for this service**

Run: `cd accounts && .venv/bin/pytest -v`
Expected: PASS, every test (confirms nothing else in `accounts/` broke).

- [ ] **Step 15: Commit**

```bash
cd accounts
git add src/normly_accounts/routers/magic_link.py src/normly_accounts/routers/registration.py \
  src/normly_accounts/routers/email_verification.py src/normly_accounts/schemas.py \
  tests/test_magic_link.py tests/test_registration.py tests/test_email_verification.py
git commit -s -m "feat(accounts): real links in magic-link/verify emails, add resend endpoint"
```

---

### Task 2: Frontend BFF routes for email verification

**Files:**
- Create: `frontend/src/app/api/auth/verify-email/route.ts`
- Create: `frontend/src/app/api/auth/verify-email/resend/route.ts`
- Create: `frontend/tests/unit/verify-email-routes.test.ts`

**Interfaces:**
- Consumes: `getBackendUrls()` (existing, unchanged); Task 1's new
  backend `GET /v1/accounts/verify-email` (unchanged, already existed)
  and `POST /v1/accounts/verify-email/resend` (new).
- Produces: `GET /api/auth/verify-email?token=...` (proxies to the
  backend GET, same query param, same status code) and
  `POST /api/auth/verify-email/resend` (proxies the JSON body) — Task 7's
  `/verify-email` page calls both directly by URL.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/unit/verify-email-routes.test.ts`:

```ts
// frontend/tests/unit/verify-email-routes.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/auth/verify-email/route";
import { POST } from "@/app/api/auth/verify-email/resend/route";

const originalFetch = global.fetch;

describe("GET /api/auth/verify-email", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("forwards the token query param to the backend and relays the response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_verified" }), { status: 200 }),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email?token=abc123");
    const response = await GET(request);
    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/v1/accounts/verify-email?token=abc123");
  });

  it("relays a 400 for an invalid token", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email?token=bad");
    const response = await GET(request);
    expect(response.status).toBe(400);
  });
});

describe("POST /api/auth/verify-email/resend", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("forwards the request body to the backend", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "if_the_account_exists_and_is_unverified_an_email_was_sent" }),
        { status: 200 },
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email/resend", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de" }),
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/v1/accounts/verify-email/resend");
    expect(JSON.parse(init.body as string)).toEqual({ email: "a@example.de" });
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npm test -- verify-email-routes`
Expected: FAIL — neither route file exists yet.

- [ ] **Step 3: Implement the GET route**

Create `frontend/src/app/api/auth/verify-email/route.ts`:

```ts
// frontend/src/app/api/auth/verify-email/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.nextUrl.searchParams.get("token") ?? "";
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/verify-email?token=${encodeURIComponent(token)}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Implement the resend route**

Create `frontend/src/app/api/auth/verify-email/resend/route.ts`:

```ts
// frontend/src/app/api/auth/verify-email/resend/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/verify-email/resend`,
    {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- verify-email-routes`
Expected: PASS, all 3 tests.

- [ ] **Step 6: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 7: Commit**

```bash
cd frontend
git add src/app/api/auth/verify-email tests/unit/verify-email-routes.test.ts
git commit -s -m "feat(frontend): add BFF routes for email verification and resend"
```

---

### Task 3: `AuthSplitLayout` + `/login` page

**Files:**
- Create: `frontend/src/components/auth/auth-split-layout.tsx`
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/login/login-page-content.tsx`
- Create: `frontend/tests/unit/login-page.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `auth.loginPageHeading`, `auth.loginPageDescription`,
  `auth.noAccountLink`, `auth.magicLinkPromptText` keys)

**Interfaces:**
- Consumes: `LoginForm` (`@/components/auth/login-form`, unchanged,
  `{ onSuccess: () => void }`).
- Produces: `AuthSplitLayout` (named export from
  `@/components/auth/auth-split-layout`), props
  `{ headingKey: TranslationKey; descriptionKey?: TranslationKey;
  children: React.ReactNode }` — Tasks 5-7 reuse this exact component
  and prop shape, do not change it later.

- [ ] **Step 1: Add this task's i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the existing `"auth"` object:

```json
    "loginPageHeading": "Willkommen zurück",
    "loginPageDescription": "Melde dich an, um fortzufahren.",
    "noAccountLink": "Noch kein Konto?",
    "magicLinkPromptText": "Lieber ohne Passwort?"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "loginPageHeading": "Welcome back",
    "loginPageDescription": "Log in to continue.",
    "noAccountLink": "Don't have an account yet?",
    "magicLinkPromptText": "Prefer no password?"
```

- [ ] **Step 2: Write the failing test for `AuthSplitLayout` + the login page**

Create `frontend/tests/unit/login-page.test.tsx`:

```tsx
// frontend/tests/unit/login-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { LoginPageContent } from "@/app/login/login-page-content";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const originalFetch = global.fetch;

describe("LoginPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    push.mockClear();
  });

  it("renders the heading, description, and login form", () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Willkommen zurück" })).toBeInTheDocument();
    expect(screen.getByText("Melde dich an, um fortzufahren.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("shows links to signup and the magic-link page", () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Registrieren" })).toHaveAttribute("href", "/signup");
    expect(screen.getByRole("link", { name: "Magic-Link" })).toHaveAttribute(
      "href", "/magic-link",
    );
  });

  it("navigates home after a successful login", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- login-page`
Expected: FAIL — neither `auth-split-layout.tsx` nor `login-page-content.tsx`
exists yet.

- [ ] **Step 4: Implement `AuthSplitLayout`**

Create `frontend/src/components/auth/auth-split-layout.tsx`:

```tsx
// frontend/src/components/auth/auth-split-layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export function AuthSplitLayout({
  headingKey,
  descriptionKey,
  children,
}: {
  headingKey: TranslationKey;
  descriptionKey?: TranslationKey;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <section className="h-svh max-h-[1200px] min-h-[600px] w-full overflow-hidden bg-background">
      <div className="grid h-full lg:grid-cols-2">
        <div className="flex items-center justify-center px-6 py-12">
          <div className="flex w-full max-w-sm flex-col gap-6">
            <div className="flex flex-col gap-2">
              <h1 className="text-3xl font-semibold tracking-tight">{t(headingKey)}</h1>
              {descriptionKey && <p className="text-muted-foreground">{t(descriptionKey)}</p>}
            </div>
            {children}
          </div>
        </div>
        <div className="relative hidden bg-muted lg:block">
          <img
            src="https://deifkwefumgah.cloudfront.net/shadcnblocks/image-set/placeholder/images/6-3x4.jpg"
            alt=""
            className="absolute inset-0 size-full object-cover"
          />
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Implement `LoginPageContent`**

Create `frontend/src/app/login/login-page-content.tsx`:

```tsx
// frontend/src/app/login/login-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { LoginForm } from "@/components/auth/login-form";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginPageContent() {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <AuthSplitLayout headingKey="auth.loginPageHeading" descriptionKey="auth.loginPageDescription">
      <LoginForm onSuccess={() => router.push("/")} />
      <a
        href="/api/auth/google/login"
        className="text-center text-sm text-muted-foreground hover:text-foreground"
      >
        {t("auth.googleButton")}
      </a>
      <p className="text-sm text-muted-foreground">
        {t("auth.magicLinkPromptText")}{" "}
        <Link href="/magic-link" className="font-medium text-primary hover:underline">
          {t("auth.magicLinkTab")}
        </Link>
      </p>
      <p className="text-sm text-muted-foreground">
        {t("auth.noAccountLink")}{" "}
        <Link href="/signup" className="font-medium text-primary hover:underline">
          {t("auth.registerTab")}
        </Link>
      </p>
    </AuthSplitLayout>
  );
}
```

- [ ] **Step 6: Implement `page.tsx`**

Create `frontend/src/app/login/page.tsx`:

```tsx
// frontend/src/app/login/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { LoginPageContent } from "./login-page-content";

export default function LoginPage() {
  return <LoginPageContent />;
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd frontend && npm test -- login-page`
Expected: PASS, all 3 tests.

- [ ] **Step 8: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed; `/login` appears in the route list.

- [ ] **Step 9: Commit**

```bash
cd frontend
git add src/components/auth/auth-split-layout.tsx src/app/login \
  tests/unit/login-page.test.tsx src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add AuthSplitLayout and the /login page"
```

---

### Task 4: `/signup` page

**Files:**
- Create: `frontend/src/app/signup/page.tsx`
- Create: `frontend/src/app/signup/signup-page-content.tsx`
- Create: `frontend/tests/unit/signup-page.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `auth.signupPageHeading`, `auth.haveAccountLink` keys)

**Interfaces:**
- Consumes: `RegisterForm` (`@/components/auth/register-form`, unchanged,
  `{ onSuccess: () => void }`).
- Produces: nothing new for later tasks — `/signup` has no other
  consumer in this plan.

- [ ] **Step 1: Add this task's i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the `"auth"` object:

```json
    "signupPageHeading": "Konto erstellen",
    "haveAccountLink": "Bereits ein Konto?"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "signupPageHeading": "Create an account",
    "haveAccountLink": "Already have an account?"
```

- [ ] **Step 2: Write the failing test**

Create `frontend/tests/unit/signup-page.test.tsx`:

```tsx
// frontend/tests/unit/signup-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { SignupPageContent } from "@/app/signup/signup-page-content";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const originalFetch = global.fetch;

describe("SignupPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    push.mockClear();
  });

  it("renders the heading, the register form, and a link back to login", () => {
    render(
      <LocaleProvider initialLocale="de">
        <SignupPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Konto erstellen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Konto erstellen" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/login");
  });

  it("navigates home after a successful registration", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <SignupPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "new@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- signup-page`
Expected: FAIL — `signup-page-content.tsx` doesn't exist yet.

- [ ] **Step 4: Implement `SignupPageContent`**

Create `frontend/src/app/signup/signup-page-content.tsx`:

```tsx
// frontend/src/app/signup/signup-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RegisterForm } from "@/components/auth/register-form";
import { useTranslation } from "@/lib/i18n/provider";

export function SignupPageContent() {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <section className="flex h-svh w-full items-center justify-center bg-muted px-6 py-12">
      <div className="flex w-full max-w-sm flex-col items-center gap-6">
        <h1 className="text-xl font-semibold">{t("auth.signupPageHeading")}</h1>
        <div className="w-full rounded-md border bg-background p-6 shadow-md">
          <RegisterForm onSuccess={() => router.push("/")} />
        </div>
        <p className="flex gap-1 text-sm text-muted-foreground">
          {t("auth.haveAccountLink")}
          <Link href="/login" className="font-medium text-primary hover:underline">
            {t("auth.loginTab")}
          </Link>
        </p>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Implement `page.tsx`**

Create `frontend/src/app/signup/page.tsx`:

```tsx
// frontend/src/app/signup/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { SignupPageContent } from "./signup-page-content";

export default function SignupPage() {
  return <SignupPageContent />;
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npm test -- signup-page`
Expected: PASS, both tests.

- [ ] **Step 7: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed; `/signup` appears in the route list.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/app/signup tests/unit/signup-page.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add the /signup page"
```

---

### Task 5: `/magic-link` page

**Files:**
- Create: `frontend/src/app/magic-link/page.tsx`
- Create: `frontend/src/app/magic-link/magic-link-page-content.tsx`
- Create: `frontend/tests/unit/magic-link-page.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `auth.magicLinkPageHeading`, `auth.magicLinkPageDescription` keys)

**Interfaces:**
- Consumes: `AuthSplitLayout` (Task 3, unchanged), `MagicLinkForm`
  (`@/components/auth/magic-link-form`, unchanged, no props).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Add this task's i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the `"auth"` object:

```json
    "magicLinkPageHeading": "Mit Link anmelden",
    "magicLinkPageDescription": "Gib deine E-Mail-Adresse ein, wir schicken dir einen Anmeldelink."
```

In `frontend/src/lib/i18n/en.json`:

```json
    "magicLinkPageHeading": "Sign in with a link",
    "magicLinkPageDescription": "Enter your email address and we'll send you a sign-in link."
```

- [ ] **Step 2: Write the failing test**

Create `frontend/tests/unit/magic-link-page.test.tsx`:

```tsx
// frontend/tests/unit/magic-link-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MagicLinkPageContent } from "@/app/magic-link/magic-link-page-content";

const originalFetch = global.fetch;

describe("MagicLinkPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the heading, description, and a link back to login", () => {
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Mit Link anmelden" })).toBeInTheDocument();
    expect(
      screen.getByText("Gib deine E-Mail-Adresse ein, wir schicken dir einen Anmeldelink."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zur Anmeldung" })).toHaveAttribute(
      "href", "/login",
    );
  });

  it("shows the confirmation message after requesting a link", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmeldelink senden" }));
    await waitFor(() => expect(screen.getByText("Anmeldelink senden ✓")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- magic-link-page`
Expected: FAIL — `magic-link-page-content.tsx` doesn't exist yet.

- [ ] **Step 4: Implement `MagicLinkPageContent`**

Create `frontend/src/app/magic-link/magic-link-page-content.tsx`:

```tsx
// frontend/src/app/magic-link/magic-link-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { MagicLinkForm } from "@/components/auth/magic-link-form";
import { useTranslation } from "@/lib/i18n/provider";

export function MagicLinkPageContent() {
  const { t } = useTranslation();

  return (
    <AuthSplitLayout
      headingKey="auth.magicLinkPageHeading"
      descriptionKey="auth.magicLinkPageDescription"
    >
      <MagicLinkForm />
      <Link
        href="/login"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        {t("auth.backToLogin")}
      </Link>
    </AuthSplitLayout>
  );
}
```

- [ ] **Step 5: Implement `page.tsx`**

Create `frontend/src/app/magic-link/page.tsx`:

```tsx
// frontend/src/app/magic-link/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { MagicLinkPageContent } from "./magic-link-page-content";

export default function MagicLinkPage() {
  return <MagicLinkPageContent />;
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npm test -- magic-link-page`
Expected: PASS, both tests.

- [ ] **Step 7: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed; `/magic-link` appears in the route list.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/app/magic-link tests/unit/magic-link-page.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add the /magic-link page"
```

---

### Task 6: Replace `/reset-password`'s page shell

**Files:**
- Modify: `frontend/src/app/reset-password/page.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `auth.resetPasswordPageHeading`, `auth.resetPasswordPageDescription`
  keys)

**Interfaces:**
- Consumes: `AuthSplitLayout` (Task 3, unchanged), the existing
  `ResetPasswordContent` (`./reset-password-content`, completely
  unchanged — this task never touches that file).
- Produces: nothing new for later tasks.

`reset-password-content.tsx` and `tests/unit/reset-password-page.test.tsx`
are NOT touched by this task — the existing test renders
`ResetPasswordContent` directly (not through `page.tsx`), so it keeps
passing unmodified as long as `ResetPasswordContent`'s own code doesn't
change, which it doesn't here.

- [ ] **Step 1: Add this task's i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the `"auth"` object:

```json
    "resetPasswordPageHeading": "Neues Passwort festlegen",
    "resetPasswordPageDescription": "Wähle ein neues Passwort für dein Konto."
```

In `frontend/src/lib/i18n/en.json`:

```json
    "resetPasswordPageHeading": "Set a new password",
    "resetPasswordPageDescription": "Choose a new password for your account."
```

- [ ] **Step 2: Replace `page.tsx`**

Replace `frontend/src/app/reset-password/page.tsx`'s entire content:

```tsx
// frontend/src/app/reset-password/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { ResetPasswordContent } from "./reset-password-content";

export default function ResetPasswordPage() {
  return (
    <AuthSplitLayout
      headingKey="auth.resetPasswordPageHeading"
      descriptionKey="auth.resetPasswordPageDescription"
    >
      <ResetPasswordContent />
    </AuthSplitLayout>
  );
}
```

- [ ] **Step 3: Run the existing reset-password test to confirm it's unaffected**

Run: `cd frontend && npm test -- reset-password`
Expected: PASS, both existing tests (they render `ResetPasswordContent`
directly, never `page.tsx`, so this step's change cannot affect them —
this is a confirmation, not a step that could plausibly fail).

- [ ] **Step 4: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/app/reset-password/page.tsx src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): restyle /reset-password with AuthSplitLayout"
```

---

### Task 7: `/verify-email` page

**Files:**
- Create: `frontend/src/app/verify-email/page.tsx`
- Create: `frontend/src/app/verify-email/verify-email-content.tsx`
- Create: `frontend/tests/unit/verify-email-page.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `auth.verifyEmailPageHeading`, `auth.verifyingMessage`,
  `auth.verifiedMessage`, `auth.verifyInvalidMessage`,
  `auth.resendVerificationButton`, `auth.resendVerificationSentMessage`
  keys)

**Interfaces:**
- Consumes: `AuthSplitLayout` (Task 3, unchanged); Task 2's
  `GET /api/auth/verify-email?token=...` and
  `POST /api/auth/verify-email/resend`.
- Produces: nothing new for later tasks.

- [ ] **Step 1: Add this task's i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the `"auth"` object:

```json
    "verifyEmailPageHeading": "E-Mail-Adresse bestätigen",
    "verifyingMessage": "Deine E-Mail-Adresse wird bestätigt…",
    "verifiedMessage": "Deine E-Mail-Adresse wurde bestätigt.",
    "verifyInvalidMessage": "Dieser Link ist ungültig oder abgelaufen.",
    "resendVerificationButton": "Bestätigungslink erneut senden",
    "resendVerificationSentMessage": "Falls ein Konto mit dieser Adresse existiert und noch nicht bestätigt ist, wurde eine E-Mail versendet."
```

In `frontend/src/lib/i18n/en.json`:

```json
    "verifyEmailPageHeading": "Verify your email address",
    "verifyingMessage": "Verifying your email address…",
    "verifiedMessage": "Your email address has been verified.",
    "verifyInvalidMessage": "This link is invalid or has expired.",
    "resendVerificationButton": "Resend verification link",
    "resendVerificationSentMessage": "If an account with this address exists and isn't verified yet, an email was sent."
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/tests/unit/verify-email-page.test.tsx`:

```tsx
// frontend/tests/unit/verify-email-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { VerifyEmailContent } from "@/app/verify-email/verify-email-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token"),
}));

const originalFetch = global.fetch;

describe("VerifyEmailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the verified message when the token is accepted", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_verified" }), { status: 200 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText("Deine E-Mail-Adresse wurde bestätigt.")).toBeInTheDocument(),
    );
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/verify-email?token=valid-token");
  });

  it("shows the invalid-link message and a resend form when the token is rejected", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText("Dieser Link ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Bestätigungslink erneut senden" })).toBeInTheDocument();
  });

  it("shows the resend-sent confirmation after submitting the resend form", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith("/api/auth/verify-email?")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ status: "sent" }), { status: 200 }),
      );
    });
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Bestätigungslink erneut senden" })).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Bestätigungslink erneut senden" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "Falls ein Konto mit dieser Adresse existiert und noch nicht bestätigt ist, wurde eine E-Mail versendet.",
        ),
      ).toBeInTheDocument(),
    );
    const resendCall = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]) => url === "/api/auth/verify-email/resend",
    );
    expect(resendCall).toBeDefined();
  });
});
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd frontend && npm test -- verify-email-page`
Expected: FAIL — `verify-email-content.tsx` doesn't exist yet.

- [ ] **Step 4: Implement `VerifyEmailContent`**

Create `frontend/src/app/verify-email/verify-email-content.tsx`:

```tsx
// frontend/src/app/verify-email/verify-email-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

type Status = "verifying" | "verified" | "invalid";

function VerifyEmailStatus() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = React.useState<Status>(token ? "verifying" : "invalid");
  const [resendEmail, setResendEmail] = React.useState("");
  const [resendSent, setResendSent] = React.useState(false);
  const [isResending, setIsResending] = React.useState(false);

  React.useEffect(() => {
    if (!token) return;
    fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then((response) => setStatus(response.ok ? "verified" : "invalid"))
      .catch(() => setStatus("invalid"));
  }, [token]);

  const submitResend = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsResending(true);
    try {
      await fetch("/api/auth/verify-email/resend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: resendEmail }),
      });
      setResendSent(true);
    } finally {
      setIsResending(false);
    }
  };

  if (status === "verifying") {
    return <p className="text-sm text-muted-foreground">{t("auth.verifyingMessage")}</p>;
  }
  if (status === "verified") {
    return <p className="text-sm">{t("auth.verifiedMessage")}</p>;
  }
  if (resendSent) {
    return <p className="text-sm">{t("auth.resendVerificationSentMessage")}</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-destructive">{t("auth.verifyInvalidMessage")}</p>
      <form onSubmit={submitResend} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("auth.emailLabel")}
          <Input
            type="email"
            value={resendEmail}
            onChange={(event) => setResendEmail(event.target.value)}
            required
          />
        </label>
        <Button type="submit" disabled={isResending}>
          {t("auth.resendVerificationButton")}
        </Button>
      </form>
    </div>
  );
}

export function VerifyEmailContent() {
  return (
    <React.Suspense fallback={null}>
      <VerifyEmailStatus />
    </React.Suspense>
  );
}
```

- [ ] **Step 5: Implement `page.tsx`**

Create `frontend/src/app/verify-email/page.tsx`:

```tsx
// frontend/src/app/verify-email/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { VerifyEmailContent } from "./verify-email-content";

export default function VerifyEmailPage() {
  return (
    <AuthSplitLayout headingKey="auth.verifyEmailPageHeading">
      <VerifyEmailContent />
    </AuthSplitLayout>
  );
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test -- verify-email-page`
Expected: PASS, all 3 tests.

- [ ] **Step 7: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed; `/verify-email` appears in the route list.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/app/verify-email tests/unit/verify-email-page.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add the /verify-email page"
```

---

### Task 8: Retire `AuthDialog`

**Files:**
- Delete: `frontend/src/components/auth/auth-dialog.tsx`
- Modify: `frontend/src/components/app-shell.tsx`
- Modify: `frontend/src/components/app-header.tsx`
- Modify: `frontend/tests/unit/app-shell.test.tsx`
- Modify: `frontend/tests/unit/app-header.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (remove the now-dead `auth.loginTab` usage as a dialog-trigger button
  label is unaffected — `loginTab`/`registerTab`/`magicLinkTab` stay,
  still used by Tasks 3-5's link text and this task's own link text; no
  keys are actually removed by this task)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — `NavUser`'s and `AppHeader`'s logged-out
  states change from rendering `<AuthDialog onAuthenticated={...} />` to
  rendering `<Link href="/login">`, that's the only behavior change.

Both call sites must change — check both, not just the one you remember.
`grep -rln "AuthDialog" frontend/src` before Step 1 confirms exactly
which files reference it (three: `app-shell.tsx`, `app-header.tsx`, and
`auth-dialog.tsx` itself).

- [ ] **Step 1: Write the failing test for `AppShell`'s logged-out state**

Add to `frontend/tests/unit/app-shell.test.tsx` (replace the EXISTING
"shows the login trigger in the footer when logged out" test — it
currently asserts a button; change the assertion to a link):

Find this existing test:

```tsx
  it("shows the login trigger in the footer when logged out", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument(),
    );
  });
```

Replace it with:

```tsx
  it("shows a link to /login in the footer when logged out", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/login"),
    );
  });
```

- [ ] **Step 2: Write the failing test for `AppHeader`'s logged-out state**

In `frontend/tests/unit/app-header.test.tsx`, find:

```tsx
  it("shows the login trigger when the session check returns no account", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument(),
    );
  });
```

Replace it with:

```tsx
  it("shows a link to /login when the session check returns no account", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/login"),
    );
  });
```

- [ ] **Step 3: Run both to verify they fail**

Run: `cd frontend && npm test -- app-shell app-header`
Expected: FAIL — both still render `AuthDialog`'s button trigger, not a
link.

- [ ] **Step 4: Rewire `AppShell`'s `NavUser`**

In `frontend/src/components/app-shell.tsx`, remove the import:

```tsx
import { AuthDialog } from "@/components/auth/auth-dialog";
```

and add:

```tsx
import Link from "next/link";
```

(check whether `Link` is already imported at the top of this file from
an earlier plan — if so, don't duplicate the import).

Inside `NavUser`, replace:

```tsx
  if (!account) {
    return (
      <div className="p-2 group-data-[collapsible=icon]:hidden">
        <AuthDialog onAuthenticated={refreshSession} />
      </div>
    );
  }
```

with:

```tsx
  if (!account) {
    return (
      <div className="p-2 group-data-[collapsible=icon]:hidden">
        <Button variant="outline" asChild>
          <Link href="/login">{t("auth.loginTab")}</Link>
        </Button>
      </div>
    );
  }
```

(`Button` and `t` are already imported/in scope in this file from earlier
plans — no new imports needed for this specific change beyond `Link`.
`refreshSession` may now be unused in `NavUser` if nothing else in the
function references it — check, and remove it from the destructured
`useAccountSession()` call if so; if `logout` still needs it or anything
else does, leave it. Since `NavUser` currently destructures `{ account,
refreshSession, logout }` as props from `AppShell` per an earlier plan,
check that specific prop signature — if `refreshSession` becomes
genuinely unused after this change, remove it from `NavUser`'s prop type
and from the `<NavUser ... />` call site in `AppShell` too, to avoid an
unused-variable lint/type situation; if you're unsure whether it's safe
to remove, leave it in place and note it in your report rather than
guessing.)

- [ ] **Step 5: Rewire `AppHeader`**

In `frontend/src/components/app-header.tsx`, remove the import:

```tsx
import { AuthDialog } from "@/components/auth/auth-dialog";
```

(check `Link` is already imported — it should be, from this same file's
existing avatar-wrapping usage before Plan 4 removed the `/account` link;
if the import was removed entirely in that earlier plan, re-add it).

Replace:

```tsx
          <AuthDialog onAuthenticated={refreshSession} />
```

with:

```tsx
          <Button variant="outline" asChild>
            <Link href="/login">{t("auth.loginTab")}</Link>
          </Button>
```

(`Link` and `Button` are both already imported in this file — no new
imports needed. `AppHeader` calls `useAccountSession()` directly, not via
props, so `refreshSession` becomes unused here too once this change
lands — same discretion as Task 8 Step 4: remove it from the
destructured `useAccountSession()` call if it's genuinely unused
elsewhere in this file, or leave it and note it if unsure.)

- [ ] **Step 6: Delete `AuthDialog`**

```bash
cd frontend
rm src/components/auth/auth-dialog.tsx
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd frontend && npm test -- app-shell app-header`
Expected: PASS, all tests in both files.

- [ ] **Step 8: Confirm nothing else references the deleted file**

Run: `cd frontend && grep -rn "auth-dialog\|AuthDialog" src tests`
Expected: no matches.

- [ ] **Step 9: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 10: Note the Playwright e2e residual**

Any existing Playwright spec that opens the login modal via
`AuthDialog`'s old trigger button, or that navigates to the old
`/reset-password` shell expecting `AppHeader` around it, will need
updating — flag this explicitly in the PR description as a known
follow-up, matching the pattern from every prior plan's retirement step
in this redesign.

- [ ] **Step 11: Commit**

```bash
cd frontend
git add -A src/components/auth/auth-dialog.tsx src/components/app-shell.tsx \
  src/components/app-header.tsx tests/unit/app-shell.test.tsx tests/unit/app-header.test.tsx
git commit -s -m "chore(frontend): retire AuthDialog, link Anmelden to /login"
```

---

## After This Plan

Ask the user for explicit confirmation before pushing the branch and
before opening a PR (each triggers a billed STACKIT CI run — see Global
Constraints). Once confirmed: push `frontend/auth-pages`, open a PR
against `main` on the `stackit` remote — mention the Playwright e2e
residual (Task 8, Step 10) in the PR description — wait for the CI
pipeline's `test-frontend` AND `test-accounts` jobs to both go green
(this plan is the first in this redesign to touch backend Python code),
then ask the user to merge (same confirm-first rule applies). Plan 6
(Suche & Dokument-Detail) remains in this redesign; it does not depend on
this plan.
