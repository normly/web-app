# Maintenance Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close six small, independent, already-scoped backlog items tracked across earlier sub-projects: a real security gap (OAuth login-CSRF), a GDPR/DSGVO export completeness gap, a consistency gap (missing license headers), and three small frontend defects (a dead badge value, a leftover spacing artifact, a dev-only double-fetch).

**Architecture:** No new architecture. Each task is a targeted fix inside an existing file or a small, well-understood addition using patterns already established elsewhere in the same codebase (existing cookie-free auth model gets its first cookie; existing export endpoint gains two more repository calls against data that's already reachable in-process; existing shadcn convention gets applied to files that were missed; existing hook value gets a consumer; one leftover JSX line gets deleted; one existing `cancelled`-flag guard gets a sibling `useRef` guard).

**Tech Stack:** FastAPI + SQLAlchemy (`accounts/`, using `normly-core`'s repositories directly against a shared Postgres session), Next.js + React + Vitest + Testing Library (`frontend/`).

## Global Constraints

- DCO `Signed-off-by` (human, via `git commit -s`) + Conventional Commits + a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer on every commit. Never let a subagent sign off its own commit.
- License headers on any newly created file. None of these six tasks create a new file — Task 3 is entirely about adding the header to ten files that already exist.
- No scope creep into anything explicitly deferred elsewhere: the Next.js/Vite major-version upgrade (own follow-up plan, not part of this one — it's a breaking major-version bump needing its own test pass), an automatic Notification-row cleanup CLI job (not confirmed in scope this session), `find_previous_edition`'s edition-string-comparison assumption, and the semantic-search Tier-2 threshold/index gaps (both explicitly deferred pending real corpus data).
- Tasks are independent — different files, no shared new types — and may be executed in any order, but are listed here in a sensible order (backend security → backend compliance → frontend mechanical → frontend small fixes).
- Every new/changed Python function keeps this codebase's existing style: no docstrings beyond what's already there, comments only where the *why* isn't obvious from the code.

---

### Task 1: Google OAuth login-CSRF fix

**Files:**
- Modify: `accounts/src/normly_accounts/routers/google.py`
- Test: `accounts/tests/test_google_login.py`

**Interfaces:**
- Consumes: nothing from another task in this plan.
- Produces: nothing another task in this plan depends on. Fully self-contained.

**Context:** `/v1/accounts/google/login` generates a random `state` token and hands it to Google inside the authorization URL, but nothing is ever persisted server-side — `/v1/accounts/google/callback` declares `state: str` as a required query parameter purely so FastAPI accepts Google's redirect, and then never reads it again. An attacker can craft their own `code`+`state` pair and drive a victim's browser through the callback, linking the victim's session to the attacker's Google account (classic OAuth login-CSRF). The fix: store `state` in a short-lived, httponly cookie when `/login` issues it, and reject the callback if the cookie is missing or doesn't match the query parameter's `state`.

- [ ] **Step 1: Replace the test file with the updated version (cookie-aware tests + 2 new tests)**

Every existing test in this file calls `/callback` directly without ever going through `/login`, using arbitrary literal `state` values — under the new check, every one of them needs to set a matching cookie first via `client.cookies.set(...)` (httpx's `TestClient.cookies` is a plain settable jar). Replace the full contents of `accounts/tests/test_google_login.py` with:

```python
# accounts/tests/test_google_login.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_accounts.google_oauth import GoogleProfile


class _FakeGoogleOAuthClient:
    def __init__(self, profile: GoogleProfile):
        self._profile = profile

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile:
        return self._profile


def _override_google_client(app, profile: GoogleProfile) -> None:
    from normly_accounts.dependencies import get_google_oauth_client

    app.dependency_overrides[get_google_oauth_client] = lambda: _FakeGoogleOAuthClient(profile)


def _set_state_cookie(client, state: str = "fake-state") -> None:
    client.cookies.set("google_oauth_state", state)


def test_google_login_redirects_to_googles_consent_screen(client):
    response = client.get("/v1/accounts/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    set_cookie = response.headers["set-cookie"]
    assert "google_oauth_state=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_google_callback_creates_a_new_account_for_an_unseen_subject(client):
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-1", email="newgoogle@example.de", email_verified=True
        )
    )
    _set_state_cookie(client, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "newgoogle@example.de"


def test_google_callback_links_to_an_existing_email_password_account(client):
    client.post(
        "/v1/accounts/register",
        json={"email": "linkme@example.de", "password": "correct horse battery staple"},
    )
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-2", email="linkme@example.de", email_verified=True
        )
    )

    _set_state_cookie(client, "fake-state")
    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "linkme@example.de"

    # A second callback with the same Google subject resolves to the SAME
    # account rather than raising a duplicate-email error -- proves the
    # link, not just a coincidental match.
    _set_state_cookie(client, "fake-state")
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code-2", "state": "fake-state"}
    )
    assert second.json()["account"]["id"] == response.json()["account"]["id"]


def test_google_callback_reuses_the_account_for_a_returning_google_subject(client):
    profile = GoogleProfile(
        subject_id="google-sub-3", email="returning@example.de", email_verified=True
    )
    _override_google_client(client.app, profile)

    _set_state_cookie(client, "state-1")
    first = client.get(
        "/v1/accounts/google/callback", params={"code": "code-1", "state": "state-1"}
    )
    _set_state_cookie(client, "state-2")
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "code-2", "state": "state-2"}
    )

    assert first.json()["account"]["id"] == second.json()["account"]["id"]


def test_google_callback_refuses_to_link_an_unverified_email_to_an_existing_account(client):
    """
    A Google identity may *assert* any email address; only `email_verified`
    means Google checked it. Linking on an unverified assertion would hand
    whoever controls that Google identity a full session on the victim's
    existing password account.
    """
    client.post(
        "/v1/accounts/register",
        json={"email": "victim@example.de", "password": "correct horse battery staple"},
    )
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="attacker-sub", email="victim@example.de", email_verified=False
        )
    )
    _set_state_cookie(client, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 400
    assert "not verified" in response.json()["detail"]


def test_google_callback_still_creates_an_account_for_an_unverified_unknown_email(client):
    """
    The risk is takeover of something that already exists. With no account on
    that address, an unverified email can only produce a new Google-only
    account reachable by this very Google subject -- no one else is harmed.
    """
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="unverified-sub", email="nobodyelse@example.de", email_verified=False
        )
    )
    _set_state_cookie(client, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "nobodyelse@example.de"


def test_google_callback_returns_400_when_the_user_cancels_consent(client):
    """
    Cancelling on Google's consent screen redirects back with `?error=...`
    and no `code`. That is an ordinary outcome, not a malformed request --
    it must be the spec's 400, not FastAPI's own 422. A valid state cookie
    is set here too, so this test still genuinely exercises the
    cancellation path rather than failing earlier on the state check.
    """
    _set_state_cookie(client, "fake-state")
    response = client.get(
        "/v1/accounts/google/callback",
        params={"state": "fake-state", "error": "access_denied"},
    )

    assert response.status_code == 400
    # Google's raw error value is third-party input and is never echoed back.
    assert "access_denied" not in response.json()["detail"]


def test_google_callback_returns_400_when_the_token_exchange_fails(client):
    """
    An expired code or a wrong client secret makes Google answer non-2xx.
    That is the caller's problem, not a defect in this service, so it must
    not surface as a 500.
    """
    import httpx

    from normly_accounts.dependencies import get_google_oauth_client

    class _FailingGoogleOAuthClient:
        def build_authorization_url(self, redirect_uri: str, state: str) -> str:
            return "https://accounts.google.com/o/oauth2/v2/auth"

        def exchange_code(self, code: str, redirect_uri: str) -> GoogleProfile:
            raise httpx.HTTPStatusError(
                "400 Bad Request",
                request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
                response=httpx.Response(400),
            )

    client.app.dependency_overrides[get_google_oauth_client] = _FailingGoogleOAuthClient
    _set_state_cookie(client, "fake-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "expired", "state": "fake-state"}
    )

    assert response.status_code == 400


def test_google_callback_is_409_when_the_account_already_has_another_google_identity(
    client, db_session
):
    """
    An account carries at most one Google identity (account_id is the primary
    key of account_google_identity). A second subject resolving to the same
    address -- a deleted and recreated Google account, say -- used to raise an
    uncaught IntegrityError: a 500, and a session too poisoned to answer
    anything else.
    """
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="old-sub", email="relinked@example.de", email_verified=True
        )
    )
    _set_state_cookie(client, "s1")
    first = client.get(
        "/v1/accounts/google/callback", params={"code": "c1", "state": "s1"}
    )
    assert first.status_code == 200

    _override_google_client(
        client.app, GoogleProfile(
            subject_id="new-sub", email="relinked@example.de", email_verified=True
        )
    )
    _set_state_cookie(client, "s2")
    second = client.get(
        "/v1/accounts/google/callback", params={"code": "c2", "state": "s2"}
    )

    assert second.status_code == 409

    # The session is still usable afterwards -- the savepoint rolled back the
    # failed insert, not the whole request.
    from normly_core.graph.postgres.repositories import PostgresAccountRepository

    assert PostgresAccountRepository(db_session).get_account_by_email(
        "relinked@example.de"
    ) is not None


def test_google_callback_returns_400_when_state_cookie_is_missing(client):
    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "fake-state"}
    )

    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_google_callback_returns_400_when_state_does_not_match_cookie(client):
    _set_state_cookie(client, "cookie-value")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "different-value"}
    )

    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()
```

- [ ] **Step 2: Run the tests to confirm the expected failures**

Run: `accounts/.venv/bin/pytest accounts/tests/test_google_login.py -v`

Expected: the 2 brand-new tests (`..._state_cookie_is_missing`, `..._state_does_not_match_cookie`) FAIL (callback still returns 200/whatever the old logic produces, not 400), and `test_google_login_redirects_to_googles_consent_screen` FAILS on the `set_cookie` assertions (`KeyError: 'set-cookie'` — `/login` doesn't set one yet). The other 9 tests still PASS at this point (they carry a cookie the current implementation simply ignores) — that's expected and not a sign anything is wrong; only the 3 listed above should fail.

- [ ] **Step 3: Implement the cookie-based state check in `google.py`**

In `accounts/src/normly_accounts/routers/google.py`, change the import line (currently `from fastapi import APIRouter, Depends, HTTPException`) to:

```python
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
```

Add two module-level constants right after `google_router = APIRouter(prefix="/v1/accounts/google", tags=["google"])`:

```python
_STATE_COOKIE_NAME = "google_oauth_state"
_STATE_COOKIE_MAX_AGE = 600
```

Replace the `google_login` function body:

```python
@google_router.get("/login")
def google_login(
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> RedirectResponse:
    state = generate_token()
    url = google_client.build_authorization_url(_redirect_uri(), state)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        _STATE_COOKIE_NAME,
        state,
        max_age=_STATE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_redirect_uri().startswith("https://"),
    )
    return response
```

Replace the `google_callback` function's signature and its first check, keeping everything from the `try: profile = google_client.exchange_code(...)` line onward exactly as it already is:

```python
@google_router.get("/callback", response_model=SessionResponse)
def google_callback(
    response: Response,
    state: str,
    code: str | None = None,
    error: str | None = None,
    google_oauth_state: str | None = Cookie(default=None, alias=_STATE_COOKIE_NAME),
    session: Session = Depends(get_session),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> SessionResponse:
    # Always clear the one-time cookie -- it must never be reusable for a
    # second callback, whether this one succeeds, fails, or the request never
    # even reaches Google (missing/mismatched state below).
    response.delete_cookie(_STATE_COOKIE_NAME)
    if google_oauth_state is None or state != google_oauth_state:
        raise HTTPException(status_code=400, detail="Google OAuth state mismatch")

    # Google redirects back here with EITHER `code` or `error` -- clicking
    # "Cancel" on the consent screen yields `?error=access_denied` and no
    # code. Declaring `code` as required would turn that ordinary outcome
    # into a 422 from FastAPI's own validation instead of the 400 the design
    # spec mandates. Google's raw `error` value is never echoed back: it is
    # third-party input and tells the caller nothing they can act on.
    if error is not None or code is None:
        raise HTTPException(status_code=400, detail="Google OAuth was cancelled or failed")
```

(Everything below that in the original file — the `try:`/`except httpx.HTTPError:` block through the final `return _create_session_response(account, session)` — is unchanged.)

- [ ] **Step 4: Run the tests again to confirm everything passes**

Run: `accounts/.venv/bin/pytest accounts/tests/test_google_login.py -v`

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add accounts/src/normly_accounts/routers/google.py accounts/tests/test_google_login.py
git commit -s -m "fix(accounts): validate OAuth state cookie on Google callback

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: GDPR export gap — add watchlist and notifications

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py`
- Modify: `accounts/src/normly_accounts/routers/account_management.py`
- Test: `accounts/tests/test_account_management.py`

**Interfaces:**
- Consumes: `PostgresWatchlistRepository.list_watches_for_account(account_id) -> list[Watchlist]` (fields `work_id`, `created_at`) and `PostgresNotificationRepository.list_for_account(account_id) -> list[Notification]` (fields `id`, `work_id`, `trigger_type` [enum, has `.value`], `trigger_document_id`, `trigger_jurisdiction`, `created_at`, `read_at`, `emailed_at`) — both already exist in `core/src/normly_core/graph/postgres/repositories.py`, unchanged by this task.
- Produces: nothing another task in this plan depends on. Fully self-contained.

**Context:** `GET /v1/accounts/export` (the DSGVO self-service data export) currently returns only account fields and chat sessions — watchlist entries and notifications aren't included at all, even though both live in the same database and are already reachable in-process (accounts/ imports core/'s repositories directly and runs them against the same SQLAlchemy session, no HTTP boundary to bridge). The export must include every notification regardless of the account's current display preference — `notifications.py`'s `list_notifications` endpoint hides notifications for `EMAIL`-preference accounts, but that's a display-only UI concern and must NOT be applied here: a full personal-data export shows everything.

- [ ] **Step 1: Add the two new tests**

Append to `accounts/tests/test_account_management.py` (also add the needed imports at the top of the file — replace the existing `from normly_core.graph.domain import ChatMessageRole` line with the wider import below, and add the two new repository imports):

```python
from normly_core.graph.domain import ChatMessageRole, NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository, PostgresChatRepository, PostgresNotificationRepository,
    PostgresWatchlistRepository, PostgresWorkRepository,
)
```

Then add these two tests at the end of the file:

```python
def test_export_includes_watchlist_entries(client, db_session):
    headers = _register(client, email="watchlistexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=uuid.UUID(account_id), work_id=work.id
    )
    db_session.commit()

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["watchlist"]) == 1
    assert body["watchlist"][0]["work_id"] == str(work.id)


def test_export_includes_notifications(client, db_session):
    headers = _register(client, email="notificationsexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresNotificationRepository(db_session).create(
        account_id=uuid.UUID(account_id), work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=None,
        trigger_document_id=None, trigger_jurisdiction=None, may_process=None,
        may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.commit()

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["work_id"] == str(work.id)
    assert body["notifications"][0]["trigger_type"] == "new_edition"
    assert body["notifications"][0]["emailed_at"] is None
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `accounts/.venv/bin/pytest accounts/tests/test_account_management.py -v`

Expected: `test_export_includes_watchlist_entries` and `test_export_includes_notifications` FAIL with a `KeyError: 'watchlist'` / `KeyError: 'notifications'` (the response body has no such keys yet). All 7 pre-existing tests still PASS.

- [ ] **Step 3: Add the new schema classes to `schemas.py`**

In `accounts/src/normly_accounts/schemas.py`, add `notification_preference: str` to `ExportAccountFields`:

```python
class ExportAccountFields(BaseModel):
    email: str
    created_at: datetime
    email_verified: bool
    google_linked: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None
    notification_preference: str
```

Add two new classes right after `ExportChatSession` and before `ExportResponse`:

```python
class ExportWatchlistEntry(BaseModel):
    work_id: uuid.UUID
    created_at: datetime


class ExportNotification(BaseModel):
    id: uuid.UUID
    work_id: uuid.UUID
    trigger_type: str
    trigger_document_id: uuid.UUID | None
    trigger_jurisdiction: str | None
    created_at: datetime
    read_at: datetime | None
    emailed_at: datetime | None
```

Extend `ExportResponse`:

```python
class ExportResponse(BaseModel):
    account: ExportAccountFields
    chat_sessions: list[ExportChatSession]
    watchlist: list[ExportWatchlistEntry]
    notifications: list[ExportNotification]
```

- [ ] **Step 4: Populate the new fields in `export_account_data`**

In `accounts/src/normly_accounts/routers/account_management.py`, change the imports:

```python
from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresChatRepository,
    PostgresNotificationRepository,
    PostgresWatchlistRepository,
)

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import (
    DeleteAccountRequest, ExportAccountFields, ExportChatMessage, ExportChatSession,
    ExportNotification, ExportResponse, ExportWatchlistEntry,
)
from normly_accounts.security import verify_password
```

Replace the body of `export_account_data` (everything from `google_linked = ...` to the final `return ExportResponse(...)`):

```python
    google_linked = PostgresAccountGoogleIdentityRepository(session).has_google_identity(
        account.id
    )

    chat_repo = PostgresChatRepository(session)
    chat_sessions = chat_repo.list_sessions_for_account(account.id)
    exported_sessions = []
    for chat_session in chat_sessions:
        messages = chat_repo.list_messages_for_session(chat_session.id)
        exported_sessions.append(
            ExportChatSession(
                session_token=chat_session.session_token, jurisdiction=chat_session.jurisdiction,
                language=chat_session.language, created_at=chat_session.created_at,
                messages=[
                    ExportChatMessage(role=m.role.value, content=m.content, created_at=m.created_at)
                    for m in messages
                ],
            )
        )

    watches = PostgresWatchlistRepository(session).list_watches_for_account(account.id)
    # Every notification is included regardless of the account's current
    # display preference -- EMAIL-preference accounts still see their in-app
    # feed hidden (notifications.py's own concern), but a full personal-data
    # export is not a display and must not apply that filter.
    notifications = PostgresNotificationRepository(session).list_for_account(account.id)

    return ExportResponse(
        account=ExportAccountFields(
            email=account.email, created_at=account.created_at,
            email_verified=account.email_verified_at is not None, google_linked=google_linked,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
            notification_preference=account.notification_preference.value,
        ),
        chat_sessions=exported_sessions,
        watchlist=[
            ExportWatchlistEntry(work_id=w.work_id, created_at=w.created_at) for w in watches
        ],
        notifications=[
            ExportNotification(
                id=n.id, work_id=n.work_id, trigger_type=n.trigger_type.value,
                trigger_document_id=n.trigger_document_id,
                trigger_jurisdiction=n.trigger_jurisdiction, created_at=n.created_at,
                read_at=n.read_at, emailed_at=n.emailed_at,
            )
            for n in notifications
        ],
    )
```

- [ ] **Step 5: Run the tests again to confirm everything passes**

Run: `accounts/.venv/bin/pytest accounts/tests/test_account_management.py -v`

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add accounts/src/normly_accounts/schemas.py accounts/src/normly_accounts/routers/account_management.py accounts/tests/test_account_management.py
git commit -s -m "fix(accounts): include watchlist and notifications in the account data export

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: License headers on the 10 pre-existing shadcn ui/ files

**Files:**
- Modify: `frontend/src/components/ui/collapsible.tsx`
- Modify: `frontend/src/components/ui/dropdown-menu.tsx`
- Modify: `frontend/src/components/ui/popover.tsx`
- Modify: `frontend/src/components/ui/scroll-area.tsx`
- Modify: `frontend/src/components/ui/separator.tsx`
- Modify: `frontend/src/components/ui/sheet.tsx`
- Modify: `frontend/src/components/ui/sidebar.tsx`
- Modify: `frontend/src/components/ui/skeleton.tsx`
- Modify: `frontend/src/components/ui/textarea.tsx`
- Modify: `frontend/src/components/ui/tooltip.tsx`

**Interfaces:**
- Consumes: nothing from another task in this plan.
- Produces: nothing another task in this plan depends on. Fully self-contained, purely mechanical, no behavior change.

**Context:** These 10 files are unmodified shadcn/ui-generated output that predates this repo's convention (established later, e.g. `input.tsx`/`button.tsx`/`pagination.tsx`) of adding a two-line AGPL header. The user has decided (this session) they get the exact same header as every other source file — no separate MIT-attribution treatment. 8 of the 10 files start with a `"use client";`-less `"use client"` directive (no trailing semicolon, confirmed byte-for-byte) as their literal first line, which Next.js requires to remain the first statement in the file — the header must go *after* that line, never before it.

- [ ] **Step 1: Insert the header into the two files with no `"use client"` directive**

`frontend/src/components/ui/skeleton.tsx` currently starts with:
```
import { cn } from "@/lib/utils"
```
Change the first line to:
```tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { cn } from "@/lib/utils"
```

`frontend/src/components/ui/textarea.tsx` currently starts with:
```
import * as React from "react"
```
Change the first line to:
```tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react"
```

- [ ] **Step 2: Insert the header after the `"use client"` line in the 8 remaining files**

For each of `collapsible.tsx`, `dropdown-menu.tsx`, `popover.tsx`, `scroll-area.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `tooltip.tsx`, the file currently starts with:
```
"use client"

import ...
```
Change it to:
```tsx
"use client"

// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import ...
```
(i.e. keep the `"use client"` line and its existing blank line exactly as they are, then insert the two comment lines plus one more blank line, then the first `import` line unchanged.)

- [ ] **Step 3: Verify every file in `ui/` now has the header, and nothing broke**

Run: `grep -L "SPDX-License-Identifier" frontend/src/components/ui/*.tsx`

Expected: empty output (no file is missing the header).

Run: `cd frontend && npx tsc --noEmit`

Expected: no errors (confirms no header was accidentally inserted before a `"use client"` directive, which would be a real Next.js build-time regression, not just a style nit).

Run: `cd frontend && npx vitest run`

Expected: the full existing suite still passes at its current count (no behavior touched by this task).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/collapsible.tsx frontend/src/components/ui/dropdown-menu.tsx frontend/src/components/ui/popover.tsx frontend/src/components/ui/scroll-area.tsx frontend/src/components/ui/separator.tsx frontend/src/components/ui/sheet.tsx frontend/src/components/ui/sidebar.tsx frontend/src/components/ui/skeleton.tsx frontend/src/components/ui/textarea.tsx frontend/src/components/ui/tooltip.tsx
git commit -s -m "chore(frontend): add missing AGPL license headers to pre-existing shadcn ui components

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Unread-notification badge on the bell icon

**Files:**
- Modify: `frontend/src/components/page-header.tsx`
- Test: `frontend/tests/unit/page-header.test.tsx`

**Interfaces:**
- Consumes: `useNotifications()` from `frontend/src/lib/use-notifications.ts`, which already returns `{ notifications, unreadCount, markRead, refresh }` (line 43 of that file) — `unreadCount` is computed there already and needs no change, only a new consumer.
- Produces: nothing another task in this plan depends on. Fully self-contained.

**Context:** `useNotifications()` already computes `unreadCount` but nothing in the frontend ever reads it (grep-confirmed zero consumers). `page-header.tsx`'s bell icon (`<Bell>` inside a `<Button>` inside `<PopoverTrigger>`) currently gives no visual indication of unread notifications outside the open popover.

- [ ] **Step 1: Write the failing test**

Add this test to `frontend/tests/unit/page-header.test.tsx`, inside the existing `describe("PageHeader", ...)` block, right after the `"lists real notifications and marks one read on click"` test:

```tsx
  it("shows an unread-count badge on the bell icon when there are unread notifications", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
            triggerJurisdiction: null, createdAt: "2026-01-15T00:00:00Z", readAt: null,
          },
          {
            id: "n2", workId: "w2", triggerType: "new_edition", triggerDocumentId: null,
            triggerJurisdiction: null, createdAt: "2026-01-14T00:00:00Z", readAt: "2026-01-15T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );

    renderPageHeader(<PageHeader titleKey="nav.chat" />);

    expect(await screen.findByTestId("unread-badge")).toHaveTextContent("1");
  });

  it("shows no unread-count badge when there are no unread notifications", async () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);

    await waitFor(() => {
      expect(screen.queryByTestId("unread-badge")).not.toBeInTheDocument();
    });
  });
```

(These reuse the file's own established mocking convention — `global.fetch` returning a raw `Response` with the notifications array — exactly like the existing `"lists real notifications..."` and `"shows an icon and a formatted date..."` tests already do, no new mock helper needed. The second test relies on `beforeEach`'s default `global.fetch` mock, which resolves to an empty array.)

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx`

Expected: `"shows an unread-count badge..."` FAILS (`findByTestId` times out — `data-testid="unread-badge"` doesn't exist yet). The "shows no unread-count badge..." test PASSES already (there's genuinely nothing there yet), which is fine — it's a regression guard for after the badge is added, not proof of anything on its own at this point.

- [ ] **Step 3: Implement the badge**

In `frontend/src/components/page-header.tsx`, change line 44 from:
```tsx
  const { notifications, markRead } = useNotifications();
```
to:
```tsx
  const { notifications, unreadCount, markRead } = useNotifications();
```

Replace the `PopoverTrigger` block (currently):
```tsx
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" aria-label={t("nav.notificationsLabel")}>
              <Bell className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
```
with:
```tsx
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="relative"
              aria-label={t("nav.notificationsLabel")}
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span
                  data-testid="unread-badge"
                  className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground"
                >
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Button>
          </PopoverTrigger>
```

- [ ] **Step 4: Run the tests again to confirm everything passes**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx`

Expected: all tests in this file PASS (10 total: 8 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/page-header.tsx frontend/tests/unit/page-header.test.tsx
git commit -s -m "feat(frontend): show an unread-count badge on the notifications bell

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Sidebar spacing artifact on the document-detail page

**Files:**
- Modify: `frontend/src/app/documents/[id]/document-detail-content.tsx`

**Interfaces:**
- Consumes: nothing from another task in this plan.
- Produces: nothing another task in this plan depends on. Fully self-contained, purely cosmetic.

**Context:** The sticky sidebar's rights-checklist card ends with a `<Separator className="my-4" />` right before its own closing `</div>` — a leftover from before the source-link `Button` was pulled out of this card (in sub-project 5's own final-review fix) to render as a sibling instead, so the source link survives a failed rights fetch. The separator no longer divides two things inside the card; it just leaves a dangling horizontal rule at the bottom-inside-edge.

- [ ] **Step 1: Delete the leftover separator**

In `frontend/src/app/documents/[id]/document-detail-content.tsx`, inside the sticky sidebar's rights card, remove this one line (currently sitting right after the `legal_basis_reference` paragraph, right before the card's closing `</div>`):

```tsx
              <Separator className="my-4" />
```

So the card's closing goes directly from the `legal_basis_reference` paragraph to `</div>`:

```tsx
              <p className="mt-3 text-xs text-muted-foreground">{rights.legal_basis_reference}</p>
            </div>
          )}
          <Button asChild size="sm" className="w-full">
```

If, after this deletion, `Separator` is no longer used anywhere else in this file, also remove its now-unused import line (check with `grep -n "Separator" frontend/src/app/documents/\[id\]/document-detail-content.tsx` — if the only remaining hit is the `import { Separator } from "@/components/ui/separator";` line itself, delete that import line too; `tsc --noEmit` in Step 2 would otherwise flag it as an unused import under this project's lint config, so don't skip this check).

- [ ] **Step 2: Run the existing test suite to confirm no regression**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`

Expected: all existing tests in this file PASS unchanged — this is a pure JSX deletion with no `data-testid` or behavioral involvement, so nothing here should need updating. If any test fails, the deletion removed more than the one intended line — re-check the diff against Step 1 before proceeding.

Also run: `cd frontend && npx tsc --noEmit`

Expected: no errors (confirms the `Separator` import cleanup, if it was needed, was done correctly).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/documents/\[id\]/document-detail-content.tsx
git commit -s -m "fix(frontend): remove leftover separator in the document-detail rights sidebar

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: StrictMode double-fetch guard on /magic-link and /verify-email

**Files:**
- Modify: `frontend/src/app/magic-link/magic-link-page-content.tsx`
- Modify: `frontend/src/app/verify-email/verify-email-content.tsx`

**Interfaces:**
- Consumes: nothing from another task in this plan.
- Produces: nothing another task in this plan depends on. Fully self-contained.

**Context:** Both pages already guard their token-consuming `fetch` with a `let cancelled = false; ... return () => { cancelled = true; }` pattern, but that only decides whose *response* wins the state update — it does not stop React StrictMode's dev-only double-invocation of the effect from firing the `fetch` itself a second time. Since both calls are one-shot and token-consuming (`POST /api/auth/magic-link/confirm`, `GET /api/auth/verify-email?token=...`), the second invocation's request can get rejected as "already used," which can flash "invalid link" for a token that in fact just succeeded on the first call — a `next dev`-only artifact, never seen in a production build, but confusing during local testing. Fix: add a `useRef` one-shot guard that stops the second invocation's effect body from ever calling `fetch` at all, additive to (not replacing) the existing `cancelled` guard.

- [ ] **Step 1: Add the ref guard to `magic-link-page-content.tsx`**

In `frontend/src/app/magic-link/magic-link-page-content.tsx`, inside `MagicLinkConfirm`, change:

```tsx
function MagicLinkConfirm({ token }: { token: string }) {
  const router = useRouter();
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"confirming" | "error">("confirming");

  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/magic-link/confirm", {
```

to:

```tsx
function MagicLinkConfirm({ token }: { token: string }) {
  const router = useRouter();
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"confirming" | "error">("confirming");
  const hasRunRef = React.useRef(false);

  React.useEffect(() => {
    if (hasRunRef.current) return;
    hasRunRef.current = true;
    let cancelled = false;
    fetch("/api/auth/magic-link/confirm", {
```

(Everything from that point on in the effect — the `method`/`headers`/`body`, the `.then`/`.catch` chain, and the `return () => { cancelled = true; }` cleanup — stays exactly as it already is.)

- [ ] **Step 2: Add the same ref guard to `verify-email-content.tsx`**

In `frontend/src/app/verify-email/verify-email-content.tsx`, inside `VerifyEmailStatus`, change:

```tsx
  const [status, setStatus] = React.useState<Status>(token ? "verifying" : "invalid");
  const [resendEmail, setResendEmail] = React.useState("");
  const [resendSent, setResendSent] = React.useState(false);
  const [isResending, setIsResending] = React.useState(false);

  React.useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`)
```

to:

```tsx
  const [status, setStatus] = React.useState<Status>(token ? "verifying" : "invalid");
  const [resendEmail, setResendEmail] = React.useState("");
  const [resendSent, setResendSent] = React.useState(false);
  const [isResending, setIsResending] = React.useState(false);
  const hasRunRef = React.useRef(false);

  React.useEffect(() => {
    if (!token) return;
    if (hasRunRef.current) return;
    hasRunRef.current = true;
    let cancelled = false;
    fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`)
```

(Everything from that point on in the effect — the `.then`/`.catch` chain and the `return () => { cancelled = true; }` cleanup — stays exactly as it already is. Note the `if (!token) return;` guard stays FIRST, before the ref check — an empty token should keep bailing out every render without ever flipping `hasRunRef.current`, matching the existing behavior for that case.)

- [ ] **Step 3: Run both pages' existing test suites to confirm no regression**

Run: `grep -rl "MagicLinkConfirm\|MagicLinkPageContent" frontend/tests/unit/` and `grep -rl "VerifyEmailStatus\|VerifyEmailContent" frontend/tests/unit/` to find the exact test file names (naming may not exactly match the component file names), then:

Run: `cd frontend && npx vitest run <path-to-magic-link-test-file> <path-to-verify-email-test-file>`

Expected: every existing test in both files still PASSES. In a single real render (the normal case these tests exercise, not StrictMode's double-invoke), `hasRunRef.current` starts `false`, so the new guard is a no-op — the `fetch` fires exactly once, exactly as before. If any test fails, check whether it renders the component twice itself (simulating StrictMode) and previously relied on the second render's fetch firing — that expectation would need to change, since preventing exactly that second fetch is this task's whole point.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/magic-link/magic-link-page-content.tsx frontend/src/app/verify-email/verify-email-content.tsx
git commit -s -m "fix(frontend): stop StrictMode from double-firing the magic-link and verify-email token requests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Final Whole-Branch Review

After all 6 tasks are done, dispatch the final whole-branch review per superpowers:subagent-driven-development (most capable available model). Points worth explicitly directing the reviewer to check, since they span more than one task or aren't visible from any single task's diff:

- Task 1 and Task 2 both touch `accounts/` — confirm nothing in Task 2's new export fields accidentally depends on Task 1's cookie change (they shouldn't; different endpoints entirely), and that `accounts/.venv/bin/pytest accounts/` (the whole suite, not just the two touched files) is still green.
- Task 3's mechanical header insertion and Task 4/5's edits to different frontend files don't overlap, but confirm `cd frontend && npx vitest run` (the whole suite) and `npx tsc --noEmit` are both green at the final combined `HEAD`, not just per-task.
- Re-confirm Task 2's notifications export genuinely omits the `EMAIL`-preference-hides-in-app-feed filter (i.e. re-read `export_account_data` at final `HEAD` and confirm it calls `PostgresNotificationRepository(session).list_for_account(account.id)` unconditionally, with no `if account.notification_preference == NotificationPreference.EMAIL: return []`-style guard anywhere near it) — this is the one place in this whole plan where copying a nearby pattern (from `notifications.py`) would have been the WRONG thing to do, so it's worth a dedicated check.
