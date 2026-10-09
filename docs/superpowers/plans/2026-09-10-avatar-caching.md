# Avatar Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline base64 `avatar_data_url` field with a cacheable `GET /v1/accounts/avatar` endpoint (ETag + conditional requests) and a matching frontend BFF proxy, so avatars are served as a normal browser-cacheable HTTP resource instead of being re-downloaded and re-embedded into every session/profile response.

**Architecture:** Backend gets one new Bearer-authenticated endpoint returning raw image bytes with an `ETag`; `AccountResponse`/`SessionValidationResponse` drop `avatar_data_url` in favor of a cheap `has_avatar: bool` (still needed for UI logic like the "remove avatar" button), while `ExportAccountFields` keeps the base64 field unchanged (GDPR export must stay self-contained). Frontend gets a matching `GET` handler on the existing avatar BFF route (cookie-auth, forwards `If-None-Match`), a redesigned shared `Avatar` component that renders `<img src="/api/account/avatar">` with an `onError` fallback to initials, and a small `avatarVersion` counter lifted to `AppShell` so the two simultaneously-mounted Avatar instances (sidebar `NavUser` and the profile overlay) both refresh together after an upload/delete.

**Tech Stack:** FastAPI (`Response`, `Request`, `HTTPException`), Pydantic schemas, pytest + `TestClient`; Next.js route handlers, React (`useState`), Vitest + Testing Library.

## Global Constraints

- Two-hop auth: the browser never holds the Bearer token, only an httpOnly session cookie; the frontend proxies with the Bearer token server-side (already the established pattern in this codebase).
- `ETag` is content-derived (`hashlib.sha256` of the image bytes), not timestamp-derived, wrapped in quotes per the HTTP spec.
- `Cache-Control: private, max-age=0, must-revalidate` on the backend endpoint.
- `avatar_data_url`/`avatarDataUrl` stays ONLY in `ExportAccountFields` (backend) — nowhere else. The frontend has no base64-avatar concept at all anymore.
- No change to `POST /avatar` / `DELETE /avatar`'s own backend logic (their response *shape* changes via the schema change, their behavior doesn't).
- No avatar resizing/format changes, no CDN/object-storage move — avatar bytes stay in Postgres exactly as today.
- DCO `Signed-off-by` via `git commit -s` (added automatically — never type a literal `Signed-off-by:` line), Conventional Commits, every commit ends with a `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
- Repository access only through the repository layer — already satisfied: the new endpoint reads `account.avatar_image`/`account.avatar_content_type` directly off the `Account` domain object `get_current_account` already loaded, no new repository method needed.
- AGPL-3.0 SPDX header preserved in every modified source file (already present everywhere touched).

---

## File Structure

- Modify `accounts/src/normly_accounts/schemas.py`: `avatar_data_url` → `has_avatar` on `AccountResponse`/`SessionValidationResponse` only.
- Modify `accounts/src/normly_accounts/routers/login.py`, `profile.py`, `session.py`: update their `AccountResponse`/`SessionValidationResponse` construction sites; `profile.py` also gains the new `GET /avatar` endpoint.
- Modify `accounts/tests/test_profile.py`, `test_account_lifecycle_e2e.py`: update existing avatar-related assertions; add new `GET /avatar` tests.
- Modify `frontend/src/lib/account-response.ts`: `avatarDataUrl`/`avatar_data_url` → `hasAvatar`/`has_avatar`.
- Modify `frontend/src/app/api/account/avatar/route.ts`: add a `GET` handler alongside the existing `POST`/`DELETE`.
- Modify `frontend/src/components/ui/avatar.tsx`: redesigned to render `/api/account/avatar` with an `avatarVersion`-based cache-bust and `onError` fallback.
- Modify `frontend/src/components/app-shell.tsx`, `profile-overlay.tsx`, `account/name-avatar-section.tsx`, `app-header.tsx`: wire the new `Avatar` API and the `avatarVersion` counter through.
- Modify ~14 frontend test files: mechanical mock renames plus a handful of real assertion updates (enumerated per task below).

---

### Task 1: Backend — `has_avatar` field, remove `avatar_data_url` from `AccountResponse`/`SessionValidationResponse`

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py:38` (`AccountResponse`), `:78` (`SessionValidationResponse`)
- Modify: `accounts/src/normly_accounts/routers/login.py:62-69` (`_create_session_response`)
- Modify: `accounts/src/normly_accounts/routers/profile.py:17,26-34` (`_account_response`)
- Modify: `accounts/src/normly_accounts/routers/session.py:17,58-64` (`validate_session`)
- Test: `accounts/tests/test_profile.py:155`, `accounts/tests/test_account_lifecycle_e2e.py:41`

**Interfaces:**
- Consumes: nothing from another task.
- Produces: `AccountResponse.has_avatar: bool` and `SessionValidationResponse.has_avatar: bool`, both `True` iff `account.avatar_image is not None`. Task 6 (frontend) depends on this field existing in the JSON the backend returns.

- [ ] **Step 1: Change the schemas**

In `accounts/src/normly_accounts/schemas.py`, in `AccountResponse` (starts line 32), change:
```python
    avatar_data_url: str | None
```
to:
```python
    has_avatar: bool
```
Do the identical replacement in `SessionValidationResponse` (starts line 73). Do NOT touch `ExportAccountFields` (line 106) — it keeps `avatar_data_url: str | None` unchanged.

- [ ] **Step 2: Update the three construction sites**



In `accounts/src/normly_accounts/routers/login.py`, `_create_session_response`'s `AccountResponse(...)` call (lines 62-69) currently reads:
```python
        account=AccountResponse(
            id=account.id, email=account.email,
            email_verified=account.email_verified_at is not None,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
            has_password=account.password_hash is not None,
            notification_preference=account.notification_preference.value,
        ),
```
Change `avatar_data_url=avatar_data_url(account),` to `has_avatar=account.avatar_image is not None,`. Do NOT remove the `avatar_data_url` helper function itself (lines 29-33 of this same file) — it's still used by `ExportAccountFields`'s construction in `account_management.py` (out of scope for this plan).

In `accounts/src/normly_accounts/routers/profile.py`, `_account_response` (lines 26-34) currently reads:
```python
def _account_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id, email=account.email,
        email_verified=account.email_verified_at is not None,
        first_name=account.first_name, last_name=account.last_name,
        avatar_data_url=avatar_data_url(account),
        has_password=account.password_hash is not None,
        notification_preference=account.notification_preference.value,
    )
```
Change `avatar_data_url=avatar_data_url(account),` to `has_avatar=account.avatar_image is not None,`. This makes the `from normly_accounts.routers.login import avatar_data_url` import on line 17 of this file unused — remove that import line. (Task 2 of this plan adds a new endpoint to this same file that does NOT need this helper either, so leave the import removed.)

In `accounts/src/normly_accounts/routers/session.py`, `validate_session`'s return (lines 58-64) currently reads:
```python
    return SessionValidationResponse(
        account_id=account.id, email=account.email,
        first_name=account.first_name, last_name=account.last_name,
        avatar_data_url=avatar_data_url(account),
        has_password=account.password_hash is not None,
        notification_preference=account.notification_preference.value,
    )
```
Change `avatar_data_url=avatar_data_url(account),` to `has_avatar=account.avatar_image is not None,`. This makes the `from normly_accounts.routers.login import avatar_data_url` import on line 17 of this file unused — remove it.

- [ ] **Step 3: Update the two existing tests this change breaks**

In `accounts/tests/test_profile.py`, `test_delete_avatar_clears_it` (line 144) currently ends with:
```python
    assert response.json()["avatar_data_url"] is None
```
Change to:
```python
    assert response.json()["has_avatar"] is False
```

In `accounts/tests/test_account_lifecycle_e2e.py`, around line 41:
```python
    assert avatar_upload.json()["avatar_data_url"] is not None
```
Change to:
```python
    assert avatar_upload.json()["has_avatar"] is True
```
Do NOT touch the other `avatar_data_url` assertion in this same file (around line 89, inside the export-flow check) — that's `ExportAccountFields`, out of scope.

(The third existing reference, `test_upload_avatar_resizes_to_256_and_returns_data_url` in `test_profile.py`, is handled entirely in Task 2 — it needs the new `GET /avatar` endpoint to exist to be rewritten meaningfully. Leave it untouched for now; it will still reference `avatar_data_url` and will FAIL after this task's schema change — that's expected and gets fixed in Task 2, not this one. If your test runner treats a failing test as blocking, that's fine — Task 2 immediately follows this one in the same branch history.)

- [ ] **Step 4: Run the tests**

Run: `cd accounts && .venv/bin/pytest tests/test_profile.py tests/test_account_lifecycle_e2e.py -v`

Expected: every test PASSES except `test_upload_avatar_resizes_to_256_and_returns_data_url`, which FAILS with a `KeyError: 'avatar_data_url'` — this is the expected, temporary state described in Step 3's note above, resolved in Task 2. Confirm no OTHER test fails.

- [ ] **Step 5: Commit**

```bash
git add accounts/src/normly_accounts/schemas.py accounts/src/normly_accounts/routers/login.py accounts/src/normly_accounts/routers/profile.py accounts/src/normly_accounts/routers/session.py accounts/tests/test_profile.py accounts/tests/test_account_lifecycle_e2e.py
git commit -s -m "$(cat <<'EOF'
feat(accounts): replace avatar_data_url with has_avatar on AccountResponse/SessionValidationResponse

Both responses fire on every session check and profile load, embedding
the full base64-encoded avatar on each call with no HTTP caching
possible for an inline data URI. A cheap has_avatar boolean is enough
for the frontend's remaining logic (the "remove avatar" button); the
actual image moves to a dedicated, cacheable endpoint (next commit).
ExportAccountFields is untouched -- the GDPR export must stay
self-contained.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Backend — new `GET /v1/accounts/avatar` endpoint

**Files:**
- Modify: `accounts/src/normly_accounts/routers/profile.py` (add the endpoint after `delete_avatar`, which currently ends the file at line 115)
- Test: `accounts/tests/test_profile.py`

**Interfaces:**
- Consumes: `AccountResponse.has_avatar` from Task 1 (used only in this task's rewritten upload test, not by the endpoint itself).
- Produces: `GET /v1/accounts/avatar` — 401 if unauthenticated, 404 if `account.avatar_image is None`, 304 if `If-None-Match` matches the current ETag, else 200 with the raw image bytes, `Content-Type`, `ETag`, and `Cache-Control` headers. Task 4 (frontend) proxies this endpoint.

- [ ] **Step 1: Write the failing tests**

In `accounts/tests/test_profile.py`, first DELETE the existing `test_upload_avatar_resizes_to_256_and_returns_data_url` (currently lines 85-101):
```python
def test_upload_avatar_resizes_to_256_and_returns_data_url(client):
    _, headers = _register_and_authorize(client)
    image_bytes = _make_test_image()

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", image_bytes, "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 200
    data_url = response.json()["avatar_data_url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    import base64
    stored = base64.b64decode(data_url.split(",", 1)[1])
    resized = Image.open(io.BytesIO(stored))
    assert resized.size == (256, 256)
```

Then add these tests where it was, right after `test_upload_avatar_rejects_a_truncated_image_instead_of_crashing` and before `test_delete_avatar_clears_it`:

```python
def test_upload_avatar_resizes_to_256_and_serves_it_via_the_avatar_endpoint(client):
    _, headers = _register_and_authorize(client)
    image_bytes = _make_test_image()

    upload_response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", image_bytes, "image/jpeg")},
        headers=headers,
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["has_avatar"] is True

    avatar_response = client.get("/v1/accounts/avatar", headers=headers)
    assert avatar_response.status_code == 200
    resized = Image.open(io.BytesIO(avatar_response.content))
    assert resized.size == (256, 256)
```

And, after the existing `test_delete_avatar_clears_it` (which now ends with `assert response.json()["has_avatar"] is False` per Task 1), before `test_update_notification_preference`:

```python
def test_get_avatar_returns_404_when_unset(client):
    _, headers = _register_and_authorize(client)

    response = client.get("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 404


def test_get_avatar_returns_the_image_with_correct_headers(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.get("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, max-age=0, must-revalidate"
    assert "etag" in response.headers
    resized = Image.open(io.BytesIO(response.content))
    assert resized.size == (256, 256)


def test_get_avatar_returns_304_when_if_none_match_matches(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )
    first = client.get("/v1/accounts/avatar", headers=headers)
    etag = first.headers["etag"]

    response = client.get(
        "/v1/accounts/avatar", headers={**headers, "If-None-Match": etag},
    )

    assert response.status_code == 304
    assert response.content == b""


def test_get_avatar_returns_200_when_if_none_match_does_not_match(client):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.get(
        "/v1/accounts/avatar", headers={**headers, "If-None-Match": '"stale-etag"'},
    )

    assert response.status_code == 200
    assert len(response.content) > 0


def test_get_avatar_requires_authorization(client):
    response = client.get("/v1/accounts/avatar")
    assert response.status_code == 401
```

`_register_and_authorize` and `_make_test_image` are this file's own existing helpers (top of file) — do not redefine them. `io` and `Image` are already imported at the top of this file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/pytest tests/test_profile.py -v -k "get_avatar or serves_it_via_the_avatar_endpoint"`

Expected: FAIL — `404 Not Found` (route doesn't exist yet) for every new test.

- [ ] **Step 3: Implement the endpoint**

In `accounts/src/normly_accounts/routers/profile.py`, change the top-level `fastapi` import (currently `from fastapi import APIRouter, Depends, File, HTTPException, UploadFile`) to:
```python
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
```
Add `import hashlib` near the top of the file, alongside the existing `import io`.

Add this function after `delete_avatar` (currently the last thing in the file, ending at line 115):

```python
@profile_router.get("/avatar")
def get_avatar(
    request: Request, account: Account = Depends(get_current_account),
) -> Response:
    if account.avatar_image is None:
        raise HTTPException(status_code=404, detail="no avatar set")

    etag = f'"{hashlib.sha256(account.avatar_image).hexdigest()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    return Response(
        content=account.avatar_image,
        media_type=account.avatar_content_type,
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=0, must-revalidate",
        },
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/pytest tests/test_profile.py -v`

Expected: PASS, every test in the file.

- [ ] **Step 5: Run the full accounts/ test suite**

Run: `cd accounts && .venv/bin/pytest tests/`

Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add accounts/src/normly_accounts/routers/profile.py accounts/tests/test_profile.py
git commit -s -m "$(cat <<'EOF'
feat(accounts): add GET /v1/accounts/avatar

Serves the raw avatar bytes directly, with a content-derived ETag and
conditional-request support (304 on a matching If-None-Match) -- the
piece that actually lets the browser cache an avatar instead of
re-fetching it embedded in every session/profile response.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Frontend — `hasAvatar` on `AccountSummary`, mechanical + logic test updates

**Files:**
- Modify: `frontend/src/lib/account-response.ts`
- Test: `frontend/tests/unit/account-response.test.ts`, `auth-routes.test.ts`, `account-profile-route.test.ts`, `account-avatar-route.test.ts` (rename only, new tests come in Task 4), `delete-account-section.test.tsx`, `email-section.test.tsx`, `notification-preference-section.test.tsx`, `document-detail-page.test.tsx`, `use-account-session.test.ts`, `app-shell.test.tsx`, `app-header.test.tsx`, `profile-overlay.test.tsx`

**Interfaces:**
- Consumes: `has_avatar: bool` from Task 1's backend response shape.
- Produces: `AccountSummary.hasAvatar: boolean` and `RawAccountFields.has_avatar: boolean`. Tasks 4 and 6 both read `AccountSummary.hasAvatar`.

This task's own type change breaks compilation of every file below in one step — they must all be fixed together for the frontend to type-check at any point in this branch's history. None of the mechanical renames below change test behavior.

- [ ] **Step 1: Change the type and mapper**

In `frontend/src/lib/account-response.ts`:
- `AccountSummary` interface: change `avatarDataUrl: string | null;` (line 15) to `hasAvatar: boolean;` (same position).
- `RawAccountFields` interface: change `avatar_data_url: string | null;` (line 23) to `has_avatar: boolean;` (same position).
- `mapAccountSummary`'s return object: change `avatarDataUrl: raw.avatar_data_url,` (line 33) to `hasAvatar: raw.has_avatar,`.

- [ ] **Step 2: Update `account-response.test.ts` (real logic, not mechanical)**

Replace the full file content with:

```typescript
// frontend/tests/unit/account-response.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { mapAccountSummary } from "@/lib/account-response";

describe("mapAccountSummary", () => {
  it("maps the backend's snake_case fields to the frontend's camelCase shape", () => {
    const result = mapAccountSummary("acc-1", "a@example.de", {
      first_name: "Jamie", last_name: "Tester", has_avatar: true,
      has_password: true, notification_preference: "immediate",
    });

    expect(result).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Tester",
      hasAvatar: true, hasPassword: true,
      notificationPreference: "immediate",
    });
  });

  it("preserves null fields", () => {
    const result = mapAccountSummary("acc-2", "b@example.de", {
      first_name: null, last_name: null, has_avatar: false, has_password: false,
      notification_preference: "none",
    });

    expect(result.firstName).toBeNull();
    expect(result.lastName).toBeNull();
    expect(result.hasAvatar).toBe(false);
    expect(result.hasPassword).toBe(false);
  });

  it("echoes the notification preference from the raw fields", () => {
    const result = mapAccountSummary("acc-3", "c@example.de", {
      first_name: null, last_name: null, has_avatar: false, has_password: false,
      notification_preference: "digest",
    });

    expect(result.notificationPreference).toBe("digest");
  });
});
```

- [ ] **Step 3: Update `auth-routes.test.ts`**

Around line 122, the mocked backend session response body has `avatar_data_url: null,` — change to `has_avatar: false,`. Around line 141, the assertion `.toEqual({..., avatarDataUrl: null, ...})` — change `avatarDataUrl: null,` to `hasAvatar: false,` in that object.

- [ ] **Step 4: Update `account-profile-route.test.ts`**

Around line 23, the mocked backend response body has `avatar_data_url: null,` — change to `has_avatar: false,`. Around line 35, the assertion `.toEqual({..., avatarDataUrl: null,})` — change to `hasAvatar: false,`.

- [ ] **Step 5: Update `account-avatar-route.test.ts` (rename only — new GET tests come in Task 4)**

- Line 30: mock POST response body `avatar_data_url: "data:image/jpeg;base64,xyz",` → `has_avatar: true,`.
- Line 45: `expect(body.avatarDataUrl).toBe("data:image/jpeg;base64,xyz");` → `expect(body.hasAvatar).toBe(true);`.
- Line 75: mock DELETE response body `avatar_data_url: null,` → `has_avatar: false,`.
- Line 88: `expect(body.avatarDataUrl).toBeNull();` → `expect(body.hasAvatar).toBe(false);`.

- [ ] **Step 6: Mechanical renames — mock `AccountSummary` objects that don't test avatar behavior**

In each file below, change every `avatarDataUrl: null,` to `hasAvatar: false,` (these are all camelCase `AccountSummary`-shaped mocks, not raw backend bodies — confirm each site is indeed camelCase before editing, per the file list):

- `frontend/tests/unit/delete-account-section.test.tsx`: lines 15, 20.
- `frontend/tests/unit/email-section.test.tsx`: line 15.
- `frontend/tests/unit/notification-preference-section.test.tsx`: line 16.
- `frontend/tests/unit/document-detail-page.test.tsx`: lines 298, 327, 346, 370 (4 occurrences).
- `frontend/tests/unit/app-shell.test.tsx`: lines 69, 118, 159 (3 occurrences) — these are inside mocked `/api/auth/session` fetch response bodies (camelCase, since that's the BFF's own JSON shape), so `avatarDataUrl: null,` → `hasAvatar: false,`.
- `frontend/tests/unit/app-header.test.tsx`: line 70 — same shape, `avatarDataUrl: null,` → `hasAvatar: false,`.
- `frontend/tests/unit/use-account-session.test.ts`: lines 22, 38, 60 (3 occurrences) — also inside mocked `/api/auth/session` fetch response bodies, camelCase: `avatarDataUrl: null,` → `hasAvatar: false,`.
- `frontend/tests/unit/profile-overlay.test.tsx`: line 18 — inside the file's shared `ACCOUNT: AccountSummary` constant, `avatarDataUrl: null,` → `hasAvatar: false,`.

- [ ] **Step 7: Run the frontend test suite**

Run: `cd frontend && npm run test`

Expected: some failures remain — `avatar.test.tsx` (Task 5 rewrites it), `name-avatar-section.test.tsx` and `app-shell.test.tsx`'s two overlay-related tests and `profile-overlay.test.tsx` (Task 6 updates the component props these tests exercise), and `account-avatar-route.test.ts` will pass (no new GET tests added yet, that's fine). Confirm every test file EXCEPT `avatar.test.tsx`, `name-avatar-section.test.tsx`, and any test that renders `<AppShell>`/`<ProfileOverlay>`/`<NameAvatarSection>` and touches avatar-specific behavior now passes. If something outside that expected list fails, investigate before proceeding — don't assume it's expected.

Run: `cd frontend && npx tsc --noEmit`

Expected: type errors only in `frontend/src/components/ui/avatar.tsx`, `app-shell.tsx`, `app-header.tsx`, `name-avatar-section.tsx`, `profile-overlay.tsx` (all fixed in Tasks 5-6) — no type errors anywhere else. If `account-response.ts` or any of the files touched in this task still show errors, fix them before committing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/account-response.ts frontend/tests/unit/account-response.test.ts frontend/tests/unit/auth-routes.test.ts frontend/tests/unit/account-profile-route.test.ts frontend/tests/unit/account-avatar-route.test.ts frontend/tests/unit/delete-account-section.test.tsx frontend/tests/unit/email-section.test.tsx frontend/tests/unit/notification-preference-section.test.tsx frontend/tests/unit/document-detail-page.test.tsx frontend/tests/unit/app-shell.test.tsx frontend/tests/unit/app-header.test.tsx frontend/tests/unit/use-account-session.test.ts frontend/tests/unit/profile-overlay.test.tsx
git commit -s -m "$(cat <<'EOF'
feat(frontend): replace avatarDataUrl with hasAvatar on AccountSummary

Mirrors the backend's AccountResponse/SessionValidationResponse change
(has_avatar replacing avatar_data_url). The actual image moves to a
dedicated, cacheable endpoint wired up in the next two commits;
hasAvatar is only needed for the "remove avatar" button's visibility.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Frontend — new `GET` handler in `avatar/route.ts`

**Files:**
- Modify: `frontend/src/app/api/account/avatar/route.ts`
- Test: `frontend/tests/unit/account-avatar-route.test.ts`

**Interfaces:**
- Consumes: nothing new from another task (uses the existing `readSessionCookies`/`getBackendUrls` helpers already imported in this file).
- Produces: `GET /api/account/avatar` — 401 without a session cookie, forwards `If-None-Match`, passes through backend 304/404, streams backend 200 with `Content-Type`/`ETag`/`Cache-Control`. Task 5's redesigned `Avatar` component references this URL directly as an `<img src>`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/tests/unit/account-avatar-route.test.ts` (inside the existing `describe("avatar BFF route", () => { ... })` block, after the `DELETE` test):

```typescript
  it("GET streams the image with its headers when the backend returns 200", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    const imageBytes = new Uint8Array([1, 2, 3, 4]);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(imageBytes, {
        status: 200,
        headers: {
          "content-type": "image/jpeg",
          "etag": '"abc123"',
          "cache-control": "private, max-age=0, must-revalidate",
        },
      }),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/jpeg");
    expect(response.headers.get("etag")).toBe('"abc123"');
    const body = new Uint8Array(await response.arrayBuffer());
    expect(Array.from(body)).toEqual([1, 2, 3, 4]);
  });

  it("GET returns 304 with no body when the backend returns 304", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 304 }));

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok", "if-none-match": '"abc123"' },
    });
    const response = await GET(request);

    expect(response.status).toBe(304);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["If-None-Match"]).toBe('"abc123"');
  });

  it("GET returns 404 when the backend has no avatar set", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "no avatar set" }), { status: 404 }),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);

    expect(response.status).toBe(404);
  });

  it("GET requires a session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/avatar");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
```

Change the file's import line from `import { POST, DELETE } from "@/app/api/account/avatar/route";` to `import { GET, POST, DELETE } from "@/app/api/account/avatar/route";`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm run test -- account-avatar-route.test.ts`

Expected: FAIL — `GET` is not exported by the route module yet (`TypeError: GET is not a function` or similar import error).

- [ ] **Step 3: Implement the handler**

In `frontend/src/app/api/account/avatar/route.ts`, add this export (alongside the existing `POST`/`DELETE`):

```typescript
export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${accountSessionToken}` };
  const ifNoneMatch = request.headers.get("if-none-match");
  if (ifNoneMatch) {
    headers["If-None-Match"] = ifNoneMatch;
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    headers,
    cache: "no-store",
  });

  if (backendResponse.status === 304) {
    return new NextResponse(null, { status: 304 });
  }
  if (backendResponse.status === 404) {
    return NextResponse.json({ detail: "no avatar set" }, { status: 404 });
  }

  const body = await backendResponse.arrayBuffer();
  return new NextResponse(body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": backendResponse.headers.get("content-type") ?? "application/octet-stream",
      "ETag": backendResponse.headers.get("etag") ?? "",
      "Cache-Control":
        backendResponse.headers.get("cache-control") ?? "private, max-age=0, must-revalidate",
    },
  });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm run test -- account-avatar-route.test.ts`

Expected: PASS, all tests in the file (existing POST/DELETE tests plus the 4 new GET ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/api/account/avatar/route.ts frontend/tests/unit/account-avatar-route.test.ts
git commit -s -m "$(cat <<'EOF'
feat(frontend): add GET handler to the avatar BFF route

Proxies the backend's new GET /v1/accounts/avatar with cookie auth,
forwarding If-None-Match so the conditional-request chain (browser ->
frontend -> backend) works end to end instead of the frontend always
re-fetching even when the browser already has a fresh copy.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Frontend — redesign the shared `Avatar` component

**Files:**
- Modify: `frontend/src/components/ui/avatar.tsx`
- Test: `frontend/tests/unit/avatar.test.tsx`

**Interfaces:**
- Consumes: `GET /api/account/avatar` from Task 4 (referenced by URL, not imported).
- Produces: `Avatar({ avatarVersion?: number; firstName: string | null; lastName: string | null; email: string; size?: number })`. Task 6 wires `avatarVersion` through from `AppShell`.

- [ ] **Step 1: Write the failing tests**

Replace `frontend/tests/unit/avatar.test.tsx` entirely with:

```typescript
// frontend/tests/unit/avatar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Avatar } from "@/components/ui/avatar";

describe("Avatar", () => {
  it("renders an img pointed at the avatar endpoint", () => {
    render(<Avatar firstName="Jamie" lastName="Tester" email="a@example.de" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar");
  });

  it("includes the avatarVersion as a cache-busting query param when set", () => {
    render(
      <Avatar avatarVersion={3} firstName="Jamie" lastName="Tester" email="a@example.de" />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar?v=3");
  });

  it("falls back to initials when the image fails to load", () => {
    render(<Avatar firstName="Jamie" lastName="Tester" email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("JT")).toBeInTheDocument();
  });

  it("falls back to the first letter of the email when no name is set", () => {
    render(<Avatar firstName={null} lastName={null} email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm run test -- avatar.test.tsx`

Expected: FAIL — the current component still requires an `avatarDataUrl` prop and renders differently.

- [ ] **Step 3: Rewrite the component**

Replace `frontend/src/components/ui/avatar.tsx` entirely with:

```typescript
// frontend/src/components/ui/avatar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

function initialsFor(
  firstName: string | null, lastName: string | null, email: string,
): string {
  if (firstName && lastName) return `${firstName[0]}${lastName[0]}`.toUpperCase();
  if (firstName) return firstName[0].toUpperCase();
  if (lastName) return lastName[0].toUpperCase();
  return (email[0] ?? "?").toUpperCase();
}

export function Avatar({
  avatarVersion = 0, firstName, lastName, email, size = 32,
}: {
  avatarVersion?: number;
  firstName: string | null;
  lastName: string | null;
  email: string;
  size?: number;
}) {
  const [imageFailed, setImageFailed] = React.useState(false);

  if (!imageFailed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- this is a
      // same-origin BFF route (/api/account/avatar), not a remote URL
      // next/image's optimizer could help with, and the avatarVersion query
      // param changes on every upload/removal, which next/image handles
      // awkwardly for a URL that intentionally varies per session.
      //
      // alt is a real, non-empty string on purpose: alt="" gives the <img>
      // an implicit ARIA role of "presentation" instead of "img", which
      // both real screen readers and getByRole("img") in tests would then
      // skip entirely.
      //
      // onError covers both "no avatar set" (backend 404) and any other
      // fetch failure -- both cases fall back to the same initials display
      // this component already used before this endpoint existed.
      <img
        key={avatarVersion}
        src={
          avatarVersion === 0 ? "/api/account/avatar" : `/api/account/avatar?v=${avatarVersion}`
        }
        alt="Profilbild" className="rounded-full object-cover"
        style={{ width: size, height: size }}
        onError={() => setImageFailed(true)}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium"
      style={{ width: size, height: size }}
    >
      {initialsFor(firstName, lastName, email)}
    </span>
  );
}
```

`imageFailed` is local state — it does NOT reset just because `avatarVersion` changes (the `key={avatarVersion}` here is on the inner `<img>`, which only remounts the `<img>` itself, not this component's own state). Task 6 handles the retry-after-upload case at the call site, by putting `key={avatarVersion}` on the `<Avatar>` element itself wherever an upload can happen — forcing the whole component to remount and reset `imageFailed`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm run test -- avatar.test.tsx`

Expected: PASS, all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/avatar.tsx frontend/tests/unit/avatar.test.tsx
git commit -s -m "$(cat <<'EOF'
feat(frontend): render Avatar from /api/account/avatar with onError fallback

Replaces the inline avatarDataUrl prop with a direct <img
src="/api/account/avatar"> reference plus an optional avatarVersion
cache-busting query param -- the browser's own HTTP cache (ETag/304,
wired up in the prior two commits) now does the caching instead of
this component re-embedding base64 on every render. A 404 (no avatar
set) falls back to the initials display via the same onError path as
any other load failure.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Frontend — wire `avatarVersion` through `AppShell`, update `NameAvatarSection` and `AppHeader`

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`, `profile-overlay.tsx`, `account/name-avatar-section.tsx`, `app-header.tsx`
- Test: `frontend/tests/unit/name-avatar-section.test.tsx`, `app-shell.test.tsx`, `profile-overlay.test.tsx`

**Interfaces:**
- Consumes: `Avatar({ avatarVersion, ... })` from Task 5; `AccountSummary.hasAvatar` from Task 3.
- Produces: nothing a later task consumes — this is the last task.

`NavUser` and `ProfileOverlay` are both rendered simultaneously inside `AppShell`, sharing one `useAccountSession()` call — `AppShell` is where the shared `avatarVersion` counter belongs so both Avatar instances refresh together after an upload/delete. `AppHeader` is a separate top-level layout (used on pages without a sidebar) with no upload capability of its own; its `Avatar` intentionally gets no `avatarVersion` wiring at all (defaults to `0`) — a documented, accepted scope boundary: after uploading elsewhere, `AppHeader`'s own avatar only refreshes on a full page reload, not live.

- [ ] **Step 1: Wire `avatarVersion` through `AppShell`**

In `frontend/src/components/app-shell.tsx`:

`NavUser`'s props type (currently):
```typescript
function NavUser({
  account,
  logout,
  onOpenProfile,
}: {
  account: AccountSummary | null;
  logout: () => Promise<void>;
  onOpenProfile: () => void;
}) {
```
becomes:
```typescript
function NavUser({
  account,
  avatarVersion,
  logout,
  onOpenProfile,
}: {
  account: AccountSummary | null;
  avatarVersion: number;
  logout: () => Promise<void>;
  onOpenProfile: () => void;
}) {
```

`NavUser`'s `<Avatar>` call (currently):
```typescript
              <Avatar
                avatarDataUrl={account.avatarDataUrl}
                firstName={account.firstName}
                lastName={account.lastName}
                email={account.email}
              />
```
becomes:
```typescript
              <Avatar
                key={avatarVersion}
                avatarVersion={avatarVersion}
                firstName={account.firstName}
                lastName={account.lastName}
                email={account.email}
              />
```

In `AppShell` itself, add a new state variable alongside the existing `profileOpen` one (currently `const [profileOpen, setProfileOpen] = React.useState(false);`):
```typescript
  const [profileOpen, setProfileOpen] = React.useState(false);
  const [avatarVersion, setAvatarVersion] = React.useState(0);
```

`AppShell`'s `<NavUser .../>` render (currently):
```typescript
          <NavUser
            account={account}
            logout={logout}
            onOpenProfile={() => setProfileOpen(true)}
          />
```
becomes:
```typescript
          <NavUser
            account={account}
            avatarVersion={avatarVersion}
            logout={logout}
            onOpenProfile={() => setProfileOpen(true)}
          />
```

`AppShell`'s `<ProfileOverlay .../>` render (currently):
```typescript
      <ProfileOverlay
        open={profileOpen}
        onOpenChange={setProfileOpen}
        account={account}
        setAccount={setAccount}
      />
```
becomes:
```typescript
      <ProfileOverlay
        open={profileOpen}
        onOpenChange={setProfileOpen}
        account={account}
        setAccount={setAccount}
        avatarVersion={avatarVersion}
        onAvatarChange={() => setAvatarVersion((v) => v + 1)}
      />
```

- [ ] **Step 2: Thread `avatarVersion`/`onAvatarChange` through `ProfileOverlay`**

In `frontend/src/components/account/profile-overlay.tsx`, `ProfileOverlay`'s props type (currently):
```typescript
export function ProfileOverlay({
  open,
  onOpenChange,
  account,
  setAccount,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account: AccountSummary | null;
  setAccount: React.Dispatch<React.SetStateAction<AccountSummary | null>>;
}) {
```
becomes:
```typescript
export function ProfileOverlay({
  open,
  onOpenChange,
  account,
  setAccount,
  avatarVersion,
  onAvatarChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account: AccountSummary | null;
  setAccount: React.Dispatch<React.SetStateAction<AccountSummary | null>>;
  avatarVersion: number;
  onAvatarChange: () => void;
}) {
```

Its `NameAvatarSection` render (currently `<NameAvatarSection account={account} onAccountUpdated={setAccount} />`) becomes:
```typescript
                <NameAvatarSection
                  account={account} onAccountUpdated={setAccount}
                  avatarVersion={avatarVersion} onAvatarChange={onAvatarChange}
                />
```

- [ ] **Step 3: Update `NameAvatarSection`**

In `frontend/src/components/account/name-avatar-section.tsx`, the props type (currently):
```typescript
export function NameAvatarSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
```
becomes:
```typescript
export function NameAvatarSection({
  account, onAccountUpdated, avatarVersion, onAvatarChange,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
  avatarVersion: number;
  onAvatarChange: () => void;
}) {
```

In `uploadAvatar`, the success branch currently reads:
```typescript
      if (response.ok) {
        setAvatarStatus("idle");
        onAccountUpdated(await response.json());
      } else {
```
Add `onAvatarChange();` right after `onAccountUpdated(await response.json());`:
```typescript
      if (response.ok) {
        setAvatarStatus("idle");
        onAccountUpdated(await response.json());
        onAvatarChange();
      } else {
```

Do the identical addition in `removeAvatar`'s success branch (same pattern: `onAccountUpdated(await response.json());` followed immediately by `onAvatarChange();`).

The `<Avatar>` call (currently):
```typescript
        <Avatar
          avatarDataUrl={account.avatarDataUrl} firstName={account.firstName}
          lastName={account.lastName} email={account.email} size={64}
        />
```
becomes:
```typescript
        <Avatar
          key={avatarVersion} avatarVersion={avatarVersion} firstName={account.firstName}
          lastName={account.lastName} email={account.email} size={64}
        />
```

The remove-button visibility condition (currently `{account.avatarDataUrl && (`) becomes `{account.hasAvatar && (`.

- [ ] **Step 4: Update `AppHeader`**

In `frontend/src/components/app-header.tsx`, the `<Avatar>` call (currently):
```typescript
              <Avatar
                avatarDataUrl={account.avatarDataUrl} firstName={account.firstName}
                lastName={account.lastName} email={account.email}
              />
```
becomes (drop the avatar-image prop entirely, no replacement — `avatarVersion` defaults to `0`):
```typescript
              <Avatar
                firstName={account.firstName}
                lastName={account.lastName} email={account.email}
              />
```

- [ ] **Step 5: Update `name-avatar-section.test.tsx`**

The shared `account` mock (currently lines 13-16, already updated to `hasAvatar: false,` by Task 3):
```typescript
const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  hasAvatar: false, hasPassword: true, notificationPreference: "immediate",
};
```
No further change needed here — Task 3 already handled this rename.

Every `render(<NameAvatarSection account={...} onAccountUpdated={...} />)` call in this file (6 occurrences, one per `it()` block) needs `avatarVersion={0} onAvatarChange={vi.fn()}` added, e.g.:
```typescript
      <LocaleProvider initialLocale="de">
        <NameAvatarSection
          account={account} onAccountUpdated={onAccountUpdated}
          avatarVersion={0} onAvatarChange={vi.fn()}
        />
      </LocaleProvider>,
```
(adjust each call's exact existing prop values — `account`/`onAccountUpdated` vary per test — only ADD the two new props, don't change the existing ones.)

The upload-success test (currently around lines 23-47) mocks the POST response body with `avatarDataUrl: null` (around line 29) — this is the BFF proxy's own camelCase response shape (already `hasAvatar` after Task 3/4) — if this specific line wasn't already caught by Task 3's mechanical sweep (it targets `AccountSummary` object literals specifically, and this one is a JSON.stringify'd mock response body, a different shape), change it to `hasAvatar: false` now.

The test at (originally) line 49, `"shows a remove button only when an avatar is already set"`, already uses the shared `account` object (now `hasAvatar: false`) and asserts the remove button is absent — no change needed beyond the props addition above, since `NameAvatarSection` now reads `account.hasAvatar` per Step 3.

The test that builds `accountWithAvatar` (originally `{ ...account, avatarDataUrl: "data:image/png;base64,abc" }`, around line 119) — if not already renamed by Task 3 (it's a spread of the shared `account`, may not have been caught by a literal-string grep) — change to `{ ...account, hasAvatar: true }`.

- [ ] **Step 6: Update `app-shell.test.tsx` and `profile-overlay.test.tsx`**

In `frontend/tests/unit/app-shell.test.tsx`, the test `"opens the profile overlay instead of navigating when Konto is clicked"` and `"shares a single useAccountSession() call between NavUser and ProfileOverlay"` both render the full `<AppShell>` and open the overlay — since `AppShell` now owns `avatarVersion` internally (not a prop these tests pass in), no test-level prop changes are needed for these two; just confirm they still pass after Steps 1-4 (the internal wiring is opaque to a test that only interacts via `render`/`fireEvent`/`screen`).

In `frontend/tests/unit/profile-overlay.test.tsx`, the `renderOverlay` helper (currently):
```typescript
function renderOverlay(account: AccountSummary | null, open = true) {
  return render(
    <LocaleProvider initialLocale="de">
      <ProfileOverlay open={open} onOpenChange={vi.fn()} account={account} setAccount={vi.fn()} />
    </LocaleProvider>,
  );
}
```
becomes:
```typescript
function renderOverlay(account: AccountSummary | null, open = true) {
  return render(
    <LocaleProvider initialLocale="de">
      <ProfileOverlay
        open={open} onOpenChange={vi.fn()} account={account} setAccount={vi.fn()}
        avatarVersion={0} onAvatarChange={vi.fn()}
      />
    </LocaleProvider>,
  );
}
```
This one change covers all 5 `it()` blocks in the file, since they all call `renderOverlay`.

- [ ] **Step 7: Run the full frontend gate**

Run: `cd frontend && npm run test`

Expected: PASS, every test in the suite.

Run: `cd frontend && npx tsc --noEmit`

Expected: clean, no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/app-shell.tsx frontend/src/components/account/profile-overlay.tsx frontend/src/components/account/name-avatar-section.tsx frontend/src/components/app-header.tsx frontend/tests/unit/name-avatar-section.test.tsx frontend/tests/unit/profile-overlay.test.tsx
git commit -s -m "$(cat <<'EOF'
feat(frontend): wire avatarVersion through AppShell, drop avatarDataUrl everywhere

AppShell owns a single avatarVersion counter shared by NavUser and
ProfileOverlay (both mounted simultaneously, sharing one
useAccountSession() call) so both Avatar instances refresh together
after an upload or removal. NameAvatarSection's "remove avatar" button
now keys off hasAvatar instead of the removed avatarDataUrl.
AppHeader's own Avatar instance is deliberately left unwired -- it has
no upload capability of its own and only needs to reflect a change on
the next full page load, not live.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** Backend `GET /v1/accounts/avatar` (raw bytes, ETag, 304, 404, `Cache-Control`) → Task 2, code copied verbatim from the spec. Frontend `GET /api/account/avatar` (cookie auth, `If-None-Match` passthrough, 304/404 passthrough, streaming) → Task 4, verbatim from the spec. Response schema changes (`avatar_data_url` removed from `AccountResponse`/`SessionValidationResponse`, kept in `ExportAccountFields`) → Task 1. Frontend avatar rendering (`<img src="/api/account/avatar">`, `onError` fallback to initials, cache-busting after upload/delete) → Tasks 5-6. The spec's own two named usage sites (`app-shell.tsx`'s `NavUser`, `name-avatar-section.tsx`) are covered by Task 6; a third site the spec didn't mention (`app-header.tsx`) was found during grounding and is also covered, with its scope boundary (no live sync) explicitly called out and user-confirmed. The `has_avatar`/`avatarVersion` additions are the two user-confirmed grounding discoveries beyond the spec's literal text — both documented inline at their point of introduction (Task 1 Step 1, Task 6 preamble). Out-of-scope items (no `POST`/`DELETE` logic change, no resizing/format change, no CDN move) — no task touches any of them.

**Placeholder scan:** No TBD/TODO; every step has literal code or an exact command.

**Type consistency:** `has_avatar: bool` (backend, Task 1) ↔ `has_avatar: boolean` (frontend raw field, Task 3) ↔ `hasAvatar: boolean` (frontend mapped field, Task 3, consumed by Task 6's `account.hasAvatar` check) — consistent naming and type across the boundary. `Avatar({ avatarVersion?: number; ... })` defined once in Task 5, consumed identically in Task 6 (`NavUser`, `NameAvatarSection`) and left at its default in `AppHeader`. `GET /v1/accounts/avatar` (Task 2) and its frontend proxy `GET /api/account/avatar` (Task 4) agree on status codes (401/404/304/200) and header names (`Content-Type`/`ETag`/`Cache-Control`).
