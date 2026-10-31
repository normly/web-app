# User management — residuals and frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the known residuals of the user-management backend and build the admin panel, the invitation page and the blocked notices, so that issue #60 ships as one PR.

**Architecture:** Part A changes three backend sign-in paths in the accounts service (lock order, legacy Google accounts, magic-link reset). Part B adds a Next.js admin page at `/admin/users` that talks to the accounts admin API through one catch-all BFF proxy (`/api/admin/[...path]`), a typed client (`lib/admin-api.ts`), URL-driven list state, four dialogs, a role-matrix dialog, an `/invitation` accept page and blocked notices on the sign-in paths.

**Tech Stack:** FastAPI/SQLAlchemy/pytest (Part A); Next.js 16 App Router, React 19, Tailwind 3, shadcn-style components on Radix, vitest + Testing Library, Playwright (Part B).

**Spec:** [`docs/superpowers/specs/2026-10-31-user-management-design.md`](../specs/2026-10-31-user-management-design.md). Backend plan (done): [`2026-10-31-user-management-backend.md`](2026-10-31-user-management-backend.md).

## Global Constraints

- Branch `feature/60-user-management` (already checked out). Never switch branches, push, or run `git config`.
- Every new source file starts with the license header: Python `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# Copyright (C) 2026 normly contributors`; TS/TSX `// SPDX-License-Identifier: AGPL-3.0-or-later` + `// Copyright (C) 2026 normly contributors` (frontend files additionally start with a `// frontend/src/...` path comment, like their neighbours).
- Commits: Conventional Commits, `git commit -s`, trailers `Refs: #60` and `Assisted-by: Claude Code`; never `Co-Authored-By`.
- Backend: all SQL in `core/src/normly_core/graph/postgres/repositories.py`; new Protocol methods named `get_*`/`list_*` need a `JURISDICTION_EXEMPT_READS` entry in `core/tests/graph/test_architecture.py`; accounts answers validation errors with 400.
- Backend tests: `cd core && ../.venv/bin/pytest …`, `cd accounts && ../.venv/bin/pytest …` (Docker must run). Frontend unit tests: `cd frontend && npx vitest run <file>`; full: `cd frontend && npm test`; type check: `cd frontend && npx tsc --noEmit`; build: `cd frontend && npm run build`.
- Frontend: Tailwind **v3** syntax only (no v4 shorthand like `w-(--x)`); no new npm dependencies (no TanStack Table, no new Radix packages) — use the existing `components/ui/*` and plain elements.
- All UI text through `t()` with keys present in **both** `de.json` and `en.json` (same shape; `TranslationKey` derives from `de.json`).
- All table columns left-aligned (`text-left`). Badges carry text, not only colour. Sort buttons expose `aria-sort` on the `<th>`.
- Error detail codes from the backend (exact strings) are mapped to `admin.errors.<code>`: `last_administrator`, `self_action`, `upgrade_requires_invitation`, `not_a_publisher`, `account_blocked`, `already_blocked`, `not_blocked`, `publisher_name_taken`, `unknown_publisher`, `confirmation_mismatch`, `invitation_invalid`, `forbidden`; anything else → `admin.errors.generic`.
- Page sizes 10/20/50 (default 10). Sort keys: `email, first_name, last_name, sign_in, role, publisher, last_login_at, created_at, status`.
- Contact address for blocked notices: `NORMLY_CONTACT_EMAIL`, else `NORMLY_IMPRINT_URL`, else no contact line.

## Product-owner decisions for Part A (2026-10-31)

1. **Lock order.** Every path takes database locks in one order: administrator rows → account row → token rows. No deadlocks between accept, the admin panel, e-mail-change confirm and magic-link confirm.
2. **Legacy Google accounts.** When an invitation is accepted for an *unverified* account that has a Google link, only credentials are reset (sessions, password, Google link, tokens); content stays. Unverified accounts without a Google link keep the full reset (credentials + content).
3. **Magic link.** When a magic-link sign-in confirms a previously unverified, already existing account, all its other credentials are reset (sessions, password, Google link, tokens); content stays. The account is then verified.

## File Structure

| File | Responsibility |
|---|---|
| `accounts/src/normly_accounts/routers/invitation.py` (modify) | Lock order; Google-linked accounts keep content |
| `accounts/src/normly_accounts/routers/email_change.py` (modify) | Lock the account before consuming the token |
| `accounts/src/normly_accounts/routers/magic_link.py` (modify) | Lock order; reset credentials of an unverified existing account |
| `accounts/src/normly_accounts/credentials.py` (create) | `reset_credentials(session, account_id)` shared by accept and magic link |
| `core/src/normly_core/graph/{domain.py,postgres/repositories.py}` (modify) | `AccountTokenRepository.find_unconsumed_token` |
| `frontend/src/lib/account-response.ts`, `src/app/api/auth/session/route.ts` (modify) | `role`, `publisherId` in the session |
| `frontend/src/components/app-shell.tsx` (modify) | Administrator sidebar group |
| `frontend/src/lib/config.ts` (modify) | `contactAddress` |
| `frontend/src/app/api/admin/[...path]/route.ts` (create) | Catch-all BFF proxy to `/v1/admin/*` |
| `frontend/src/app/api/auth/invitation/accept/route.ts` (create) | Accept + session cookie |
| `frontend/src/lib/admin-api.ts` (create) | Typed client, snake→camel mapping, `AdminApiError` |
| `frontend/src/lib/admin-users-query.ts` (create) | URL ⇄ list query (pure functions + hook) |
| `frontend/src/lib/admin-format.ts` (create) | Number and date formatting |
| `frontend/src/components/ui/native-select.tsx` (create) | Styled native `<select>` |
| `frontend/src/components/admin/*.tsx` (create) | Badges, summary cards, toolbar, table, pagination, row actions, dialogs, role matrix |
| `frontend/src/app/admin/users/{page.tsx,user-management-content.tsx}` (create) | The page |
| `frontend/src/app/invitation/{page.tsx,invitation-page-content.tsx}` (create) | Accept page |
| `frontend/src/components/auth/blocked-notice.tsx` (create) | Blocked notice with contact |
| `frontend/src/middleware.ts` (modify) | `/admin/*` without session cookie → `/login` |
| `frontend/src/lib/i18n/{de,en}.json` (modify) | All new copy |
| `compose.yaml` (modify) | Pass `NORMLY_CONTACT_EMAIL`, `NORMLY_IMPRINT_URL` to the frontend |

---

## Part A — backend residuals

### Task 1: Shared credential reset and one lock order

**Files:**
- Create: `accounts/src/normly_accounts/credentials.py`
- Modify: `core/src/normly_core/graph/domain.py` (`AccountTokenRepository`), `core/src/normly_core/graph/postgres/repositories.py` (`PostgresAccountTokenRepository`)
- Modify: `accounts/src/normly_accounts/routers/invitation.py`, `accounts/src/normly_accounts/routers/email_change.py`
- Test: `accounts/tests/test_lock_order.py` (create), `core/tests/graph/test_account_token_lookup.py` (create)

**Interfaces:**
- Produces: `PostgresAccountTokenRepository.find_unconsumed_token(token: str, purpose: AccountTokenPurpose) -> AccountToken | None` (no lock, ignores used/expired tokens); `normly_accounts.credentials.reset_credentials(session, account_id) -> None` (deletes sessions, Google links, account-bound tokens; clears the password hash).

- [ ] **Step 1: Write the failing core test**

`core/tests/graph/test_account_token_lookup.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

NOW = datetime.now(timezone.utc)


def test_find_unconsumed_token_ignores_used_expired_and_other_purposes(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="lookup@example.de", password_hash=None
    )
    tokens = PostgresAccountTokenRepository(db_session)
    tokens.create_token(account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK,
                        token="live", created_at=NOW, expires_at=NOW + timedelta(minutes=5))
    tokens.create_token(account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK,
                        token="old", created_at=NOW, expires_at=NOW - timedelta(minutes=1))

    found = tokens.find_unconsumed_token("live", AccountTokenPurpose.MAGIC_LINK)
    assert found is not None and found.account_id == account.id
    assert tokens.find_unconsumed_token("live", AccountTokenPurpose.PASSWORD_RESET) is None
    assert tokens.find_unconsumed_token("old", AccountTokenPurpose.MAGIC_LINK) is None
    tokens.consume_token("live", AccountTokenPurpose.MAGIC_LINK)
    assert tokens.find_unconsumed_token("live", AccountTokenPurpose.MAGIC_LINK) is None
```

- [ ] **Step 2: Run it and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_account_token_lookup.py -v`
Expected: FAIL with `AttributeError: … has no attribute 'find_unconsumed_token'`.

- [ ] **Step 3: Implement the lookup**

Add to the `AccountTokenRepository` Protocol in `domain.py`:

```python
    def find_unconsumed_token(
        self, token: str, purpose: AccountTokenPurpose
    ) -> AccountToken | None:
        """An unused, unexpired token without locking it; consume_token still decides."""
        ...
```

Implement in `PostgresAccountTokenRepository` next to `consume_token`, reusing its `_token_to_domain`-style mapper (use whatever function `consume_token` uses to build the domain object):

```python
    def find_unconsumed_token(
        self, token: str, purpose: AccountTokenPurpose
    ) -> AccountToken | None:
        orm = self._session.execute(
            select(AccountTokenORM).where(
                AccountTokenORM.token == token,
                AccountTokenORM.purpose == purpose,
                AccountTokenORM.used_at.is_(None),
                AccountTokenORM.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()
        return _account_token_to_domain(orm) if orm else None
```

(If the existing mapper has a different name, use that one.)

- [ ] **Step 4: Extract the credential reset**

`accounts/src/normly_accounts/credentials.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Resetting the sign-in data of an account whose mailbox was never proven (ADR-030)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
)


def reset_credentials(session: Session, account_id: uuid.UUID) -> None:
    """
    Every way in that whoever registered the address may hold: sessions,
    Google links, open tokens and the password. The caller holds the account
    row lock (lock order: administrator rows, account row, token rows).
    """
    PostgresAccountSessionRepository(session).delete_sessions_for_account(account_id)
    PostgresAccountGoogleIdentityRepository(session).unlink_all_for_account(account_id)
    PostgresAccountTokenRepository(session).delete_for_account(account_id)
    PostgresAccountRepository(session).clear_password_hash(account_id)
```

In `routers/invitation.py`, replace the four reset calls with `reset_credentials(session, account.id)` (keep `reset_unverified_account_content` for now — Task 2 changes when it runs).

- [ ] **Step 5: Write the failing lock-order tests**

`accounts/tests/test_lock_order.py`. They record the order in which the handlers take locks by wrapping the repository methods; the expected order is administrator rows → account row → token rows.

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""One lock order on every path: administrator rows, account row, token rows."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from normly_core.graph.domain import AccountTokenPurpose, Role
from normly_core.graph.postgres import repositories as repos
from normly_core.graph.postgres.repositories import (
    PostgresAccountTokenRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import make_account, make_admin


@pytest.fixture()
def lock_log(monkeypatch):
    log: list[str] = []

    def wrap(cls, name, label):
        original = getattr(cls, name)

        def recorder(self, *args, **kwargs):
            log.append(label)
            return original(self, *args, **kwargs)

        monkeypatch.setattr(cls, name, recorder)

    wrap(repos.PostgresAccountRepository, "lock_active_administrator_ids", "admins")
    wrap(repos.PostgresAccountRepository, "lock_account", "account")
    wrap(repos.PostgresAccountTokenRepository, "consume_token", "token")
    wrap(repos.PostgresAccountTokenRepository, "delete_for_account", "token")
    return log


def _first_positions(log):
    return {label: log.index(label) for label in set(log)}


def test_accept_for_an_unverified_administrator_locks_admins_before_the_account(
    client, db_session, lock_log
):
    _, headers = make_admin(db_session)
    unverified_admin = make_account(db_session, "unverified-admin@example.de",
                                    role=Role.ADMINISTRATOR, password="correct horse")
    client.post("/v1/admin/invitations", headers=headers,
                json={"email": unverified_admin.email, "role": "user"})
    token = PostgresInvitationRepository(db_session).get_invitation_by_email(
        unverified_admin.email
    ).token
    lock_log.clear()

    client.post("/v1/accounts/invitations/accept", json={"token": token})

    first = _first_positions(lock_log)
    assert first["admins"] < first["account"] < first["token"]


def test_email_change_confirm_locks_the_account_before_the_token(client, db_session, lock_log):
    account = make_account(db_session, "mover@example.de", password="correct horse")
    now = datetime.now(timezone.utc)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=account.id, email="moved@example.de",
        purpose=AccountTokenPurpose.EMAIL_CHANGE, token="change-tok",
        created_at=now, expires_at=now + timedelta(hours=1),
    )
    lock_log.clear()

    response = client.get("/v1/accounts/email/confirm", params={"token": "change-tok"})

    assert response.status_code == 200
    first = _first_positions(lock_log)
    assert first["account"] < first["token"]
```

Adapt the `create_token` keyword arguments to the signature introduced by the e-mail-change fix (commit `3b1eada`) if it differs; the test intent stays.

- [ ] **Step 6: Run and see them fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_lock_order.py -v`
Expected: both FAIL (`KeyError: 'admins'` or a wrong order).

- [ ] **Step 7: Fix the order**

`routers/invitation.py` — before locking the pre-registered account:

```python
    if pre_registered and account.email_verified_at is None:
        if account.role is Role.ADMINISTRATOR:
            # Lock order (ADR-030): administrator rows first, like the admin
            # panel, then the account row, then its tokens.
            accounts.lock_active_administrator_ids()
        account = accounts.lock_account(account.id)
```

`routers/email_change.py` `confirm_email_change` — look the token up without a lock, lock its account, then consume:

```python
    tokens = PostgresAccountTokenRepository(session)
    pending = tokens.find_unconsumed_token(token, AccountTokenPurpose.EMAIL_CHANGE)
    if pending is None or pending.account_id is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    # Lock order (ADR-030): account row before token rows, like invitation accept.
    PostgresAccountRepository(session).lock_account(pending.account_id)
    consumed = tokens.consume_token(token, AccountTokenPurpose.EMAIL_CHANGE)
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
```

Keep the rest of the confirm handler (address from the token, query-parameter check, 409 on a taken address) unchanged.

- [ ] **Step 8: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest tests/test_lock_order.py tests/test_invitation_accept.py tests/test_invitation_races.py tests/test_email_change.py -v` and `cd core && ../.venv/bin/pytest tests/graph/test_account_token_lookup.py tests/graph/test_architecture.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add accounts core
git commit -s -m "fix(accounts): take locks in one order on every sign-in path" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 2: Google-linked unverified accounts keep their content on accept

**Files:**
- Modify: `accounts/src/normly_accounts/routers/invitation.py`
- Modify: `docs/adr/README.md` (ADR-030 consent bullet), `docs/srs/03-requirements.md` (REQ-ACC-006 statement)
- Test: `accounts/tests/test_invitation_accept.py` (append)

**Interfaces:**
- Consumes: `PostgresAccountGoogleIdentityRepository.has_google_identity(account_id) -> bool`, `reset_credentials` (Task 1).

- [ ] **Step 1: Write the failing test** (append)

```python
def test_an_unverified_google_linked_account_keeps_its_content_on_accept(client, db_session):
    from normly_core.graph.postgres.repositories import (
        PostgresAccountGoogleIdentityRepository,
        PostgresWatchlistRepository,
    )

    _, headers = make_admin(db_session)
    colleague = make_account(db_session, "legacy-google@example.de")
    accounts = PostgresAccountRepository(db_session)
    accounts.update_profile_names(colleague.id, first_name="Lea", last_name="Brandt")
    google = PostgresAccountGoogleIdentityRepository(db_session)
    google.link_google_identity(account_id=colleague.id, google_subject_id="legacy-sub")
    token = _invite(client, headers, db_session, colleague.email, role="user")

    response = client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert response.status_code == 200
    after = accounts.get_account_by_id(colleague.id)
    assert (after.first_name, after.last_name) == ("Lea", "Brandt")
    assert after.email_verified_at is not None
    assert not google.has_google_identity(colleague.id)  # credentials still reset
```

If `make_account` creates verified accounts in your helper, make sure this account is unverified (the helper creates unverified accounts by default — `create_account` sets no `email_verified_at`).

- [ ] **Step 2: Run and see it fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_invitation_accept.py::test_an_unverified_google_linked_account_keeps_its_content_on_accept -v`
Expected: FAIL (`first_name` is `None` — content was wiped).

- [ ] **Step 3: Implement**

In `routers/invitation.py`, inside `if credentials_reset:`:

```python
    if credentials_reset:
        # A Google link on an unverified account almost always means a real
        # owner who signed in with Google before such sign-ins marked the
        # address verified: keep their content, reset only the way in.
        google_linked = PostgresAccountGoogleIdentityRepository(session).has_google_identity(
            account.id
        )
        reset_credentials(session, account.id)
        if not google_linked:
            accounts.reset_unverified_account_content(account.id, locale=invitation.locale)
```

Add `"content_reset": credentials_reset and not google_linked` to the audit `details` (initialise `google_linked = False` before the `if`).

- [ ] **Step 4: Docs**

ADR-030 consent bullet and REQ-ACC-006 statement: replace the content-reset sentence with "…its sign-in data is reset; its content is deleted too unless the account has a Google link (a real owner who signed in with Google before Google sign-ins verified the address)."

- [ ] **Step 5: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest tests/test_invitation_accept.py tests/test_invitation_races.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add accounts docs
git commit -s -m "fix(accounts): keep the content of a Google-linked account on accept" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 3: Magic link resets the credentials of an unverified existing account

**Files:**
- Modify: `accounts/src/normly_accounts/routers/magic_link.py` (`confirm_magic_link`)
- Modify: `docs/adr/README.md` (ADR-030), `docs/srs/03-requirements.md` (REQ-ACC-006)
- Test: `accounts/tests/test_magic_link.py` (append), `accounts/tests/test_lock_order.py` (append)

**Interfaces:**
- Consumes: `find_unconsumed_token`, `lock_account`, `reset_credentials` (Task 1).

- [ ] **Step 1: Write the failing tests**

Append to `accounts/tests/test_magic_link.py`:

```python
def test_magic_link_on_an_unverified_account_resets_the_registrants_credentials(
    client, db_session
):
    client.post("/v1/accounts/register",
                json={"email": "squatted@example.de", "password": "correct horse"})
    squatter = client.post("/v1/accounts/login",
                           json={"email": "squatted@example.de", "password": "correct horse"})
    squatter_headers = {"Authorization": f"Bearer {squatter.json()['session_token']}"}

    client.post("/v1/accounts/magic-link/request", json={"email": "squatted@example.de"})
    token = _magic_link_token(db_session, "squatted@example.de")
    confirmed = client.post("/v1/accounts/magic-link/confirm", json={"token": token})

    assert confirmed.status_code == 200
    assert client.get("/v1/accounts/session", headers=squatter_headers).status_code == 401
    assert client.post("/v1/accounts/login", json={
        "email": "squatted@example.de", "password": "correct horse",
    }).status_code == 401
    owner = {"Authorization": f"Bearer {confirmed.json()['session_token']}"}
    assert client.get("/v1/accounts/session", headers=owner).status_code == 200


def test_magic_link_on_a_verified_account_keeps_password_and_sessions(client, db_session):
    from datetime import datetime, timezone

    client.post("/v1/accounts/register",
                json={"email": "verified-ml@example.de", "password": "correct horse"})
    account = PostgresAccountRepository(db_session).get_account_by_email("verified-ml@example.de")
    PostgresAccountRepository(db_session).mark_email_verified(account.id, datetime.now(timezone.utc))
    first = client.post("/v1/accounts/login",
                        json={"email": "verified-ml@example.de", "password": "correct horse"})

    client.post("/v1/accounts/magic-link/request", json={"email": "verified-ml@example.de"})
    token = _magic_link_token(db_session, "verified-ml@example.de")
    client.post("/v1/accounts/magic-link/confirm", json={"token": token})

    headers = {"Authorization": f"Bearer {first.json()['session_token']}"}
    assert client.get("/v1/accounts/session", headers=headers).status_code == 200
```

Append to `accounts/tests/test_lock_order.py`:

```python
def test_magic_link_confirm_locks_the_account_before_the_token(client, db_session, lock_log):
    make_account(db_session, "ml-order@example.de", password="correct horse")
    client.post("/v1/accounts/magic-link/request", json={"email": "ml-order@example.de"})
    from tests.test_magic_link import _magic_link_token

    token = _magic_link_token(db_session, "ml-order@example.de")
    lock_log.clear()

    assert client.post("/v1/accounts/magic-link/confirm", json={"token": token}).status_code == 200
    first = _first_positions(lock_log)
    assert first["account"] < first["token"]
```

- [ ] **Step 2: Run and see them fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_magic_link.py tests/test_lock_order.py -v`
Expected: the squatter test FAILS (old session still 200); the lock-order test FAILS (`KeyError: 'account'`).

- [ ] **Step 3: Implement**

Rewrite `confirm_magic_link` in `routers/magic_link.py`:

```python
@magic_link_router.post("/confirm", response_model=SessionResponse)
def confirm_magic_link(
    payload: MagicLinkConfirmRequest, session: Session = Depends(get_session),
) -> SessionResponse:
    tokens = PostgresAccountTokenRepository(session)
    account_repo = PostgresAccountRepository(session)

    pending = tokens.find_unconsumed_token(payload.token, AccountTokenPurpose.MAGIC_LINK)
    if pending is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    existing = (
        account_repo.get_account_by_id(pending.account_id)
        if pending.account_id is not None
        else account_repo.get_account_by_email(pending.email)
    )
    if existing is not None:
        # Lock order (ADR-030): account row before token rows.
        existing = account_repo.lock_account(existing.id)

    consumed = tokens.consume_token(payload.token, AccountTokenPurpose.MAGIC_LINK)
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    account = existing
    if account is None:
        # The token named a bare address, and following the link has just
        # proven the mailbox readable -- so this, not the request, is where
        # the account comes into being.
        assert consumed.email is not None  # ck_account_token_account_or_email
        account = account_repo.create_account(
            email=consumed.email, password_hash=None, locale=payload.locale,
        )
    elif account.email_verified_at is None and account.blocked_at is None:
        # The mailbox is proven only now. Whoever registered the address
        # before may not be its owner: their way in goes, the content stays
        # (ADR-030). A blocked account is refused below without changes.
        reset_credentials(session, account.id)

    if account.email_verified_at is None and account.blocked_at is None:
        account_repo.mark_email_verified(account.id, datetime.now(timezone.utc))
    account = account_repo.get_account_by_id(account.id)

    return _create_session_response(account, session)
```

Keep the existing comments about verification where they still apply. Import `reset_credentials` from `normly_accounts.credentials`.

- [ ] **Step 4: Docs**

ADR-030 consent bullet: add "A magic-link sign-in that first proves the mailbox of an existing, unverified account resets that account's other sign-in data the same way; its content stays." REQ-ACC-006: add the same rule in one clause.

- [ ] **Step 5: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest -q`
Expected: PASS (whole accounts suite — magic-link flows are used by many tests).

- [ ] **Step 6: Commit**

```bash
git add accounts docs
git commit -s -m "fix(accounts): reset an unverified account's credentials on magic-link sign-in" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

## Part B — frontend

### Task 4: Role in the session, administrator menu, contact config, middleware

**Files:**
- Modify: `frontend/src/lib/account-response.ts`, `frontend/src/app/api/auth/session/route.ts`
- Modify: `frontend/src/components/app-shell.tsx`
- Modify: `frontend/src/lib/config.ts`, `frontend/src/middleware.ts`, `compose.yaml`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/app-shell.test.tsx` (append), `frontend/tests/unit/config.test.ts` (append), `frontend/tests/unit/middleware.test.ts` (create or append if it exists)

**Interfaces:**
- Produces: `AccountSummary.role: "user" | "publisher" | "administrator"`, `AccountSummary.publisherId: string | null`; `InstanceConfig.contactAddress: string | null`; i18n keys `nav.administrator`, `nav.userManagement`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/tests/unit/app-shell.test.tsx` (inside the `describe`):

```tsx
  it("shows the administrator group only to administrators", async () => {
    const account = (role: string) => ({
      accountId: "1", email: "a@example.de", firstName: null, lastName: null,
      hasAvatar: false, hasPassword: true, notificationPreference: "none",
      role, publisherId: null,
    });
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account: account("administrator") })),
    );
    const { unmount } = render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}><div>content</div></AppShell>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Nutzermanagement" })).toHaveAttribute(
        "href", "/admin/users",
      ),
    );
    expect(screen.getByText("Administrator")).toBeInTheDocument();
    unmount();

    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account: account("publisher") })),
    );
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}><div>content</div></AppShell>
      </LocaleProvider>,
    );
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: "Nutzermanagement" })).not.toBeInTheDocument();
  });
```

Append to `frontend/tests/unit/config.test.ts` (follow its existing env-stubbing style):

```ts
  it("prefers NORMLY_CONTACT_EMAIL, then the imprint URL, for the contact address", () => {
    vi.stubEnv("NORMLY_CONTACT_EMAIL", "kontakt@normly.example");
    vi.stubEnv("NORMLY_IMPRINT_URL", "https://normly.example/impressum");
    expect(getInstanceConfig().contactAddress).toBe("kontakt@normly.example");
    vi.stubEnv("NORMLY_CONTACT_EMAIL", "");
    expect(getInstanceConfig().contactAddress).toBe("https://normly.example/impressum");
    vi.stubEnv("NORMLY_IMPRINT_URL", "");
    expect(getInstanceConfig().contactAddress).toBeNull();
  });
```

`frontend/tests/unit/middleware.test.ts`:

```ts
// frontend/tests/unit/middleware.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

describe("middleware", () => {
  it("sends /admin/* without an account session to /login", () => {
    const response = middleware(new NextRequest("http://localhost/admin/users"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/login");
  });

  it("lets /admin/* through with an account session cookie", () => {
    const response = middleware(new NextRequest("http://localhost/admin/users", {
      headers: { cookie: "normly_account_session=tok" },
    }));
    expect(response.headers.get("location")).toBeNull();
  });
});
```

(If `tests/unit/middleware.test.ts` already exists, append the two cases instead.)

- [ ] **Step 2: Run and see them fail**

Run: `cd frontend && npx vitest run tests/unit/app-shell.test.tsx tests/unit/config.test.ts tests/unit/middleware.test.ts`
Expected: FAIL (no admin link, `contactAddress` undefined, no redirect).

- [ ] **Step 3: Session fields**

`account-response.ts`:

```ts
export type AccountRole = "user" | "publisher" | "administrator";

export interface AccountSummary {
  accountId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  hasAvatar: boolean;
  hasPassword: boolean;
  notificationPreference: string;
  // Only decides what the menu shows; the server checks the role again on
  // every admin request.
  role: AccountRole;
  publisherId: string | null;
}

interface RawAccountFields {
  first_name: string | null;
  last_name: string | null;
  has_avatar: boolean;
  has_password: boolean;
  notification_preference: string;
  role?: AccountRole;
  publisher_id?: string | null;
}

export function mapAccountSummary(
  accountId: string, email: string, raw: RawAccountFields,
): AccountSummary {
  return {
    accountId, email, firstName: raw.first_name, lastName: raw.last_name,
    hasAvatar: raw.has_avatar, hasPassword: raw.has_password,
    notificationPreference: raw.notification_preference,
    role: raw.role ?? "user", publisherId: raw.publisher_id ?? null,
  };
}
```

`role`/`publisher_id` are optional on the raw type because other routes (profile, avatar) reuse the mapper with bodies that do not carry them; they default to `"user"`/`null`. Check every caller of `mapAccountSummary` (`grep -rn mapAccountSummary src`) and fix any type errors (`npx tsc --noEmit`). Existing tests that compare whole objects (e.g. `account-profile-route.test.ts`) must be updated to include `role: "user", publisherId: null` only if they now fail.

- [ ] **Step 4: Sidebar**

In `app-shell.tsx` import `Users` from `lucide-react` and `SidebarGroupLabel` from `@/components/ui/sidebar` (it exists in the shadcn sidebar; if not exported there, render the label as `<div className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground group-data-[collapsible=icon]:hidden">`). After the first `SidebarGroup`:

```tsx
          {account?.role === "administrator" && (
            <SidebarGroup>
              <SidebarGroupLabel>{t("nav.administrator")}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      asChild
                      isActive={pathname.startsWith("/admin/users")}
                      tooltip={t("nav.userManagement")}
                    >
                      <Link href="/admin/users">
                        <Users className="size-4" />
                        <span>{t("nav.userManagement")}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
```

i18n — add to `nav` in `de.json`: `"administrator": "Administrator", "userManagement": "Nutzermanagement"`; in `en.json`: `"administrator": "Administrator", "userManagement": "User management"`.

- [ ] **Step 5: Contact config, middleware, compose**

`config.ts`: add `contactAddress: string | null;` to `InstanceConfig` (comment: "Named in blocked notices; NORMLY_CONTACT_EMAIL, else the imprint URL.") and in `getInstanceConfig()`:

```ts
    contactAddress:
      process.env.NORMLY_CONTACT_EMAIL || process.env.NORMLY_IMPRINT_URL || null,
```

`middleware.ts` — at the top of `middleware()`:

```ts
  // UX only: without a session the admin page cannot show anything. The
  // accounts service checks the role on every admin request regardless.
  if (
    request.nextUrl.pathname.startsWith("/admin")
    && !request.cookies.get("normly_account_session")
  ) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
```

`compose.yaml` — in the `frontend` service's `environment:` add `NORMLY_CONTACT_EMAIL: ${NORMLY_CONTACT_EMAIL:-}` and `NORMLY_IMPRINT_URL: ${NORMLY_IMPRINT_URL:-}` (skip a key that is already there).

- [ ] **Step 6: Run the tests and the type check**

Run: `cd frontend && npx vitest run tests/unit/app-shell.test.tsx tests/unit/config.test.ts tests/unit/middleware.test.ts && npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend compose.yaml
git commit -s -m "feat(frontend): show the administrator menu to administrators" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 5: Admin copy, BFF proxy, typed client, formatting and query state

**Files:**
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json` (new top-level `admin` and `invitation` objects; `auth` and `account` additions)
- Create: `frontend/src/app/api/admin/[...path]/route.ts`, `frontend/src/app/api/auth/invitation/accept/route.ts`
- Create: `frontend/src/lib/admin-api.ts`, `frontend/src/lib/admin-format.ts`, `frontend/src/lib/admin-users-query.ts`
- Test: `frontend/tests/unit/admin-proxy-route.test.ts`, `frontend/tests/unit/admin-api.test.ts`, `frontend/tests/unit/admin-format.test.ts`, `frontend/tests/unit/admin-users-query.test.ts`, `frontend/tests/unit/invitation-accept-route.test.ts` (all create)

**Interfaces:**
- Produces (used by Tasks 6–10):
  - `adminApi` with `listUsers(query: UsersQuery): Promise<AdminUserPage>`, `summary(): Promise<AdminSummary>`, `publishers(): Promise<Publisher[]>`, `createPublisher(name: string): Promise<Publisher>`, `checkInvitation(email: string): Promise<InvitationCheck>`, `invite(input: InviteInput): Promise<{ emailSent: boolean }>`, `resendInvitation(id: string): Promise<{ emailSent: boolean }>`, `withdrawInvitation(id: string): Promise<void>`, `downgradeToUser(id: string): Promise<void>`, `changePublisher(id: string, publisherId: string): Promise<void>`, `block(id: string, reason: BlockReason): Promise<{ emailSent: boolean }>`, `unblock(id: string): Promise<void>`, `remove(id: string, confirmEmail: string): Promise<{ emailSent: boolean }>`, `roleMatrix(): Promise<RoleMatrix>`.
  - Types `Role`, `UserStatus`, `BlockReason`, `AdminUserRow`, `AdminUserPage`, `AdminSummary`, `Publisher`, `InvitationCheck`, `InviteInput`, `RoleMatrix`, `UsersQuery`, `SortKey`; class `AdminApiError { status: number; code: string }`; `errorKey(error: unknown): TranslationKey`.
  - `formatNumber(n, locale)`, `formatDate(iso, locale)`, `formatDateTime(iso, locale)`, `formatLastLogin(iso | null, locale, t, now?)`.
  - `parseUsersQuery(params: URLSearchParams): UsersQuery`, `serializeUsersQuery(q: UsersQuery): string`, `useUsersQuery(): { query: UsersQuery; update(patch: Partial<UsersQuery>): void }` (any change except `page` resets `page` to 1).
  - BFF: `/api/admin/<path>` forwards method, query and JSON body to `/v1/admin/<path>`; `/api/auth/invitation/accept` POST sets the session cookie on success.

- [ ] **Step 1: Add the copy**

Add to `de.json` (top level, next to `account`):

```json
"admin": {
  "inviteButton": "Nutzer einladen",
  "noAccess": "Kein Zugriff. Diese Seite ist Administratoren vorbehalten.",
  "loadError": "Die Daten konnten nicht geladen werden.",
  "summary": {
    "accountsTotal": "Konten gesamt",
    "activeHint": "davon {count} in den letzten 30 Tagen aktiv",
    "publishers": "Mit Rolle Publisher",
    "publishersHint": "{publishers} Verlage · {invitations} Einladungen offen",
    "administrators": "Mit Rolle Administrator",
    "administratorsHint": "Zugriff auf das Nutzermanagement",
    "blocked": "Gesperrt",
    "blockedHint": "häufigster Grund: {reason}",
    "blockedNone": "keine gesperrten Konten"
  },
  "tabs": { "all": "Alle", "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
  "status": {
    "label": "Status", "all": "Alle Status", "active": "Aktiv", "invited": "Eingeladen",
    "expired": "Abgelaufen", "blocked": "Gesperrt"
  },
  "searchPlaceholder": "E-Mail oder Name suchen …",
  "searchLabel": "Konten durchsuchen",
  "columns": {
    "account": "Konto", "firstName": "Vorname", "lastName": "Nachname", "signIn": "Anmeldung",
    "role": "Rolle", "publisher": "Zuordnung", "lastLogin": "Letzte Anmeldung",
    "createdAt": "Konto seit", "status": "Status", "actions": "Aktionen"
  },
  "signIn": { "email": "E-Mail", "google": "Google" },
  "never": "noch nie",
  "today": "heute {time}",
  "yesterday": "gestern {time}",
  "roles": { "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
  "blockReasons": {
    "bulk_retrieval": "Massenabruf", "abuse": "Missbrauch",
    "terms_violation": "Verstoß gegen Nutzungsbedingungen", "other": "Sonstiges"
  },
  "pagination": {
    "showing": "Zeige {from} bis {to} von {total} Zeilen",
    "rowsPerPage": "Zeilen pro Seite",
    "page": "Seite {page} von {pages}",
    "first": "Erste Seite", "previous": "Vorherige Seite",
    "next": "Nächste Seite", "last": "Letzte Seite"
  },
  "empty": "Keine Einträge gefunden.",
  "actions": {
    "menu": "Aktionen für {email}", "edit": "Bearbeiten", "block": "Sperren",
    "unblock": "Entsperren", "remove": "Entfernen", "resend": "Erneut senden",
    "withdraw": "Zurückziehen"
  },
  "edit": {
    "title": "Konto bearbeiten",
    "upgradeHint": "Höhere Rollen werden per Einladung vergeben.",
    "publisher": "Verlag",
    "downgrade": "Auf User zurückstufen",
    "save": "Speichern",
    "cancel": "Abbrechen"
  },
  "block": {
    "title": "Konto sperren",
    "description": "{email} wird sofort abgemeldet und kann sich nicht mehr anmelden. Die Person erhält eine neutrale E-Mail ohne Angabe des Grundes.",
    "reason": "Grund",
    "confirm": "Sperren",
    "cancel": "Abbrechen"
  },
  "remove": {
    "title": "Konto entfernen",
    "description": "Das Konto {email} und alle zugehörigen Daten werden endgültig gelöscht. Bei Missbrauch besser sperren: Eine entfernte Adresse kann sich neu registrieren.",
    "confirmLabel": "Zur Bestätigung die E-Mail-Adresse eingeben",
    "confirm": "Endgültig entfernen",
    "cancel": "Abbrechen"
  },
  "invite": {
    "title": "Nutzer einladen",
    "email": "E-Mail-Adresse",
    "emailPlaceholder": "name@verlag.de",
    "role": "Rolle",
    "publisher": "Verlagszuordnung",
    "publisherPlaceholder": "Verlag wählen",
    "newPublisher": "+ Neuer Verlag …",
    "newPublisherName": "Name des Verlags",
    "addPublisher": "Anlegen",
    "language": "Sprache der Einladung",
    "languageDe": "Deutsch",
    "languageEn": "English",
    "message": "Persönliche Nachricht (optional)",
    "messagePlaceholder": "z. B. Zugang zu Ihrer Nutzungs- und Nachfrageübersicht, wie besprochen",
    "help": "Der Link ist 7 Tage gültig und nur einmal verwendbar. Rolle und Zuordnung werden erst gebunden, wenn die eingeladene Person den Link öffnet und die Einladung annimmt.",
    "existingAccount": "Für diese Adresse besteht bereits ein Konto. Es erhält die Rolle mit Annahme der Einladung.",
    "unverifiedAccount": "Das bestehende Konto ist unbestätigt. Beim Annehmen werden seine Anmeldedaten zurückgesetzt; ohne Google-Verknüpfung werden auch seine Inhalte gelöscht.",
    "blockedAccount": "Dieses Konto ist gesperrt und kann nicht eingeladen werden.",
    "openInvitation": "Für diese Adresse gibt es bereits eine offene Einladung. Sie wird ersetzt.",
    "send": "Einladung senden",
    "cancel": "Abbrechen"
  },
  "roleMatrix": {
    "button": "Was die Rollen sehen",
    "title": "Was die Rollen sehen",
    "planned": "geplant",
    "roles": { "anonymous": "Anonym", "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
    "capabilities": {
      "search_and_free_content": "Suche und freie Inhalte",
      "chat_and_history": "Chat und Verlauf",
      "chats_of_others": "Chats anderer Nutzer",
      "personal_usage_data_of_others": "Personenbezogene Nutzungsdaten anderer",
      "usage_and_demand": "Nutzung und Nachfrage",
      "deliveries": "Lieferungen",
      "billing": "Abrechnung",
      "user_management": "Nutzermanagement und Audit-Protokoll"
    },
    "values": {
      "yes": "ja", "no": "–", "own": "eigene", "aggregated_own": "eigene Inhalte, aggregiert", "all": "alle"
    }
  },
  "notices": {
    "invited": "Einladung an {email} gesendet.",
    "resent": "Einladung erneut gesendet.",
    "withdrawn": "Einladung zurückgezogen.",
    "saved": "Änderung gespeichert.",
    "blocked": "Konto gesperrt.",
    "unblocked": "Konto entsperrt.",
    "removed": "Konto entfernt.",
    "emailNotSent": "Die Aktion wurde ausgeführt, aber die E-Mail konnte nicht versendet werden."
  },
  "errors": {
    "last_administrator": "Der letzte Administrator kann nicht herabgestuft, gesperrt oder entfernt werden.",
    "self_action": "Das eigene Konto kann hier nicht geändert werden.",
    "upgrade_requires_invitation": "Höhere Rollen werden per Einladung vergeben.",
    "not_a_publisher": "Das Konto hat nicht die Rolle Publisher.",
    "account_blocked": "Das Konto ist gesperrt.",
    "already_blocked": "Das Konto ist bereits gesperrt.",
    "not_blocked": "Das Konto ist nicht gesperrt.",
    "publisher_name_taken": "Ein Verlag mit diesem Namen existiert bereits.",
    "unknown_publisher": "Der Verlag existiert nicht.",
    "confirmation_mismatch": "Die E-Mail-Adresse stimmt nicht überein.",
    "invitation_invalid": "Die Einladung ist ungültig oder abgelaufen.",
    "forbidden": "Dafür fehlt die Berechtigung.",
    "generic": "Das hat nicht geklappt. Bitte erneut versuchen."
  }
},
"invitation": {
  "heading": "Einladung zu normly",
  "description": "Mit der Annahme wirst du angemeldet und erhältst die Rolle aus der Einladung.",
  "accept": "Einladung annehmen",
  "accepting": "Wird angenommen …",
  "invalid": "Dieser Einladungslink ist ungültig oder abgelaufen. Bitte die einladende Person um eine neue Einladung.",
  "missingToken": "Dieser Link ist unvollständig. Bitte öffne den Link aus der Einladungs-E-Mail.",
  "lastAdministrator": "Diese Einladung würde den letzten Administrator entfernen und kann daher nicht angenommen werden."
}
```

Add to `de.json` `auth`: `"accountBlocked": "Dein Konto ist gesperrt. Eine Anmeldung ist nicht möglich."`, `"accountBlockedContact": "Bei Fragen wende dich an {contact}."`. Add to `de.json` `account`: `"deleteLastAdministrator": "Du bist der letzte Administrator. Mache zuerst eine andere Person zum Administrator."`.

Add the same structure to `en.json` with these values:

```json
"admin": {
  "inviteButton": "Invite user",
  "noAccess": "No access. This page is for administrators only.",
  "loadError": "The data could not be loaded.",
  "summary": {
    "accountsTotal": "Total accounts",
    "activeHint": "{count} of them active in the last 30 days",
    "publishers": "With role publisher",
    "publishersHint": "{publishers} publishers · {invitations} open invitations",
    "administrators": "With role administrator",
    "administratorsHint": "Access to user management",
    "blocked": "Blocked",
    "blockedHint": "most frequent reason: {reason}",
    "blockedNone": "no blocked accounts"
  },
  "tabs": { "all": "All", "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
  "status": {
    "label": "Status", "all": "All statuses", "active": "Active", "invited": "Invited",
    "expired": "Expired", "blocked": "Blocked"
  },
  "searchPlaceholder": "Search e-mail or name …",
  "searchLabel": "Search accounts",
  "columns": {
    "account": "Account", "firstName": "First name", "lastName": "Last name", "signIn": "Sign-in",
    "role": "Role", "publisher": "Publisher", "lastLogin": "Last sign-in",
    "createdAt": "Account since", "status": "Status", "actions": "Actions"
  },
  "signIn": { "email": "E-mail", "google": "Google" },
  "never": "never",
  "today": "today {time}",
  "yesterday": "yesterday {time}",
  "roles": { "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
  "blockReasons": {
    "bulk_retrieval": "Bulk retrieval", "abuse": "Abuse",
    "terms_violation": "Terms of use violated", "other": "Other"
  },
  "pagination": {
    "showing": "Showing {from} to {to} of {total} rows",
    "rowsPerPage": "Rows per page",
    "page": "Page {page} of {pages}",
    "first": "First page", "previous": "Previous page",
    "next": "Next page", "last": "Last page"
  },
  "empty": "No entries found.",
  "actions": {
    "menu": "Actions for {email}", "edit": "Edit", "block": "Block",
    "unblock": "Unblock", "remove": "Remove", "resend": "Resend",
    "withdraw": "Withdraw"
  },
  "edit": {
    "title": "Edit account",
    "upgradeHint": "Higher roles are granted by invitation.",
    "publisher": "Publisher",
    "downgrade": "Downgrade to user",
    "save": "Save",
    "cancel": "Cancel"
  },
  "block": {
    "title": "Block account",
    "description": "{email} is signed out at once and can no longer sign in. The person receives a neutral e-mail that does not state the reason.",
    "reason": "Reason",
    "confirm": "Block",
    "cancel": "Cancel"
  },
  "remove": {
    "title": "Remove account",
    "description": "The account {email} and all its data are deleted for good. For abuse, block instead: a removed address can register again.",
    "confirmLabel": "Type the e-mail address to confirm",
    "confirm": "Remove for good",
    "cancel": "Cancel"
  },
  "invite": {
    "title": "Invite user",
    "email": "E-mail address",
    "emailPlaceholder": "name@publisher.com",
    "role": "Role",
    "publisher": "Publisher binding",
    "publisherPlaceholder": "Choose a publisher",
    "newPublisher": "+ New publisher …",
    "newPublisherName": "Publisher name",
    "addPublisher": "Add",
    "language": "Invitation language",
    "languageDe": "Deutsch",
    "languageEn": "English",
    "message": "Personal message (optional)",
    "messagePlaceholder": "e.g. access to your usage and demand overview, as discussed",
    "help": "The link is valid for 7 days and can be used once. Role and binding take effect only when the invited person opens the link and accepts.",
    "existingAccount": "An account already exists for this address. It receives the role when the invitation is accepted.",
    "unverifiedAccount": "The existing account is unverified. Accepting resets its sign-in data; without a Google link its content is deleted too.",
    "blockedAccount": "This account is blocked and cannot be invited.",
    "openInvitation": "There is already an open invitation for this address. It will be replaced.",
    "send": "Send invitation",
    "cancel": "Cancel"
  },
  "roleMatrix": {
    "button": "What the roles see",
    "title": "What the roles see",
    "planned": "planned",
    "roles": { "anonymous": "Anonymous", "user": "User", "publisher": "Publisher", "administrator": "Administrator" },
    "capabilities": {
      "search_and_free_content": "Search and free content",
      "chat_and_history": "Chat and history",
      "chats_of_others": "Chats of other users",
      "personal_usage_data_of_others": "Personal usage data of others",
      "usage_and_demand": "Usage and demand",
      "deliveries": "Deliveries",
      "billing": "Billing",
      "user_management": "User management and audit log"
    },
    "values": {
      "yes": "yes", "no": "–", "own": "own", "aggregated_own": "own content, aggregated", "all": "all"
    }
  },
  "notices": {
    "invited": "Invitation sent to {email}.",
    "resent": "Invitation sent again.",
    "withdrawn": "Invitation withdrawn.",
    "saved": "Change saved.",
    "blocked": "Account blocked.",
    "unblocked": "Account unblocked.",
    "removed": "Account removed.",
    "emailNotSent": "The action was carried out, but the e-mail could not be sent."
  },
  "errors": {
    "last_administrator": "The last administrator cannot be downgraded, blocked or removed.",
    "self_action": "Your own account cannot be changed here.",
    "upgrade_requires_invitation": "Higher roles are granted by invitation.",
    "not_a_publisher": "The account does not have the publisher role.",
    "account_blocked": "The account is blocked.",
    "already_blocked": "The account is already blocked.",
    "not_blocked": "The account is not blocked.",
    "publisher_name_taken": "A publisher with this name already exists.",
    "unknown_publisher": "The publisher does not exist.",
    "confirmation_mismatch": "The e-mail address does not match.",
    "invitation_invalid": "The invitation is invalid or has expired.",
    "forbidden": "You do not have permission for this.",
    "generic": "That did not work. Please try again."
  }
},
"invitation": {
  "heading": "Invitation to normly",
  "description": "Accepting signs you in and gives you the role from the invitation.",
  "accept": "Accept invitation",
  "accepting": "Accepting …",
  "invalid": "This invitation link is invalid or has expired. Please ask the person who invited you for a new invitation.",
  "missingToken": "This link is incomplete. Please open the link from the invitation e-mail.",
  "lastAdministrator": "Accepting this invitation would remove the last administrator, so it cannot be accepted."
}
```

`en.json` `auth`: `"accountBlocked": "Your account is blocked. You cannot sign in."`, `"accountBlockedContact": "If you have questions, contact {contact}."`; `account`: `"deleteLastAdministrator": "You are the last administrator. Make someone else an administrator first."`.

If the repo has a test that pins both dictionaries to the same shape (search `tests/unit` for `en.json`), it must still pass.

- [ ] **Step 2: Write the failing tests**

`frontend/tests/unit/admin-proxy-route.test.ts`:

```ts
// frontend/tests/unit/admin-proxy-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE, GET, PATCH } from "@/app/api/admin/[...path]/route";

const originalFetch = global.fetch;
const ctx = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("/api/admin/[...path]", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards path, query and session to the accounts admin API", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ rows: [], total: 0 }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const request = new NextRequest("http://localhost/api/admin/users?q=a%40b&page=2", {
      headers: { cookie: "normly_account_session=tok" },
    });

    const response = await GET(request, ctx(["users"]));

    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/admin/users?q=a%40b&page=2");
    expect(init.headers.Authorization).toBe("Bearer tok");
  });

  it("passes JSON bodies and 204 answers through", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const request = new NextRequest("http://localhost/api/admin/accounts/42", {
      method: "PATCH", body: JSON.stringify({ role: "user" }),
      headers: { cookie: "normly_account_session=tok", "content-type": "application/json" },
    });

    const response = await PATCH(request, ctx(["accounts", "42"]));

    expect(response.status).toBe(204);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ role: "user" }));
  });

  it("answers 401 without a session and refuses dot segments", async () => {
    const anonymous = new NextRequest("http://localhost/api/admin/users");
    expect((await GET(anonymous, ctx(["users"]))).status).toBe(401);
    const sneaky = new NextRequest("http://localhost/api/admin/x", {
      method: "DELETE", headers: { cookie: "normly_account_session=tok" },
    });
    expect((await DELETE(sneaky, ctx(["..", "accounts", "me"]))).status).toBe(400);
  });
});
```

`frontend/tests/unit/admin-api.test.ts`:

```ts
// frontend/tests/unit/admin-api.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminApiError, adminApi, errorKey } from "@/lib/admin-api";

const originalFetch = global.fetch;

describe("adminApi", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("maps the user page to camelCase and builds the query", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      rows: [{
        kind: "account", id: "1", email: "a@b.de", first_name: "A", last_name: null,
        sign_in_methods: ["email", "google"], role: "publisher", publisher_id: "p",
        publisher_name: "DIN Media", last_login_at: null, created_at: "2026-10-01T10:00:00Z",
        status: "active", block_reason: null, expires_at: null,
      }],
      total: 1, page: 1, page_size: 10,
    })));

    const page = await adminApi.listUsers({
      q: "a", role: "publisher", status: "all", sort: "email", order: "asc", page: 1, pageSize: 10,
    });

    expect(page.rows[0]).toMatchObject({
      firstName: "A", signInMethods: ["email", "google"], publisherName: "DIN Media",
    });
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/admin/users?q=a&role=publisher&sort=email&order=asc&page=1&page_size=10",
    );
  });

  it("turns an error body into AdminApiError with the backend code", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "last_administrator" }), { status: 409 }),
    );
    const failure = adminApi.unblock("1");
    await expect(failure).rejects.toBeInstanceOf(AdminApiError);
    await expect(failure).rejects.toMatchObject({ status: 409, code: "last_administrator" });
  });

  it("maps known codes to translation keys and everything else to generic", () => {
    expect(errorKey(new AdminApiError(409, "self_action"))).toBe("admin.errors.self_action");
    expect(errorKey(new AdminApiError(400, "invalid or missing parameter: body.email")))
      .toBe("admin.errors.generic");
    expect(errorKey(new Error("network"))).toBe("admin.errors.generic");
  });
});
```

`frontend/tests/unit/admin-format.test.ts`:

```ts
// frontend/tests/unit/admin-format.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { formatDate, formatLastLogin, formatNumber } from "@/lib/admin-format";

const t = (key: string) =>
  ({ "admin.never": "noch nie", "admin.today": "heute {time}", "admin.yesterday": "gestern {time}" })[key] ?? key;

describe("admin formatting", () => {
  const now = new Date("2026-10-31T12:00:00");

  it("formats numbers per locale", () => {
    expect(formatNumber(1284, "de")).toBe("1.284");
    expect(formatNumber(1284, "en")).toBe("1,284");
  });

  it("shows today and yesterday relatively, older dates absolutely", () => {
    expect(formatLastLogin(null, "de", t, now)).toBe("noch nie");
    expect(formatLastLogin(new Date("2026-10-31T09:12:00").toISOString(), "de", t, now))
      .toBe("heute 09:12");
    expect(formatLastLogin(new Date("2026-10-30T22:40:00").toISOString(), "de", t, now))
      .toBe("gestern 22:40");
    expect(formatLastLogin(new Date("2026-10-19T16:41:00").toISOString(), "de", t, now))
      .toBe("19.10.2026 16:41");
    expect(formatDate(new Date("2026-03-15T10:00:00").toISOString(), "de")).toBe("15.03.2026");
  });
});
```

`frontend/tests/unit/admin-users-query.test.ts`:

```ts
// frontend/tests/unit/admin-users-query.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { DEFAULT_USERS_QUERY, parseUsersQuery, serializeUsersQuery } from "@/lib/admin-users-query";

describe("users query in the URL", () => {
  it("falls back to defaults for missing or invalid values", () => {
    expect(parseUsersQuery(new URLSearchParams(""))).toEqual(DEFAULT_USERS_QUERY);
    expect(parseUsersQuery(new URLSearchParams("page=-3&page_size=7&sort=password&role=owner")))
      .toEqual(DEFAULT_USERS_QUERY);
  });

  it("round-trips non-default values and omits defaults", () => {
    const query = { ...DEFAULT_USERS_QUERY, q: "keller", role: "administrator" as const,
                    status: "blocked" as const, sort: "last_login_at" as const,
                    order: "desc" as const, page: 3, pageSize: 50 };
    const serialized = serializeUsersQuery(query);
    expect(parseUsersQuery(new URLSearchParams(serialized))).toEqual(query);
    expect(serializeUsersQuery(DEFAULT_USERS_QUERY)).toBe("");
  });
});
```

`frontend/tests/unit/invitation-accept-route.test.ts`:

```ts
// frontend/tests/unit/invitation-accept-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/auth/invitation/accept/route";

const originalFetch = global.fetch;

describe("POST /api/auth/invitation/accept", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("sets the session cookie on success", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_token: "new-session", account: {} }), { status: 200 }),
    );
    const response = await POST(new NextRequest("http://localhost/api/auth/invitation/accept", {
      method: "POST", body: JSON.stringify({ token: "inv" }),
      headers: { "content-type": "application/json" },
    }));
    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value).toBe("new-session");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/invitations/accept");
  });

  it("passes errors through without a cookie", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invitation_invalid" }), { status: 410 }),
    );
    const response = await POST(new NextRequest("http://localhost/api/auth/invitation/accept", {
      method: "POST", body: JSON.stringify({ token: "old" }),
      headers: { "content-type": "application/json" },
    }));
    expect(response.status).toBe(410);
    expect(response.cookies.get("normly_account_session")).toBeUndefined();
  });
});
```

- [ ] **Step 3: Run and see them fail**

Run: `cd frontend && npx vitest run tests/unit/admin-proxy-route.test.ts tests/unit/admin-api.test.ts tests/unit/admin-format.test.ts tests/unit/admin-users-query.test.ts tests/unit/invitation-accept-route.test.ts`
Expected: FAIL (modules do not exist).

- [ ] **Step 4: BFF routes**

`frontend/src/app/api/admin/[...path]/route.ts`:

```ts
// frontend/src/app/api/admin/[...path]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

type Context = { params: Promise<{ path: string[] }> };

// One pass-through for the whole admin API: the accounts service checks the
// role on every request, so this route only forwards the session. Segments
// are encoded one by one and dot segments are refused, so a path can never
// leave /v1/admin/.
async function proxy(request: NextRequest, { params }: Context): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const { path } = await params;
  if (path.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return NextResponse.json({ detail: "invalid path" }, { status: 400 });
  }
  const url =
    `${getBackendUrls().accounts}/v1/admin/${path.map(encodeURIComponent).join("/")}`
    + request.nextUrl.search;

  const headers: Record<string, string> = { Authorization: `Bearer ${accountSessionToken}` };
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) {
      init.body = body;
      headers["content-type"] = "application/json";
    }
  }

  const backendResponse = await fetch(url, init);
  if (backendResponse.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  return new NextResponse(await backendResponse.text(), {
    status: backendResponse.status,
    headers: {
      "content-type": backendResponse.headers.get("content-type") ?? "application/json",
    },
  });
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
```

`frontend/src/app/api/auth/invitation/accept/route.ts`:

```ts
// frontend/src/app/api/auth/invitation/accept/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/invitations/accept`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: payload.token }),
    },
  );
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
```

- [ ] **Step 5: Typed client**

`frontend/src/lib/admin-api.ts`:

```ts
// frontend/src/lib/admin-api.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export type Role = "user" | "publisher" | "administrator";
export type UserStatus = "active" | "blocked" | "invited" | "expired";
export type BlockReason = "bulk_retrieval" | "abuse" | "terms_violation" | "other";
export type SortKey =
  | "email" | "first_name" | "last_name" | "sign_in" | "role" | "publisher"
  | "last_login_at" | "created_at" | "status";

export const ROLES: Role[] = ["user", "publisher", "administrator"];
export const BLOCK_REASONS: BlockReason[] = ["bulk_retrieval", "abuse", "terms_violation", "other"];
export const PAGE_SIZES = [10, 20, 50] as const;

export interface UsersQuery {
  q: string;
  role: Role | "all";
  status: UserStatus | "all";
  sort: SortKey;
  order: "asc" | "desc";
  page: number;
  pageSize: number;
}

export interface AdminUserRow {
  kind: "account" | "invitation";
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  signInMethods: Array<"email" | "google">;
  role: Role;
  publisherId: string | null;
  publisherName: string | null;
  lastLoginAt: string | null;
  createdAt: string | null;
  status: UserStatus;
  blockReason: BlockReason | null;
  expiresAt: string | null;
}

export interface AdminUserPage { rows: AdminUserRow[]; total: number; page: number; pageSize: number }

export interface AdminSummary {
  accountsTotal: number;
  accountsActive30Days: number;
  accountsByRole: Record<Role, number>;
  publishersWithAccounts: number;
  openInvitations: number;
  blocked: number;
  mostFrequentBlockReason: BlockReason | null;
}

export interface Publisher { id: string; name: string }
export interface InvitationCheck {
  existingAccount: boolean; verified: boolean; blocked: boolean; openInvitation: boolean;
}
export interface InviteInput {
  email: string; role: Role; publisherId: string | null; locale: "de" | "en"; message: string;
}
export interface RoleMatrix {
  roles: string[];
  rows: Array<{ capability: string; planned: boolean; values: Record<string, string> }>;
}

export class AdminApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
    this.name = "AdminApiError";
  }
}

const KNOWN_CODES = new Set([
  "last_administrator", "self_action", "upgrade_requires_invitation", "not_a_publisher",
  "account_blocked", "already_blocked", "not_blocked", "publisher_name_taken",
  "unknown_publisher", "confirmation_mismatch", "invitation_invalid", "forbidden",
]);

export function errorKey(error: unknown): TranslationKey {
  if (error instanceof AdminApiError && KNOWN_CODES.has(error.code)) {
    return `admin.errors.${error.code}` as TranslationKey;
  }
  return "admin.errors.generic";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new AdminApiError(response.status, typeof body.detail === "string" ? body.detail : "generic");
  }
  return body as T;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Raw = any;

function mapRow(raw: Raw): AdminUserRow {
  return {
    kind: raw.kind, id: raw.id, email: raw.email, firstName: raw.first_name,
    lastName: raw.last_name, signInMethods: raw.sign_in_methods, role: raw.role,
    publisherId: raw.publisher_id, publisherName: raw.publisher_name,
    lastLoginAt: raw.last_login_at, createdAt: raw.created_at, status: raw.status,
    blockReason: raw.block_reason, expiresAt: raw.expires_at,
  };
}

function usersSearch(query: UsersQuery): string {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.role !== "all") params.set("role", query.role);
  if (query.status !== "all") params.set("status", query.status);
  params.set("sort", query.sort);
  params.set("order", query.order);
  params.set("page", String(query.page));
  params.set("page_size", String(query.pageSize));
  return params.toString();
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const adminApi = {
  async listUsers(query: UsersQuery): Promise<AdminUserPage> {
    const raw = await request<Raw>(`users?${usersSearch(query)}`);
    return { rows: raw.rows.map(mapRow), total: raw.total, page: raw.page, pageSize: raw.page_size };
  },
  async summary(): Promise<AdminSummary> {
    const raw = await request<Raw>("users/summary");
    return {
      accountsTotal: raw.accounts_total, accountsActive30Days: raw.accounts_active_30_days,
      accountsByRole: raw.accounts_by_role, publishersWithAccounts: raw.publishers_with_accounts,
      openInvitations: raw.open_invitations, blocked: raw.blocked,
      mostFrequentBlockReason: raw.most_frequent_block_reason,
    };
  },
  async publishers(): Promise<Publisher[]> {
    const raw = await request<Raw[]>("publishers");
    return raw.map((p) => ({ id: p.id, name: p.name }));
  },
  async createPublisher(name: string): Promise<Publisher> {
    const raw = await request<Raw>("publishers", { method: "POST", ...json({ name }) });
    return { id: raw.id, name: raw.name };
  },
  async checkInvitation(email: string): Promise<InvitationCheck> {
    const raw = await request<Raw>(`invitations/check?email=${encodeURIComponent(email)}`);
    return {
      existingAccount: raw.existing_account, verified: raw.verified, blocked: raw.blocked,
      openInvitation: raw.open_invitation,
    };
  },
  async invite(input: InviteInput): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>("invitations", {
      method: "POST",
      ...json({
        email: input.email, role: input.role, publisher_id: input.publisherId,
        locale: input.locale, message: input.message.trim() || null,
      }),
    });
    return { emailSent: raw.email_sent };
  },
  async resendInvitation(id: string): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`invitations/${id}/resend`, { method: "POST" });
    return { emailSent: raw.email_sent };
  },
  withdrawInvitation: (id: string) => request<void>(`invitations/${id}`, { method: "DELETE" }),
  downgradeToUser: (id: string) =>
    request<void>(`accounts/${id}`, { method: "PATCH", ...json({ role: "user" }) }),
  changePublisher: (id: string, publisherId: string) =>
    request<void>(`accounts/${id}`, { method: "PATCH", ...json({ publisher_id: publisherId }) }),
  async block(id: string, reason: BlockReason): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`accounts/${id}/block`, { method: "POST", ...json({ reason }) });
    return { emailSent: raw.email_sent };
  },
  unblock: (id: string) => request<void>(`accounts/${id}/unblock`, { method: "POST" }),
  async remove(id: string, confirmEmail: string): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`accounts/${id}`, {
      method: "DELETE", ...json({ confirm_email: confirmEmail }),
    });
    return { emailSent: raw.email_sent };
  },
  roleMatrix: () => request<RoleMatrix>("role-matrix"),
};
```

If the project has no ESLint config, drop the `eslint-disable` comment.

- [ ] **Step 6: Formatting and query state**

`frontend/src/lib/admin-format.ts`:

```ts
// frontend/src/lib/admin-format.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { interpolate } from "@/lib/i18n/interpolate";

type Locale = "de" | "en";
const TAG: Record<Locale, string> = { de: "de-DE", en: "en-GB" };

export function formatNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(TAG[locale]).format(value);
}

export function formatDate(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(TAG[locale], { day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(iso));
}

function formatTime(date: Date, locale: Locale): string {
  return new Intl.DateTimeFormat(TAG[locale], { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatDateTime(iso: string, locale: Locale): string {
  const date = new Date(iso);
  return `${formatDate(iso, locale)} ${formatTime(date, locale)}`;
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

export function formatLastLogin(
  iso: string | null, locale: Locale, t: (key: never) => string, now: Date = new Date(),
): string {
  const translate = t as unknown as (key: string) => string;
  if (!iso) return translate("admin.never");
  const date = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, now)) return interpolate(translate("admin.today"), { time: formatTime(date, locale) });
  if (sameDay(date, yesterday)) {
    return interpolate(translate("admin.yesterday"), { time: formatTime(date, locale) });
  }
  return formatDateTime(iso, locale);
}
```

Replace the `t` parameter typing with the project's real `t` type (`(key: TranslationKey) => string`) if it type-checks cleanly with the test's plain-function stub; the cast is only there so the test can pass a simple lookup.

`frontend/src/lib/admin-users-query.ts`:

```ts
// frontend/src/lib/admin-users-query.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PAGE_SIZES, ROLES, type SortKey, type UsersQuery } from "@/lib/admin-api";

const SORT_KEYS: SortKey[] = [
  "email", "first_name", "last_name", "sign_in", "role", "publisher", "last_login_at",
  "created_at", "status",
];
const STATUSES = ["active", "blocked", "invited", "expired"] as const;

export const DEFAULT_USERS_QUERY: UsersQuery = {
  q: "", role: "all", status: "all", sort: "email", order: "asc", page: 1, pageSize: 10,
};

function oneOf<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export function parseUsersQuery(params: URLSearchParams): UsersQuery {
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("page_size"));
  return {
    q: params.get("q") ?? "",
    role: oneOf(params.get("role"), ROLES, "all" as never) as UsersQuery["role"],
    status: oneOf(params.get("status"), STATUSES, "all" as never) as UsersQuery["status"],
    sort: oneOf(params.get("sort"), SORT_KEYS, "email"),
    order: params.get("order") === "desc" ? "desc" : "asc",
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : 10,
  };
}

export function serializeUsersQuery(query: UsersQuery): string {
  const params = new URLSearchParams();
  const d = DEFAULT_USERS_QUERY;
  if (query.q !== d.q) params.set("q", query.q);
  if (query.role !== d.role) params.set("role", query.role);
  if (query.status !== d.status) params.set("status", query.status);
  if (query.sort !== d.sort) params.set("sort", query.sort);
  if (query.order !== d.order) params.set("order", query.order);
  if (query.page !== d.page) params.set("page", String(query.page));
  if (query.pageSize !== d.pageSize) params.set("page_size", String(query.pageSize));
  return params.toString();
}

export function useUsersQuery() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = React.useMemo(
    () => parseUsersQuery(new URLSearchParams(searchParams.toString())), [searchParams],
  );
  const update = React.useCallback((patch: Partial<UsersQuery>) => {
    // Any change except paging starts again at page 1.
    const next = { ...query, ...patch, page: "page" in patch ? patch.page ?? 1 : 1 };
    const search = serializeUsersQuery(next);
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  }, [query, router, pathname]);
  return { query, update };
}
```

Tidy the `oneOf(..., "all" as never)` casts if TypeScript allows a cleaner form; behaviour must stay: unknown values fall back to the default.

- [ ] **Step 7: Run the tests and the type check**

Run: `cd frontend && npx vitest run tests/unit/admin-proxy-route.test.ts tests/unit/admin-api.test.ts tests/unit/admin-format.test.ts tests/unit/admin-users-query.test.ts tests/unit/invitation-accept-route.test.ts && npx tsc --noEmit`
Expected: PASS. If `formatNumber(1284, "de")` yields `1284` in the test environment (missing ICU), check Node's ICU (`node -e "console.log(new Intl.NumberFormat('de-DE').format(1284))"`); Node ≥ 13 ships full ICU.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): add the admin API client, proxy and copy" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 6: The user management page — summary, toolbar, table, pagination

**Files:**
- Create: `frontend/src/components/ui/native-select.tsx`
- Create: `frontend/src/components/admin/badges.tsx`, `summary-cards.tsx`, `users-toolbar.tsx`, `users-table.tsx`, `users-pagination.tsx`
- Create: `frontend/src/app/admin/users/page.tsx`, `frontend/src/app/admin/users/user-management-content.tsx`
- Test: `frontend/tests/unit/user-management-page.test.tsx` (create)

**Interfaces:**
- Consumes: Task 5 (`adminApi`, `useUsersQuery`, formatters, copy), `useAccountSession`.
- Produces: `UserManagementContent` holding `reload()` and a `dialog` state that Tasks 7–9 extend: `type DialogState = null | { kind: "edit" | "block" | "remove"; row: AdminUserRow } | { kind: "invite" } | { kind: "matrix" }`; `UsersTable` props `{ rows, query, onSort, renderActions(row) }`; `notice` state `{ kind: "success" | "error"; text: string } | null` shown as `role="status"` / `role="alert"`.

- [ ] **Step 1: Write the failing test**

`frontend/tests/unit/user-management-page.test.tsx`:

```tsx
// frontend/tests/unit/user-management-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { UserManagementContent } from "@/app/admin/users/user-management-content";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/admin/users",
  useSearchParams: () => new URLSearchParams(search),
}));

const originalFetch = global.fetch;

const summary = {
  accounts_total: 1284, accounts_active_30_days: 412,
  accounts_by_role: { user: 1279, publisher: 3, administrator: 2 },
  publishers_with_accounts: 2, open_invitations: 1, blocked: 1,
  most_frequent_block_reason: "bulk_retrieval",
};
const row = (overrides: Record<string, unknown>) => ({
  kind: "account", id: "1", email: "ops@normly.example", first_name: "Jonas",
  last_name: "Keller", sign_in_methods: ["email"], role: "administrator",
  publisher_id: null, publisher_name: null, last_login_at: null,
  created_at: "2026-03-15T10:00:00Z", status: "active", block_reason: null, expires_at: null,
  ...overrides,
});

function mockApi(status = 200) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/auth/session")) {
      return Promise.resolve(new Response(JSON.stringify({ account: null })));
    }
    if (status !== 200) {
      return Promise.resolve(new Response(JSON.stringify({ detail: "forbidden" }), { status }));
    }
    if (url.startsWith("/api/admin/users/summary")) {
      return Promise.resolve(new Response(JSON.stringify(summary)));
    }
    return Promise.resolve(new Response(JSON.stringify({
      rows: [
        row({}),
        row({ id: "2", kind: "invitation", email: "partner@vde.example", first_name: null,
              last_name: null, sign_in_methods: [], role: "publisher", publisher_name: "VDE Verlag",
              created_at: null, status: "invited" }),
      ],
      total: 1284, page: 1, page_size: 10,
    })));
  });
}

function renderPage() {
  return render(
    <LocaleProvider initialLocale="de"><UserManagementContent /></LocaleProvider>,
  );
}

describe("UserManagementContent", () => {
  beforeEach(() => {
    search = "";
    replace.mockReset();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the summary, the role tabs with counts and the rows", async () => {
    mockApi();
    renderPage();
    expect(await screen.findByText("1.284", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("davon 412 in den letzten 30 Tagen aktiv")).toBeInTheDocument();
    expect(screen.getByText("häufigster Grund: Massenabruf")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Publisher\s*3/ })).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("ops@normly.example")).toBeInTheDocument();
    expect(within(table).getByText("Eingeladen")).toBeInTheDocument();
    expect(within(table).getByText("VDE Verlag")).toBeInTheDocument();
    expect(screen.getByText("Zeige 1 bis 10 von 1.284 Zeilen")).toBeInTheDocument();
    expect(screen.getByText("Seite 1 von 129")).toBeInTheDocument();
  });

  it("writes sorting, filters and paging into the URL", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Letzte Anmeldung" }));
    expect(replace).toHaveBeenLastCalledWith("/admin/users?sort=last_login_at", { scroll: false });

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "blocked" } });
    expect(replace).toHaveBeenLastCalledWith("/admin/users?status=blocked", { scroll: false });

    fireEvent.click(screen.getByRole("button", { name: "Nächste Seite" }));
    expect(replace).toHaveBeenLastCalledWith("/admin/users?page=2", { scroll: false });
  });

  it("marks the sorted column with aria-sort", async () => {
    search = "sort=email&order=desc";
    mockApi();
    renderPage();
    await screen.findByRole("table");
    expect(screen.getByRole("columnheader", { name: "Konto" })).toHaveAttribute("aria-sort", "descending");
  });

  it("shows the no-access state on 403", async () => {
    mockApi(403);
    renderPage();
    expect(await screen.findByText("Kein Zugriff. Diese Seite ist Administratoren vorbehalten."))
      .toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run and see it fail**

Run: `cd frontend && npx vitest run tests/unit/user-management-page.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Native select**

`frontend/src/components/ui/native-select.tsx`:

```tsx
// frontend/src/components/ui/native-select.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { cn } from "@/lib/utils";

// A styled native <select>: keyboard, screen readers and mobile pickers work
// without another Radix package. Same look as Input.
const NativeSelect = React.forwardRef<
  HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
NativeSelect.displayName = "NativeSelect";

export { NativeSelect };
```

- [ ] **Step 4: Badges and summary cards**

`frontend/src/components/admin/badges.tsx`:

```tsx
// frontend/src/components/admin/badges.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { Ban, BookOpen, CircleCheck, Clock, Hourglass, Shield, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Role, UserStatus } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const ROLE_ICON = { administrator: Shield, publisher: BookOpen, user: User } as const;

export function RoleBadge({ role }: { role: Role }) {
  const { t } = useTranslation();
  const Icon = ROLE_ICON[role];
  return (
    <Badge variant={role === "administrator" ? "default" : role === "publisher" ? "secondary" : "outline"}
           className="gap-1 whitespace-nowrap">
      <Icon className="size-3" aria-hidden />
      {t(`admin.roles.${role}`)}
    </Badge>
  );
}

const STATUS_STYLE: Record<UserStatus, { icon: typeof Clock; className: string }> = {
  active: { icon: CircleCheck, className: "border-green-600/40 text-green-700 dark:text-green-400" },
  invited: { icon: Clock, className: "border-amber-600/40 text-amber-700 dark:text-amber-400" },
  expired: { icon: Hourglass, className: "border-border text-muted-foreground" },
  blocked: { icon: Ban, className: "border-red-600/40 text-red-700 dark:text-red-400" },
};

export function StatusBadge({ status }: { status: UserStatus }) {
  const { t } = useTranslation();
  const { icon: Icon, className } = STATUS_STYLE[status];
  return (
    <Badge variant="outline" className={cn("gap-1 whitespace-nowrap", className)}>
      <Icon className="size-3" aria-hidden />
      {t(`admin.status.${status}`)}
    </Badge>
  );
}
```

(The template-literal keys are valid `TranslationKey`s; if TypeScript cannot narrow them, cast with `as TranslationKey`.)

`frontend/src/components/admin/summary-cards.tsx`:

```tsx
// frontend/src/components/admin/summary-cards.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import type { AdminSummary } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

function Card({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 text-card-foreground">
      <h2 className="text-sm text-muted-foreground">{label}</h2>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-muted-foreground">{hint}</p>
    </div>
  );
}

export function SummaryCards({ summary }: { summary: AdminSummary }) {
  const { t, locale } = useTranslation();
  const n = (value: number) => formatNumber(value, locale);
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card
        label={t("admin.summary.accountsTotal")}
        value={n(summary.accountsTotal)}
        hint={interpolate(t("admin.summary.activeHint"), { count: n(summary.accountsActive30Days) })}
      />
      <Card
        label={t("admin.summary.publishers")}
        value={n(summary.accountsByRole.publisher)}
        hint={interpolate(t("admin.summary.publishersHint"), {
          publishers: n(summary.publishersWithAccounts), invitations: n(summary.openInvitations),
        })}
      />
      <Card
        label={t("admin.summary.administrators")}
        value={n(summary.accountsByRole.administrator)}
        hint={t("admin.summary.administratorsHint")}
      />
      <Card
        label={t("admin.summary.blocked")}
        value={n(summary.blocked)}
        hint={summary.mostFrequentBlockReason
          ? interpolate(t("admin.summary.blockedHint"), {
            reason: t(`admin.blockReasons.${summary.mostFrequentBlockReason}`),
          })
          : t("admin.summary.blockedNone")}
      />
    </div>
  );
}
```

- [ ] **Step 5: Toolbar, table, pagination**

`frontend/src/components/admin/users-toolbar.tsx`:

```tsx
// frontend/src/components/admin/users-toolbar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AdminSummary, UsersQuery } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";

const TABS = ["all", "user", "administrator", "publisher"] as const;
const STATUS_OPTIONS = ["all", "active", "invited", "expired", "blocked"] as const;

export function UsersToolbar({
  query, summary, onChange,
}: {
  query: UsersQuery;
  summary: AdminSummary | null;
  onChange: (patch: Partial<UsersQuery>) => void;
}) {
  const { t, locale } = useTranslation();
  const [text, setText] = React.useState(query.q);

  // 300 ms debounce; the URL stays the single source of truth.
  React.useEffect(() => {
    if (text === query.q) return;
    const timer = window.setTimeout(() => onChange({ q: text }), 300);
    return () => window.clearTimeout(timer);
  }, [text, query.q, onChange]);

  const count = (tab: (typeof TABS)[number]) => {
    if (!summary) return null;
    return formatNumber(tab === "all" ? summary.accountsTotal : summary.accountsByRole[tab], locale);
  };

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <Tabs value={query.role} onValueChange={(value) => onChange({ role: value as UsersQuery["role"] })}>
          <TabsList>
            {TABS.map((tab) => (
              <TabsTrigger key={tab} value={tab} className="gap-2">
                {t(`admin.tabs.${tab}`)}
                {count(tab) !== null && (
                  <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground">{count(tab)}</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <label className="flex items-center gap-2 text-sm">
          <span>{t("admin.status.label")}</span>
          <NativeSelect
            className="h-9 w-auto"
            value={query.status}
            onChange={(event) => onChange({ status: event.target.value as UsersQuery["status"] })}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{t(`admin.status.${status}`)}</option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <Input
        type="search"
        aria-label={t("admin.searchLabel")}
        placeholder={t("admin.searchPlaceholder")}
        className="lg:max-w-xs"
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
    </div>
  );
}
```

`<label>` wraps the select so `getByLabelText("Status")` finds it.

`frontend/src/components/admin/users-table.tsx`:

```tsx
// frontend/src/components/admin/users-table.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RoleBadge, StatusBadge } from "@/components/admin/badges";
import type { AdminUserRow, SortKey, UsersQuery } from "@/lib/admin-api";
import { formatDate, formatLastLogin } from "@/lib/admin-format";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useTranslation } from "@/lib/i18n/provider";

type Translate = (key: TranslationKey) => string;
type Locale = "de" | "en";

interface Column {
  sort: SortKey;
  label: TranslationKey;
  cell: (row: AdminUserRow, t: Translate, locale: Locale) => React.ReactNode;
}

const dash = <span className="text-muted-foreground">–</span>;

// One definition per column: header, sort key and cell. All left-aligned.
const COLUMNS: Column[] = [
  { sort: "email", label: "admin.columns.account", cell: (r) => <span className="font-medium">{r.email}</span> },
  { sort: "first_name", label: "admin.columns.firstName", cell: (r) => r.firstName ?? dash },
  { sort: "last_name", label: "admin.columns.lastName", cell: (r) => r.lastName ?? dash },
  {
    sort: "sign_in", label: "admin.columns.signIn",
    cell: (r, t) => r.signInMethods.length
      ? r.signInMethods.map((m) => t(`admin.signIn.${m}` as TranslationKey)).join(", ")
      : dash,
  },
  { sort: "role", label: "admin.columns.role", cell: (r) => <RoleBadge role={r.role} /> },
  { sort: "publisher", label: "admin.columns.publisher", cell: (r) => r.publisherName ?? dash },
  {
    sort: "last_login_at", label: "admin.columns.lastLogin",
    cell: (r, t, locale) => r.kind === "invitation"
      ? t("admin.never")
      : formatLastLogin(r.lastLoginAt, locale, t as never),
  },
  {
    sort: "created_at", label: "admin.columns.createdAt",
    cell: (r, _t, locale) => (r.createdAt ? formatDate(r.createdAt, locale) : dash),
  },
  { sort: "status", label: "admin.columns.status", cell: (r) => <StatusBadge status={r.status} /> },
];

export function UsersTable({
  rows, query, onSort, renderActions,
}: {
  rows: AdminUserRow[];
  query: UsersQuery;
  onSort: (sort: SortKey) => void;
  renderActions: (row: AdminUserRow) => React.ReactNode;
}) {
  const { t, locale } = useTranslation();
  return (
    <div className="overflow-x-auto rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            {COLUMNS.map((column) => {
              const active = query.sort === column.sort;
              const Icon = !active ? ArrowUpDown : query.order === "asc" ? ArrowUp : ArrowDown;
              return (
                <TableHead
                  key={column.sort}
                  className="text-left"
                  aria-sort={active ? (query.order === "asc" ? "ascending" : "descending") : "none"}
                >
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 font-medium text-foreground"
                    onClick={() => onSort(column.sort)}
                  >
                    {t(column.label)}
                    <Icon className="size-3 text-muted-foreground" aria-hidden />
                  </button>
                </TableHead>
              );
            })}
            <TableHead className="text-left">
              <span className="sr-only">{t("admin.columns.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLUMNS.length + 1} className="text-left text-muted-foreground">
                {t("admin.empty")}
              </TableCell>
            </TableRow>
          ) : rows.map((row) => (
            <TableRow key={`${row.kind}-${row.id}`}>
              {COLUMNS.map((column) => (
                <TableCell key={column.sort} className="whitespace-nowrap text-left">
                  {column.cell(row, t, locale)}
                </TableCell>
              ))}
              <TableCell className="text-left">{renderActions(row)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

`frontend/src/components/admin/users-pagination.tsx`:

```tsx
// frontend/src/components/admin/users-pagination.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { PAGE_SIZES, type UsersQuery } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function UsersPagination({
  query, total, onChange,
}: {
  query: UsersQuery;
  total: number;
  onChange: (patch: Partial<UsersQuery>) => void;
}) {
  const { t, locale } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / query.pageSize));
  const from = total === 0 ? 0 : (query.page - 1) * query.pageSize + 1;
  const to = Math.min(query.page * query.pageSize, total);
  const n = (value: number) => formatNumber(value, locale);
  const go = (page: number) => onChange({ page });

  return (
    <div className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-muted-foreground">
        {interpolate(t("admin.pagination.showing"), { from: n(from), to: n(to), total: n(total) })}
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2">
          <span>{t("admin.pagination.rowsPerPage")}</span>
          <NativeSelect
            className="h-9 w-auto"
            value={query.pageSize}
            onChange={(event) => onChange({ pageSize: Number(event.target.value) })}
          >
            {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
          </NativeSelect>
        </label>
        <span>{interpolate(t("admin.pagination.page"), { page: n(query.page), pages: n(pages) })}</span>
        <div className="flex gap-1">
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.first")}
                  disabled={query.page <= 1} onClick={() => go(1)}>
            <ChevronsLeft />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.previous")}
                  disabled={query.page <= 1} onClick={() => go(query.page - 1)}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.next")}
                  disabled={query.page >= pages} onClick={() => go(query.page + 1)}>
            <ChevronRight />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.last")}
                  disabled={query.page >= pages} onClick={() => go(pages)}>
            <ChevronsRight />
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: The page**

`frontend/src/app/admin/users/page.tsx`:

```tsx
// frontend/src/app/admin/users/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Suspense } from "react";
import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { UserManagementContent } from "./user-management-content";

export default function UserManagementPage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.userManagement" />
      <div className="p-4 md:p-8">
        <Suspense fallback={null}>
          <UserManagementContent />
        </Suspense>
      </div>
    </AppShell>
  );
}
```

`frontend/src/app/admin/users/user-management-content.tsx`:

```tsx
// frontend/src/app/admin/users/user-management-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SummaryCards } from "@/components/admin/summary-cards";
import { UsersPagination } from "@/components/admin/users-pagination";
import { UsersTable } from "@/components/admin/users-table";
import { UsersToolbar } from "@/components/admin/users-toolbar";
import {
  AdminApiError, adminApi, type AdminSummary, type AdminUserPage, type AdminUserRow, type SortKey,
} from "@/lib/admin-api";
import { useUsersQuery } from "@/lib/admin-users-query";
import { useTranslation } from "@/lib/i18n/provider";

export type DialogState =
  | null
  | { kind: "edit" | "block" | "remove"; row: AdminUserRow }
  | { kind: "invite" }
  | { kind: "matrix" };

export type Notice = { kind: "success" | "error"; text: string } | null;

export function UserManagementContent() {
  const { t } = useTranslation();
  const { query, update } = useUsersQuery();
  const [page, setPage] = React.useState<AdminUserPage | null>(null);
  const [summary, setSummary] = React.useState<AdminSummary | null>(null);
  const [state, setState] = React.useState<"loading" | "ready" | "forbidden" | "error">("loading");
  const [reloadKey, setReloadKey] = React.useState(0);
  const [dialog, setDialog] = React.useState<DialogState>(null);
  const [notice, setNotice] = React.useState<Notice>(null);
  const reload = React.useCallback(() => setReloadKey((k) => k + 1), []);

  React.useEffect(() => {
    let cancelled = false;
    Promise.all([adminApi.listUsers(query), adminApi.summary()])
      .then(([users, totals]) => {
        if (cancelled) return;
        setPage(users);
        setSummary(totals);
        setState("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        setState(error instanceof AdminApiError && (error.status === 403 || error.status === 401)
          ? "forbidden" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [query, reloadKey]);

  const onSort = (sort: SortKey) =>
    update({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc" });

  if (state === "forbidden") return <p className="text-sm">{t("admin.noAccess")}</p>;
  if (state === "error") return <p role="alert" className="text-sm text-destructive">{t("admin.loadError")}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Button onClick={() => setDialog({ kind: "invite" })}>{t("admin.inviteButton")}</Button>
      </div>
      {notice && (
        <p role={notice.kind === "error" ? "alert" : "status"}
           className={notice.kind === "error" ? "text-sm text-destructive" : "text-sm"}>
          {notice.text}
        </p>
      )}
      {summary && <SummaryCards summary={summary} />}
      <UsersToolbar query={query} summary={summary} onChange={update} />
      {page && (
        <>
          <UsersTable
            rows={page.rows}
            query={query}
            onSort={onSort}
            renderActions={() => null /* Task 7 */}
          />
          <UsersPagination query={query} total={page.total} onChange={update} />
        </>
      )}
      <div>
        <Button variant="outline" size="sm" onClick={() => setDialog({ kind: "matrix" })}>
          <Info />
          {t("admin.roleMatrix.button")}
        </Button>
      </div>
      {/* Dialogs are added in Tasks 7–9 and read `dialog`, `setDialog`, `reload`, `setNotice`. */}
      {dialog === undefined && reload && setNotice && null}
    </div>
  );
}
```

The last JSX line only keeps the not-yet-used state from tripping "unused" checks; Task 7 replaces it with the dialogs. Remove it there.

- [ ] **Step 7: Run the test and the type check**

Run: `cd frontend && npx vitest run tests/unit/user-management-page.test.tsx && npx tsc --noEmit`
Expected: PASS. If the tabs' accessible names differ (Radix renders `role="tab"`), adjust the regex in the test to the rendered name, not the component.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): add the user management page with list and summary" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 7: Row actions and the edit, block and remove dialogs

**Files:**
- Create: `frontend/src/components/admin/row-actions.tsx`, `edit-dialog.tsx`, `block-dialog.tsx`, `remove-dialog.tsx`
- Modify: `frontend/src/app/admin/users/user-management-content.tsx`
- Test: `frontend/tests/unit/admin-row-actions.test.tsx` (create)

**Interfaces:**
- Consumes: `DialogState`, `Notice`, `reload` (Task 6); `adminApi`, `errorKey`, `BLOCK_REASONS` (Task 5); `useAccountSession` for the own account id.
- Produces: `RowActions({ row, isSelf, onOpen(kind), onResend, onWithdraw, onUnblock })`; dialogs `{ row, onClose(), onDone(noticeText) }`.

- [ ] **Step 1: Write the failing test**

`frontend/tests/unit/admin-row-actions.test.tsx`:

```tsx
// frontend/tests/unit/admin-row-actions.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { RowActions } from "@/components/admin/row-actions";
import { RemoveDialog } from "@/components/admin/remove-dialog";
import type { AdminUserRow } from "@/lib/admin-api";

const base: AdminUserRow = {
  kind: "account", id: "7", email: "crawler@example.de", firstName: null, lastName: null,
  signInMethods: ["email"], role: "user", publisherId: null, publisherName: null,
  lastLoginAt: null, createdAt: "2026-10-10T00:00:00Z", status: "active",
  blockReason: null, expiresAt: null,
};
const originalFetch = global.fetch;

function openMenu(row: AdminUserRow, isSelf = false) {
  render(
    <LocaleProvider initialLocale="de">
      <RowActions row={row} isSelf={isSelf} onOpen={vi.fn()} onResend={vi.fn()}
                  onWithdraw={vi.fn()} onUnblock={vi.fn()} />
    </LocaleProvider>,
  );
  fireEvent.pointerDown(screen.getByRole("button", { name: `Aktionen für ${row.email}` }));
}

describe("row actions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("offers edit, block and remove for an active account", async () => {
    openMenu(base);
    expect(await screen.findByRole("menuitem", { name: "Bearbeiten" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sperren" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Entfernen" })).toBeInTheDocument();
  });

  it("offers unblock for a blocked account and resend/withdraw for an invitation", async () => {
    openMenu({ ...base, status: "blocked" });
    expect(await screen.findByRole("menuitem", { name: "Entsperren" })).toBeInTheDocument();
  });

  it("offers resend and withdraw for an invitation", async () => {
    openMenu({ ...base, kind: "invitation", status: "expired" });
    expect(await screen.findByRole("menuitem", { name: "Erneut senden" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Zurückziehen" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Sperren" })).not.toBeInTheDocument();
  });

  it("disables block and remove on the own row", async () => {
    openMenu({ ...base, role: "administrator" }, true);
    expect(await screen.findByRole("menuitem", { name: "Sperren" })).toHaveAttribute("data-disabled");
    expect(screen.getByRole("menuitem", { name: "Entfernen" })).toHaveAttribute("data-disabled");
  });

  it("enables removal only after the address is typed, then calls the API", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ email_sent: true }), { status: 200 }),
    );
    const onDone = vi.fn();
    render(
      <LocaleProvider initialLocale="de">
        <RemoveDialog row={base} onClose={vi.fn()} onDone={onDone} />
      </LocaleProvider>,
    );
    const confirm = screen.getByRole("button", { name: "Endgültig entfernen" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Zur Bestätigung die E-Mail-Adresse eingeben"),
                     { target: { value: "crawler@example.de" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("Konto entfernt."));
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/admin/accounts/7");
    expect(init.method).toBe("DELETE");
  });

  it("shows the backend error code as text", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "last_administrator" }), { status: 409 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <RemoveDialog row={{ ...base, role: "administrator" }} onClose={vi.fn()} onDone={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Zur Bestätigung die E-Mail-Adresse eingeben"),
                     { target: { value: "crawler@example.de" } });
    fireEvent.click(screen.getByRole("button", { name: "Endgültig entfernen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Der letzte Administrator kann nicht herabgestuft, gesperrt oder entfernt werden.",
    );
  });
});
```

Radix `DropdownMenu` opens on `pointerdown`; if the existing tests in the repo open menus differently (see `app-shell.test.tsx`), use that pattern.

- [ ] **Step 2: Run and see it fail**

Run: `cd frontend && npx vitest run tests/unit/admin-row-actions.test.tsx`
Expected: FAIL (modules missing).

- [ ] **Step 3: Row actions**

`frontend/src/components/admin/row-actions.tsx`:

```tsx
// frontend/src/components/admin/row-actions.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AdminUserRow } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function RowActions({
  row, isSelf, onOpen, onResend, onWithdraw, onUnblock,
}: {
  row: AdminUserRow;
  isSelf: boolean;
  onOpen: (kind: "edit" | "block" | "remove") => void;
  onResend: () => void;
  onWithdraw: () => void;
  onUnblock: () => void;
}) {
  const { t } = useTranslation();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" className="size-9"
                aria-label={interpolate(t("admin.actions.menu"), { email: row.email })}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {row.kind === "invitation" ? (
          <>
            <DropdownMenuItem onSelect={onResend}>{t("admin.actions.resend")}</DropdownMenuItem>
            <DropdownMenuItem onSelect={onWithdraw} className="text-destructive">
              {t("admin.actions.withdraw")}
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem onSelect={() => onOpen("edit")} disabled={isSelf}>
              {t("admin.actions.edit")}
            </DropdownMenuItem>
            {row.status === "blocked" ? (
              <DropdownMenuItem onSelect={onUnblock} disabled={isSelf}>
                {t("admin.actions.unblock")}
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onSelect={() => onOpen("block")} disabled={isSelf}>
                {t("admin.actions.block")}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => onOpen("remove")} disabled={isSelf}
                              className="text-destructive">
              {t("admin.actions.remove")}
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

(On the own row everything is disabled: the backend refuses every self action, and name/e-mail are edited in the profile.)

- [ ] **Step 4: The three dialogs**

`frontend/src/components/admin/remove-dialog.tsx`:

```tsx
// frontend/src/components/admin/remove-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { adminApi, errorKey, type AdminUserRow } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function RemoveDialog({
  row, onClose, onDone,
}: { row: AdminUserRow; onClose: () => void; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const [typed, setTyped] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const matches = typed.trim().toLowerCase() === row.email.toLowerCase();

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { emailSent } = await adminApi.remove(row.id, typed.trim());
      onDone(emailSent ? t("admin.notices.removed") : t("admin.notices.emailNotSent"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.remove.title")}</DialogTitle>
        <p className="text-sm text-muted-foreground">
          {interpolate(t("admin.remove.description"), { email: row.email })}
        </p>
        <label className="mt-4 flex flex-col gap-2 text-sm">
          {t("admin.remove.confirmLabel")}
          <Input value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" />
        </label>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("admin.remove.cancel")}</Button>
          <Button variant="destructive" disabled={!matches || busy} onClick={submit}>
            {t("admin.remove.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

`frontend/src/components/admin/block-dialog.tsx` — same structure; a `NativeSelect` labelled `t("admin.block.reason")` with one `<option>` per `BLOCK_REASONS` entry (`t(\`admin.blockReasons.${reason}\`)`), default `"bulk_retrieval"`; description `interpolate(t("admin.block.description"), { email })`; confirm button `t("admin.block.confirm")` (variant `destructive`) calls `adminApi.block(row.id, reason)` and on success `onDone(emailSent ? t("admin.notices.blocked") : t("admin.notices.emailNotSent"))`; errors as in `RemoveDialog`.

`frontend/src/components/admin/edit-dialog.tsx`:

```tsx
// frontend/src/components/admin/edit-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import { RoleBadge } from "@/components/admin/badges";
import { adminApi, errorKey, type AdminUserRow, type Publisher } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";

// Fewer rights at once, more rights only by invitation (ADR-030): a publisher
// can change its binding, publishers and administrators can be downgraded.
export function EditDialog({
  row, onClose, onDone,
}: { row: AdminUserRow; onClose: () => void; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const [publishers, setPublishers] = React.useState<Publisher[]>([]);
  const [publisherId, setPublisherId] = React.useState(row.publisherId ?? "");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (row.role !== "publisher") return;
    adminApi.publishers().then(setPublishers).catch(() => setPublishers([]));
  }, [row.role]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onDone(t("admin.notices.saved"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.edit.title")}</DialogTitle>
        <p className="text-sm">{row.email}</p>
        <div className="mt-2"><RoleBadge role={row.role} /></div>
        {row.role === "publisher" && (
          <label className="mt-4 flex flex-col gap-2 text-sm">
            {t("admin.edit.publisher")}
            <NativeSelect value={publisherId} onChange={(event) => setPublisherId(event.target.value)}>
              {publishers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </NativeSelect>
          </label>
        )}
        <p className="mt-4 text-sm text-muted-foreground">{t("admin.edit.upgradeHint")}</p>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("admin.edit.cancel")}</Button>
          {row.role !== "user" && (
            <Button variant="outline" disabled={busy}
                    onClick={() => run(() => adminApi.downgradeToUser(row.id))}>
              {t("admin.edit.downgrade")}
            </Button>
          )}
          {row.role === "publisher" && (
            <Button disabled={busy || !publisherId || publisherId === row.publisherId}
                    onClick={() => run(() => adminApi.changePublisher(row.id, publisherId))}>
              {t("admin.edit.save")}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 5: Wire into the page**

In `user-management-content.tsx`: get the own id with `const { account } = useAccountSession();`; replace `renderActions={() => null}` with:

```tsx
            renderActions={(row) => (
              <RowActions
                row={row}
                isSelf={row.kind === "account" && row.id === account?.accountId}
                onOpen={(kind) => setDialog({ kind, row })}
                onResend={() => quick(() => adminApi.resendInvitation(row.id), "admin.notices.resent")}
                onWithdraw={() => quick(() => adminApi.withdrawInvitation(row.id), "admin.notices.withdrawn")}
                onUnblock={() => quick(() => adminApi.unblock(row.id), "admin.notices.unblocked")}
              />
            )}
```

with the helper inside the component:

```tsx
  const done = (text: string) => {
    setDialog(null);
    setNotice({ kind: "success", text });
    reload();
  };
  async function quick(action: () => Promise<{ emailSent: boolean } | void>, key: TranslationKey) {
    try {
      const result = await action();
      done(result && result.emailSent === false ? t("admin.notices.emailNotSent") : t(key));
    } catch (failure) {
      setNotice({ kind: "error", text: t(errorKey(failure)) });
    }
  }
```

and render the dialogs (replacing the placeholder line):

```tsx
      {dialog?.kind === "edit" && <EditDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "block" && <BlockDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "remove" && <RemoveDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
```

- [ ] **Step 6: Run the tests and the type check**

Run: `cd frontend && npx vitest run tests/unit/admin-row-actions.test.tsx tests/unit/user-management-page.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): edit, block, unblock and remove accounts from the table" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 8: Invite dialog

**Files:**
- Create: `frontend/src/components/admin/invite-dialog.tsx`
- Modify: `frontend/src/app/admin/users/user-management-content.tsx`
- Test: `frontend/tests/unit/invite-dialog.test.tsx` (create)

**Interfaces:**
- Consumes: `adminApi.publishers/createPublisher/checkInvitation/invite`, `errorKey`, `ROLES`.
- Produces: `InviteDialog({ onClose, onDone(text) })`.

- [ ] **Step 1: Write the failing test**

`frontend/tests/unit/invite-dialog.test.tsx`:

```tsx
// frontend/tests/unit/invite-dialog.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { InviteDialog } from "@/components/admin/invite-dialog";

const originalFetch = global.fetch;

function mockApi(check = { existing_account: false, verified: false, blocked: false, open_invitation: false }) {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (url === "/api/admin/publishers" && (!init || !init.method)) {
      return Promise.resolve(new Response(JSON.stringify([{ id: "p1", name: "VDE Verlag" }])));
    }
    if (url === "/api/admin/publishers") {
      return Promise.resolve(new Response(JSON.stringify({ id: "p2", name: "DIN Media" }), { status: 201 }));
    }
    if (url.startsWith("/api/admin/invitations/check")) {
      return Promise.resolve(new Response(JSON.stringify(check)));
    }
    return Promise.resolve(new Response(JSON.stringify({ id: "i", email_sent: true }), { status: 201 }));
  });
}

function renderDialog(onDone = vi.fn()) {
  render(
    <LocaleProvider initialLocale="de">
      <InviteDialog onClose={vi.fn()} onDone={onDone} />
    </LocaleProvider>,
  );
  return onDone;
}

describe("InviteDialog", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("asks for a publisher only for the publisher role", async () => {
    mockApi();
    renderDialog();
    expect(screen.queryByLabelText("Verlagszuordnung")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    expect(await screen.findByLabelText("Verlagszuordnung")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "p@vde.example" } });
    expect(screen.getByRole("button", { name: "Einladung senden" })).toBeDisabled();
  });

  it("sends role, publisher, language and message", async () => {
    mockApi();
    const onDone = renderDialog();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "p@vde.example" } });
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    fireEvent.change(await screen.findByLabelText("Verlagszuordnung"), { target: { value: "p1" } });
    fireEvent.change(screen.getByLabelText("Sprache der Einladung"), { target: { value: "en" } });
    fireEvent.change(screen.getByLabelText("Persönliche Nachricht (optional)"), { target: { value: "Hallo" } });
    fireEvent.click(screen.getByRole("button", { name: "Einladung senden" }));

    await waitFor(() => expect(onDone).toHaveBeenCalledWith("Einladung an p@vde.example gesendet."));
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls
      .find(([url, init]) => url === "/api/admin/invitations" && init?.method === "POST");
    expect(JSON.parse(call![1].body)).toEqual({
      email: "p@vde.example", role: "publisher", publisher_id: "p1", locale: "en", message: "Hallo",
    });
  });

  it("warns about an unverified existing account and refuses a blocked one", async () => {
    mockApi({ existing_account: true, verified: false, blocked: false, open_invitation: false });
    renderDialog();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "x@example.de" } });
    fireEvent.blur(screen.getByLabelText("E-Mail-Adresse"));
    expect(await screen.findByText(/Das bestehende Konto ist unbestätigt/)).toBeInTheDocument();
  });

  it("creates a new publisher inline and selects it", async () => {
    mockApi();
    renderDialog();
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    fireEvent.change(await screen.findByLabelText("Verlagszuordnung"), { target: { value: "__new__" } });
    fireEvent.change(screen.getByLabelText("Name des Verlags"), { target: { value: "DIN Media" } });
    fireEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(screen.getByLabelText("Verlagszuordnung")).toHaveValue("p2"));
  });
});
```

- [ ] **Step 2: Run and see it fail**

Run: `cd frontend && npx vitest run tests/unit/invite-dialog.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`frontend/src/components/admin/invite-dialog.tsx`:

```tsx
// frontend/src/components/admin/invite-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  ROLES, adminApi, errorKey, type InvitationCheck, type Publisher, type Role,
} from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

const NEW_PUBLISHER = "__new__";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InviteDialog({ onClose, onDone }: { onClose: () => void; onDone: (text: string) => void }) {
  const { t, locale } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<Role>("user");
  const [publishers, setPublishers] = React.useState<Publisher[]>([]);
  const [publisherId, setPublisherId] = React.useState("");
  const [newName, setNewName] = React.useState("");
  const [language, setLanguage] = React.useState<"de" | "en">(locale);
  const [message, setMessage] = React.useState("");
  const [check, setCheck] = React.useState<InvitationCheck | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (role !== "publisher" || publishers.length) return;
    adminApi.publishers().then(setPublishers).catch(() => setPublishers([]));
  }, [role, publishers.length]);

  async function runCheck() {
    if (!EMAIL_PATTERN.test(email.trim())) {
      setCheck(null);
      return;
    }
    try {
      setCheck(await adminApi.checkInvitation(email.trim()));
    } catch {
      setCheck(null);
    }
  }

  async function addPublisher() {
    setError(null);
    try {
      const created = await adminApi.createPublisher(newName.trim());
      setPublishers((list) => [...list, created].sort((a, b) => a.name.localeCompare(b.name)));
      setPublisherId(created.id);
      setNewName("");
    } catch (failure) {
      setError(t(errorKey(failure)));
    }
  }

  const needsPublisher = role === "publisher";
  const canSend = EMAIL_PATTERN.test(email.trim())
    && (!needsPublisher || (publisherId !== "" && publisherId !== NEW_PUBLISHER))
    && !check?.blocked && message.length <= 500 && !busy;

  async function send() {
    setBusy(true);
    setError(null);
    try {
      const { emailSent } = await adminApi.invite({
        email: email.trim(), role, publisherId: needsPublisher ? publisherId : null,
        locale: language, message,
      });
      onDone(emailSent
        ? interpolate(t("admin.notices.invited"), { email: email.trim() })
        : t("admin.notices.emailNotSent"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogTitle>{t("admin.invite.title")}</DialogTitle>
        <div className="mt-4 grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.email")}
            <Input type="email" required placeholder={t("admin.invite.emailPlaceholder")} value={email}
                   onChange={(event) => { setEmail(event.target.value); setCheck(null); }}
                   onBlur={runCheck} />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.role")}
            <NativeSelect value={role} onChange={(event) => setRole(event.target.value as Role)}>
              {ROLES.map((r) => <option key={r} value={r}>{t(`admin.roles.${r}`)}</option>)}
            </NativeSelect>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.language")}
            <NativeSelect value={language} onChange={(event) => setLanguage(event.target.value as "de" | "en")}>
              <option value="de">{t("admin.invite.languageDe")}</option>
              <option value="en">{t("admin.invite.languageEn")}</option>
            </NativeSelect>
          </label>
        </div>
        {needsPublisher && (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              {t("admin.invite.publisher")}
              <NativeSelect value={publisherId} onChange={(event) => setPublisherId(event.target.value)}>
                <option value="" disabled>{t("admin.invite.publisherPlaceholder")}</option>
                {publishers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                <option value={NEW_PUBLISHER}>{t("admin.invite.newPublisher")}</option>
              </NativeSelect>
            </label>
            {publisherId === NEW_PUBLISHER && (
              <div className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-2 text-sm">
                  {t("admin.invite.newPublisherName")}
                  <Input value={newName} onChange={(event) => setNewName(event.target.value)} />
                </label>
                <Button variant="outline" disabled={!newName.trim()} onClick={addPublisher}>
                  {t("admin.invite.addPublisher")}
                </Button>
              </div>
            )}
          </div>
        )}
        <label className="mt-4 flex flex-col gap-2 text-sm">
          {t("admin.invite.message")}
          <Textarea maxLength={500} placeholder={t("admin.invite.messagePlaceholder")} value={message}
                    onChange={(event) => setMessage(event.target.value)} />
        </label>
        {check?.blocked && <p role="alert" className="mt-3 text-sm text-destructive">{t("admin.invite.blockedAccount")}</p>}
        {check && !check.blocked && check.existingAccount && (
          <p className="mt-3 text-sm">
            {check.verified ? t("admin.invite.existingAccount") : t("admin.invite.unverifiedAccount")}
          </p>
        )}
        {check?.openInvitation && <p className="mt-2 text-sm">{t("admin.invite.openInvitation")}</p>}
        <p className="mt-3 text-sm text-muted-foreground">{t("admin.invite.help")}</p>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-start gap-2">
          <Button disabled={!canSend} onClick={send}>{t("admin.invite.send")}</Button>
          <Button variant="outline" onClick={onClose}>{t("admin.invite.cancel")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

In `user-management-content.tsx` add `{dialog?.kind === "invite" && <InviteDialog onClose={() => setDialog(null)} onDone={done} />}`.

- [ ] **Step 4: Run the tests and the type check**

Run: `cd frontend && npx vitest run tests/unit/invite-dialog.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): invite users with role, publisher and message" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 9: "What the roles see" dialog

**Files:**
- Create: `frontend/src/components/admin/role-matrix-dialog.tsx`
- Modify: `frontend/src/app/admin/users/user-management-content.tsx`
- Test: `frontend/tests/unit/role-matrix-dialog.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/unit/role-matrix-dialog.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { RoleMatrixDialog } from "@/components/admin/role-matrix-dialog";

const originalFetch = global.fetch;

describe("RoleMatrixDialog", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the server's matrix with translated labels and planned markers", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      roles: ["anonymous", "user", "publisher", "administrator"],
      rows: [
        { capability: "chats_of_others", planned: false,
          values: { anonymous: "no", user: "no", publisher: "no", administrator: "no" } },
        { capability: "usage_and_demand", planned: true,
          values: { anonymous: "no", user: "no", publisher: "aggregated_own", administrator: "all" } },
      ],
    })));
    render(<LocaleProvider initialLocale="de"><RoleMatrixDialog onClose={vi.fn()} /></LocaleProvider>);

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Anonym" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Nutzung und Nachfrage/ });
    expect(within(row).getByText("geplant")).toBeInTheDocument();
    expect(within(row).getByText("eigene Inhalte, aggregiert")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run and see it fail**

Run: `cd frontend && npx vitest run tests/unit/role-matrix-dialog.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/admin/role-matrix-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminApi, type RoleMatrix } from "@/lib/admin-api";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useTranslation } from "@/lib/i18n/provider";

// Built from the same definition the server checks (permissions.py), so the
// dialog cannot promise what the server does not enforce.
export function RoleMatrixDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [matrix, setMatrix] = React.useState<RoleMatrix | null>(null);
  const [failed, setFailed] = React.useState(false);
  const label = (key: string) => t(key as TranslationKey);

  React.useEffect(() => {
    adminApi.roleMatrix().then(setMatrix).catch(() => setFailed(true));
  }, []);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogTitle>{t("admin.roleMatrix.title")}</DialogTitle>
        {failed && <p role="alert" className="text-sm text-destructive">{t("admin.loadError")}</p>}
        {matrix && (
          <div className="mt-4 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-left"><span className="sr-only">{t("admin.columns.role")}</span></TableHead>
                  {matrix.roles.map((role) => (
                    <TableHead key={role} className="text-left">{label(`admin.roleMatrix.roles.${role}`)}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {matrix.rows.map((row) => (
                  <TableRow key={row.capability}>
                    <TableCell className="text-left text-muted-foreground">
                      {label(`admin.roleMatrix.capabilities.${row.capability}`)}
                      {row.planned && <Badge variant="muted" className="ml-2">{t("admin.roleMatrix.planned")}</Badge>}
                    </TableCell>
                    {matrix.roles.map((role) => (
                      <TableCell key={role} className="text-left">
                        {label(`admin.roleMatrix.values.${row.values[role]}`)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

In the page add `{dialog?.kind === "matrix" && <RoleMatrixDialog onClose={() => setDialog(null)} />}`.

- [ ] **Step 4: Run tests and type check; commit**

Run: `cd frontend && npx vitest run tests/unit/role-matrix-dialog.test.tsx && npx tsc --noEmit` — Expected: PASS.

```bash
git add frontend
git commit -s -m "feat(frontend): show what each role sees" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 10: Invitation page, blocked notices, last-administrator message

**Files:**
- Create: `frontend/src/app/invitation/page.tsx`, `frontend/src/app/invitation/invitation-page-content.tsx`
- Create: `frontend/src/components/auth/blocked-notice.tsx`
- Modify: `frontend/src/app/login/page.tsx`, `frontend/src/app/login/login-page-content.tsx`, `frontend/src/components/auth/login-form.tsx`
- Modify: `frontend/src/app/magic-link/page.tsx`, `frontend/src/app/magic-link/magic-link-page-content.tsx`
- Modify: `frontend/src/app/api/auth/google/callback/route.ts`
- Modify: `frontend/src/components/account/delete-account-section.tsx`
- Test: `frontend/tests/unit/invitation-page.test.tsx` (create); append to `login-form.test.tsx`, `magic-link-page.test.tsx`, `auth-routes.test.ts` (Google callback) and `delete-account-section.test.tsx`

**Interfaces:**
- Produces: `BlockedNotice({ contact }: { contact: string | null })`; `LoginForm` optional prop `contact?: string | null`; Google callback redirects a blocked account to `/login?auth_error=blocked`.

- [ ] **Step 1: Write the failing tests**

`frontend/tests/unit/invitation-page.test.tsx`:

```tsx
// frontend/tests/unit/invitation-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { InvitationPageContent } from "@/app/invitation/invitation-page-content";

const push = vi.fn();
let search = "token=inv-1";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));
const originalFetch = global.fetch;

function renderPage() {
  render(<LocaleProvider initialLocale="de"><InvitationPageContent contact="kontakt@normly.example" /></LocaleProvider>);
}

describe("invitation page", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    search = "token=inv-1";
    push.mockReset();
  });

  it("does nothing until the button is clicked, then accepts and goes home", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ session_token: "s" })));
    renderPage();
    expect(global.fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Einladung annehmen" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/auth/invitation/accept");
    expect(JSON.parse(init.body)).toEqual({ token: "inv-1" });
  });

  it.each([
    [410, "invitation_invalid", /ungültig oder abgelaufen/],
    [403, "account_blocked", /Dein Konto ist gesperrt/],
    [409, "last_administrator", /letzten Administrator/],
  ])("shows the %s state", async (status, detail, text) => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status }));
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Einladung annehmen" }));
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("explains a link without token", () => {
    search = "";
    renderPage();
    expect(screen.getByText(/Link ist unvollständig/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Einladung annehmen" })).not.toBeInTheDocument();
  });
});
```

Append to `frontend/tests/unit/login-form.test.tsx` (follow its render helper):

```tsx
  it("shows the blocked notice with the contact on account_blocked", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "account_blocked" }), { status: 403 }),
    );
    render(<LocaleProvider initialLocale="de"><LoginForm onSuccess={vi.fn()} contact="kontakt@normly.example" /></LocaleProvider>);
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "a@b.de" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));
    expect(await screen.findByText("Dein Konto ist gesperrt. Eine Anmeldung ist nicht möglich.")).toBeInTheDocument();
    expect(screen.getByText("Bei Fragen wende dich an kontakt@normly.example.")).toBeInTheDocument();
  });
```

(Adapt labels/button names to what `login-form.test.tsx` already uses.)

Append to the Google-callback test (in `auth-routes.test.ts`, or wherever `/api/auth/google/callback` is tested):

```ts
  it("sends a blocked account to the login page with a blocked hint", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "account_blocked" }), { status: 403 }),
    );
    const response = await GET(new NextRequest("http://localhost/api/auth/google/callback?code=c&state=s"));
    expect(response.headers.get("location")).toBe("http://localhost/login?auth_error=blocked");
  });
```

Append to `delete-account-section.test.tsx` a case: the delete request answers `409 {"detail": "last_administrator"}` → the section shows `"Du bist der letzte Administrator. Mache zuerst eine andere Person zum Administrator."` (follow the file's existing render and click steps).

Append to `magic-link-page.test.tsx` a case: confirm answers `403 {"detail": "account_blocked"}` → `"Dein Konto ist gesperrt. Eine Anmeldung ist nicht möglich."` is shown.

- [ ] **Step 2: Run and see them fail**

Run: `cd frontend && npx vitest run tests/unit/invitation-page.test.tsx tests/unit/login-form.test.tsx tests/unit/magic-link-page.test.tsx tests/unit/auth-routes.test.ts tests/unit/delete-account-section.test.tsx`
Expected: the new cases FAIL.

- [ ] **Step 3: Blocked notice**

`frontend/src/components/auth/blocked-notice.tsx`:

```tsx
// frontend/src/components/auth/blocked-notice.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

// Neutral on purpose: no reason, only where to ask (ADR-030).
export function BlockedNotice({ contact }: { contact: string | null }) {
  const { t } = useTranslation();
  return (
    <div role="alert" className="rounded-md border border-destructive/50 p-3 text-sm">
      <p>{t("auth.accountBlocked")}</p>
      {contact && <p className="mt-1">{interpolate(t("auth.accountBlockedContact"), { contact })}</p>}
    </div>
  );
}
```

(If `border-destructive/50` is not generated under this project's Tailwind 3 config — the opacity-modifier trap noted in `app-shell.tsx` — use `border-destructive`.)

- [ ] **Step 4: Invitation page**

`frontend/src/app/invitation/page.tsx`:

```tsx
// frontend/src/app/invitation/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Suspense } from "react";
import { getInstanceConfig } from "@/lib/config";
import { InvitationPageContent } from "./invitation-page-content";

export default function InvitationPage() {
  return (
    <Suspense fallback={null}>
      <InvitationPageContent contact={getInstanceConfig().contactAddress} />
    </Suspense>
  );
}
```

`frontend/src/app/invitation/invitation-page-content.tsx`:

```tsx
// frontend/src/app/invitation/invitation-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { BlockedNotice } from "@/components/auth/blocked-notice";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

type State = "ready" | "accepting" | "invalid" | "blocked" | "lastAdministrator" | "error";

// Unlike the magic link, nothing happens on load: accepting binds a role, so
// it needs a deliberate click, and link scanners cannot use up the token.
export function InvitationPageContent({ contact }: { contact: string | null }) {
  const { t } = useTranslation();
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [state, setState] = React.useState<State>("ready");

  async function accept() {
    setState("accepting");
    try {
      const response = await fetch("/api/auth/invitation/accept", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (response.ok) {
        router.push("/");
        return;
      }
      const body = await response.json().catch(() => ({}));
      setState(
        body.detail === "account_blocked" ? "blocked"
          : body.detail === "last_administrator" ? "lastAdministrator"
            : response.status === 410 ? "invalid" : "error",
      );
    } catch {
      setState("error");
    }
  }

  return (
    <AuthSplitLayout headingKey="invitation.heading" descriptionKey={token ? "invitation.description" : undefined}>
      {!token && <p className="text-sm">{t("invitation.missingToken")}</p>}
      {token && (state === "ready" || state === "accepting") && (
        <Button onClick={accept} disabled={state === "accepting"}>
          {state === "accepting" ? t("invitation.accepting") : t("invitation.accept")}
        </Button>
      )}
      {state === "invalid" && <p role="alert" className="text-sm text-destructive">{t("invitation.invalid")}</p>}
      {state === "blocked" && <BlockedNotice contact={contact} />}
      {state === "lastAdministrator" && (
        <p role="alert" className="text-sm text-destructive">{t("invitation.lastAdministrator")}</p>
      )}
      {state === "error" && <p role="alert" className="text-sm text-destructive">{t("admin.errors.generic")}</p>}
    </AuthSplitLayout>
  );
}
```

Check `AuthSplitLayout`'s prop types (`headingKey`, `descriptionKey`) and adapt if they differ.

- [ ] **Step 5: Sign-in paths**

- `login/page.tsx`: render `<LoginPageContent contact={getInstanceConfig().contactAddress} />` inside `<Suspense fallback={null}>`.
- `login-page-content.tsx`: accept `contact: string | null`; read `useSearchParams().get("auth_error") === "blocked"` and render `<BlockedNotice contact={contact} />` above the form in that case; pass `contact` to `<LoginForm … contact={contact} />`.
- `login-form.tsx`: add the optional prop `contact?: string | null`; replace the boolean `error` state with `"none" | "generic" | "blocked"`; on a non-OK response read the body and set `"blocked"` when `detail === "account_blocked"`, else `"generic"`; render `<BlockedNotice contact={contact ?? null} />` for `"blocked"` and the existing generic text otherwise.
- `magic-link/page.tsx` + content: same `contact` plumbing; in `MagicLinkConfirm`, on a non-OK response read the body and show `<BlockedNotice>` for `account_blocked`, the existing invalid message otherwise.
- `api/auth/google/callback/route.ts`: before the generic error redirect:

```ts
  if (backendResponse.status === 403 && body.detail === "account_blocked") {
    return NextResponse.redirect(new URL("/login?auth_error=blocked", request.url));
  }
```

- `delete-account-section.tsx`: when the delete request answers 409 with `detail === "last_administrator"`, show `t("account.deleteLastAdministrator")` instead of the generic error.

- [ ] **Step 6: Run the tests, the whole unit suite and the type check**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS (whole suite — the login form and pages are covered by several existing tests).

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -s -m "feat(frontend): accept invitations and explain blocked accounts" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 11: End-to-end test, build and docs

**Files:**
- Create: `frontend/tests/e2e/user-management.spec.ts`
- Modify: `docs/guide/operations.md` (one short "User management" paragraph pointing to the page and `grant-admin`), `docs/superpowers/specs/2026-10-31-user-management-design.md` (frontend section: native selects instead of shadcn `select`/`card`/`alert-dialog`; one catch-all proxy instead of one route per endpoint; invitation states)

- [ ] **Step 1: Write the e2e spec**

The e2e suite runs against a full local stack (`docker compose up`, see `docs/guide/getting-started.md`) and is not part of CI. This spec additionally needs an administrator and Mailpit; it skips itself without them.

```ts
// frontend/tests/e2e/user-management.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { expect, test } from "@playwright/test";

// Needs: a running stack, an administrator created with
// `docker compose run --rm pipeline grant-admin --email $E2E_ADMIN_EMAIL`
// and Mailpit's API (compose service `mailpit`, default http://127.0.0.1:8025).
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://127.0.0.1:8025";

test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD");

async function invitationLink(request: import("@playwright/test").APIRequestContext, to: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const list = await (await request.get(`${MAILPIT}/api/v1/search?query=to:${encodeURIComponent(to)}`)).json();
    if (list.messages?.length) {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${list.messages[0].ID}`)).json();
      const match = /https?:\/\/\S+\/invitation\?token=[\w-]+/.exec(message.Text);
      if (match) return match[0];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no invitation mail for ${to}`);
}

test("an administrator invites a publisher, who accepts; then blocks them", async ({ page, browser, request }) => {
  const invited = `e2e-publisher-${Date.now()}@example.de`;
  const publisher = `E2E Verlag ${Date.now()}`;

  await page.goto("/login");
  await page.getByLabel("E-Mail-Adresse").fill(ADMIN_EMAIL!);
  await page.getByLabel("Passwort").fill(ADMIN_PASSWORD!);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.getByRole("link", { name: "Nutzermanagement" }).click();
  await expect(page).toHaveURL(/\/admin\/users/);

  await page.getByRole("button", { name: "Nutzer einladen" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(invited);
  await page.getByLabel("Rolle").selectOption("publisher");
  await page.getByLabel("Verlagszuordnung").selectOption("__new__");
  await page.getByLabel("Name des Verlags").fill(publisher);
  await page.getByRole("button", { name: "Anlegen" }).click();
  await page.getByRole("button", { name: "Einladung senden" }).click();
  await expect(page.getByRole("status")).toContainText(invited);

  const link = await invitationLink(request, invited);
  const invitee = await (await browser.newContext({ locale: "de-DE" })).newPage();
  await invitee.goto(link.replace(/^https?:\/\/[^/]+/, ""));
  await invitee.getByRole("button", { name: "Einladung annehmen" }).click();
  await expect(invitee).toHaveURL(/\/$/);

  await page.getByRole("searchbox", { name: "Konten durchsuchen" }).fill(invited);
  const row = page.getByRole("row", { name: new RegExp(invited) });
  await expect(row).toContainText(publisher);
  await expect(row).toContainText("Aktiv");

  await row.getByRole("button", { name: `Aktionen für ${invited}` }).click();
  await page.getByRole("menuitem", { name: "Sperren" }).click();
  await page.getByRole("button", { name: "Sperren" }).click();
  await expect(row).toContainText("Gesperrt");

  await invitee.reload();
  await expect(invitee.getByRole("link", { name: "Anmelden" })).toBeVisible();
});
```

- [ ] **Step 2: Run it if the stack is available**

Run (from `frontend/`, with the stack up and an administrator granted): `E2E_ADMIN_EMAIL=… E2E_ADMIN_PASSWORD=… npx playwright test tests/e2e/user-management.spec.ts`
Expected: PASS. If the stack cannot be started in this environment, report that the e2e test was not run and why.

- [ ] **Step 3: Docs**

`docs/guide/operations.md`: after the "Granting the first administrator" section add:

```markdown
Further administrators and publishers are invited from **User management**
(`/admin/users`, visible to administrators in the sidebar). Accounts can be
downgraded, blocked or removed there; every action is recorded in the
admin audit log (ADR-030).
```

Spec frontend section: replace the shadcn component list with "native `<select>` elements styled like inputs, plain `div` cards and the existing `Dialog`; no new dependencies", replace "`/api/admin/*` — BFF pass-through routes" with "one catch-all pass-through `/api/admin/[...path]`", and list the invitation page states `ready, accepting, invalid, blocked, last administrator, missing token`.

- [ ] **Step 4: Full verification**

Run: `cd frontend && npm test && npx tsc --noEmit && npm run build` and `cd accounts && ../.venv/bin/pytest -q` and `cd core && ../.venv/bin/pytest -q`.
Expected: all green; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend docs
git commit -s -m "test(frontend): cover the invitation flow end to end" -m "Refs: #60" -m "Assisted-by: Claude Code"
```
