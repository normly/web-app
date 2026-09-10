# accounts/ Commit-Timing Sweep, Test Hardening, and Two Small Data Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close a "response sent before DB commit" hazard across 17 `accounts/` endpoints, replace an unwitting-passes-either-way regression test with one that actually proves real durability, and fix two small, independent, low-risk `core/` data-correctness gaps.

**Architecture:** Three tasks. Task 1 applies one mechanical fix pattern (an explicit `session.commit()` before returning) across 17 endpoints in `accounts/`. Task 2 hardens the test suite that verifies this class of fix, using a corrected understanding of what a `TestClient`-based test can and cannot prove (see the spec's own "Wichtige Korrektur" section — read `docs/superpowers/specs/2026-09-10-accounts-commit-timing-design.md` for the full rationale before starting Task 2). Task 3 is two small, `core/`-only, completely independent fixes bundled into this same plan because they're equally mechanical/low-risk.

**Tech Stack:** FastAPI + SQLAlchemy (`accounts/`, `core/`), pytest + testcontainers.

## Global Constraints

- DCO `Signed-off-by` (via `git commit -s` — the human's identity is already configured in git config, never type a literal placeholder Signed-off-by line) + Conventional Commits + a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer on every commit.
- No behavior change beyond commit timing in Task 1 — same status codes, same response bodies, same field names, no new features, no API contract changes.
- Task 3's two fixes are documentation/timestamp-correctness only — no schema migration for either.
- Each task is its own commit(s), independently revertible.
- No push/PR/merge without explicit confirmation first (billed STACKIT CI runs, no working cancel API). Never push `main` directly, even after a local merge — always via a branch + PR, per the lesson from this session's immediately preceding sub-project.

---

### Task 1: Commit-timing sweep across 17 `accounts/` endpoints

**Files:**
- Modify: `accounts/src/normly_accounts/routers/email_verification.py`
- Modify: `accounts/src/normly_accounts/routers/password.py`
- Modify: `accounts/src/normly_accounts/routers/email_change.py`
- Modify: `accounts/src/normly_accounts/routers/login.py`
- Modify: `accounts/src/normly_accounts/routers/notifications.py`
- Modify: `accounts/src/normly_accounts/routers/profile.py`
- Modify: `accounts/src/normly_accounts/routers/watchlist.py`
- Modify: `accounts/src/normly_accounts/routers/magic_link.py`
- Modify: `accounts/src/normly_accounts/routers/sessions.py`
- Modify: `accounts/src/normly_accounts/routers/password_reset.py`
- Modify: `accounts/src/normly_accounts/routers/google.py`

**Interfaces:**
- Consumes: nothing from another task.
- Produces: nothing another task in this plan depends on for correctness (Task 2's password-change test exercises `password.py`'s fix, but per the spec's own correction, cannot actually distinguish fixed-vs-unfixed behavior via `TestClient` — Task 2 still runs after Task 1 for a coherent commit history).

**Context:** `accounts/src/normly_accounts/dependencies.py`'s `get_session()` only commits when FastAPI tears down the yield-dependency, which happens **after** the HTTP response is already sent. Two endpoints already guard against this correctly (`_create_session_response()` in `login.py`, used by `login`/`register`/`confirm_magic_link`/`google_callback`; and `delete_account` in `account_management.py`) — do not touch either. The 17 endpoints below do not. The fix is identical in shape everywhere: add `session.commit()` right after the write completes and before the function returns (or before any read-back whose result is what gets returned).

- [ ] **Step 1: Confirm the current test file names**

Run: `ls accounts/tests/`

Expected (used by this task's gates below): `test_email_verification.py`, `test_set_password.py`, `test_email_change.py`, `test_login.py`, `test_notifications.py`, `test_profile.py`, `test_watchlist.py`, `test_magic_link.py`, `test_account_sessions_endpoint.py`, `test_password_reset.py`, `test_google_login.py` all exist. If any name differs from this list, use the real name for that file's gate in the steps below.

- [ ] **Step 2: Fix `email_verification.py` (2 sites)**

In `verify_email` (`GET /verify-email`), change:
```python
    PostgresAccountRepository(session).mark_email_verified(
        consumed.account_id, datetime.now(timezone.utc)
    )
    return {"status": "email_verified"}
```
to:
```python
    PostgresAccountRepository(session).mark_email_verified(
        consumed.account_id, datetime.now(timezone.utc)
    )
    session.commit()
    return {"status": "email_verified"}
```

In `resend_verification_email` (`POST /verify-email/resend`), change:
```python
        except Exception:
            # Same rationale as every other best-effort send in this
            # codebase (password_reset.py, registration.py, magic_link.py):
            # the request itself must not fail when SMTP is unreachable.
            # Log that a delivery failure happened, for on-call
            # observability, same as those other routers -- but never the
            # token itself.
            logger.exception("verify-email resend delivery failed for %s", account.email)
    # Same response regardless of whether the account exists or is
    # already verified -- enumeration protection, same principle as
    # password-reset's own request endpoint.
    return {"status": "if_the_account_exists_and_is_unverified_an_email_was_sent"}
```
to:
```python
        except Exception:
            # Same rationale as every other best-effort send in this
            # codebase (password_reset.py, registration.py, magic_link.py):
            # the request itself must not fail when SMTP is unreachable.
            # Log that a delivery failure happened, for on-call
            # observability, same as those other routers -- but never the
            # token itself.
            logger.exception("verify-email resend delivery failed for %s", account.email)
    session.commit()
    # Same response regardless of whether the account exists or is
    # already verified -- enumeration protection, same principle as
    # password-reset's own request endpoint.
    return {"status": "if_the_account_exists_and_is_unverified_an_email_was_sent"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_email_verification.py -v`
Expected: all tests still pass.

- [ ] **Step 3: Fix `password.py` (1 site)**

Change:
```python
    PostgresAccountRepository(session).set_password_hash(
        account.id, hash_password(payload.new_password)
    )
    return {"status": "password_set"}
```
to:
```python
    PostgresAccountRepository(session).set_password_hash(
        account.id, hash_password(payload.new_password)
    )
    session.commit()
    return {"status": "password_set"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_set_password.py -v`
Expected: all tests still pass.

- [ ] **Step 4: Fix `email_change.py` (2 sites)**

In `request_email_change` (`POST /change`), change:
```python
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
    return {"status": "confirmation_sent"}
```
to:
```python
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
    session.commit()
    return {"status": "confirmation_sent"}
```

In `confirm_email_change` (`GET /confirm`), change:
```python
    try:
        account_repo.update_email(consumed.account_id, email)
    except EmailAlreadyRegisteredError:
        # The pre-check above narrows but does not close the race: a second
        # confirm for the same newly-freed address can still slip past it
        # and hit uq_account_email in update_email itself. Same response as
        # the pre-check, so the client sees one consistent 409 either way.
        raise HTTPException(status_code=409, detail="an account already exists for this email")
    return {"status": "email_changed"}
```
to:
```python
    try:
        account_repo.update_email(consumed.account_id, email)
    except EmailAlreadyRegisteredError:
        # The pre-check above narrows but does not close the race: a second
        # confirm for the same newly-freed address can still slip past it
        # and hit uq_account_email in update_email itself. Same response as
        # the pre-check, so the client sees one consistent 409 either way.
        raise HTTPException(status_code=409, detail="an account already exists for this email")
    session.commit()
    return {"status": "email_changed"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_email_change.py -v`
Expected: all tests still pass.

- [ ] **Step 5: Fix `login.py` (1 site — `_create_session_response` and `login` itself are already safe, do not touch them)**

In `logout` (`POST /logout`), change:
```python
@login_router.post("/logout")
def logout(payload: LogoutRequest, session: Session = Depends(get_session)) -> dict:
    PostgresAccountSessionRepository(session).revoke_session(payload.session_token)
    return {"status": "logged_out"}
```
to:
```python
@login_router.post("/logout")
def logout(payload: LogoutRequest, session: Session = Depends(get_session)) -> dict:
    PostgresAccountSessionRepository(session).revoke_session(payload.session_token)
    session.commit()
    return {"status": "logged_out"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_login.py -v`
Expected: all tests still pass.

- [ ] **Step 6: Fix `notifications.py` (1 site)**

Change:
```python
    repo = PostgresNotificationRepository(session)
    updated = repo.mark_read(
        notification_id, account_id=account.id, read_at=datetime.now(timezone.utc)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="notification not found")
    notifications = repo.list_for_account(account.id)
    return _notification_response(next(n for n in notifications if n.id == notification_id))
```
to:
```python
    repo = PostgresNotificationRepository(session)
    updated = repo.mark_read(
        notification_id, account_id=account.id, read_at=datetime.now(timezone.utc)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="notification not found")
    session.commit()
    notifications = repo.list_for_account(account.id)
    return _notification_response(next(n for n in notifications if n.id == notification_id))
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_notifications.py -v`
Expected: all tests still pass.

- [ ] **Step 7: Fix `profile.py` (3 sites)**

In `update_profile` (`PATCH /profile`), change:
```python
        account_repo.update_notification_preference(account.id, preference=preference)
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.post("/avatar", response_model=AccountResponse)
```
to:
```python
        account_repo.update_notification_preference(account.id, preference=preference)
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.post("/avatar", response_model=AccountResponse)
```

In `upload_avatar` (`POST /avatar`), change:
```python
    account_repo = PostgresAccountRepository(session)
    account_repo.set_avatar(
        account.id, avatar_image=buffer.getvalue(), avatar_content_type="image/jpeg"
    )
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.delete("/avatar", response_model=AccountResponse)
```
to:
```python
    account_repo = PostgresAccountRepository(session)
    account_repo.set_avatar(
        account.id, avatar_image=buffer.getvalue(), avatar_content_type="image/jpeg"
    )
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.delete("/avatar", response_model=AccountResponse)
```

In `delete_avatar` (`DELETE /avatar`), change:
```python
    account_repo = PostgresAccountRepository(session)
    account_repo.clear_avatar(account.id)
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)
```
to:
```python
    account_repo = PostgresAccountRepository(session)
    account_repo.clear_avatar(account.id)
    session.commit()
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_profile.py -v`
Expected: all tests still pass.

- [ ] **Step 8: Fix `watchlist.py` (2 sites)**

In `add_watch` (`POST /watchlist`), change:
```python
    try:
        watch = PostgresWatchlistRepository(session).add_watch(
            account_id=account.id, work_id=payload.work_id
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="work not found")
    return WatchlistEntryResponse(work_id=watch.work_id, created_at=watch.created_at)
```
to:
```python
    try:
        watch = PostgresWatchlistRepository(session).add_watch(
            account_id=account.id, work_id=payload.work_id
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="work not found")
    session.commit()
    return WatchlistEntryResponse(work_id=watch.work_id, created_at=watch.created_at)
```

In `remove_watch` (`DELETE /watchlist/{work_id}`), change:
```python
    PostgresWatchlistRepository(session).remove_watch(account_id=account.id, work_id=work_id)
    return {"status": "removed"}
```
to:
```python
    PostgresWatchlistRepository(session).remove_watch(account_id=account.id, work_id=work_id)
    session.commit()
    return {"status": "removed"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_watchlist.py -v`
Expected: all tests still pass.

- [ ] **Step 9: Fix `magic_link.py` (1 site — `confirm_magic_link` already goes through `_create_session_response`, already safe, do not touch it)**

In `request_magic_link` (`POST /request`), change:
```python
    except Exception:
        # Per the design spec: the magic-link request itself must not fail
        # when SMTP is unreachable -- the token is already persisted, delivery
        # is decoupled (no retry mechanism yet, tracked as an accepted open
        # point). Never log the token itself.
        logger.exception("magic link email delivery failed for %s", payload.email)
    return {"status": "if_the_request_is_valid_an_email_was_sent"}
```
to:
```python
    except Exception:
        # Per the design spec: the magic-link request itself must not fail
        # when SMTP is unreachable -- the token is already persisted, delivery
        # is decoupled (no retry mechanism yet, tracked as an accepted open
        # point). Never log the token itself.
        logger.exception("magic link email delivery failed for %s", payload.email)
    session.commit()
    return {"status": "if_the_request_is_valid_an_email_was_sent"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_magic_link.py -v`
Expected: all tests still pass.

- [ ] **Step 10: Fix `sessions.py` (1 site)**

Change:
```python
    revoked = PostgresAccountSessionRepository(session).revoke_session_by_id(
        session_id, account.id
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "session_revoked"}
```
to:
```python
    revoked = PostgresAccountSessionRepository(session).revoke_session_by_id(
        session_id, account.id
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="session not found")
    session.commit()
    return {"status": "session_revoked"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_account_sessions_endpoint.py -v`
Expected: all tests still pass.

- [ ] **Step 11: Fix `password_reset.py` (2 sites)**

In `request_password_reset` (`POST /request`), change:
```python
            logger.exception("password reset email delivery failed for %s", account.email)
    # Same response whether or not the account exists -- enumeration
    # protection, same principle as login's generic 401.
    return {"status": "if_the_account_exists_an_email_was_sent"}
```
to:
```python
            logger.exception("password reset email delivery failed for %s", account.email)
    session.commit()
    # Same response whether or not the account exists -- enumeration
    # protection, same principle as login's generic 401.
    return {"status": "if_the_account_exists_an_email_was_sent"}
```

In `confirm_password_reset` (`POST /confirm`), change:
```python
    PostgresAccountRepository(session).set_password_hash(
        token.account_id, hash_password(payload.new_password)
    )
    return {"status": "password_changed"}
```
to:
```python
    PostgresAccountRepository(session).set_password_hash(
        token.account_id, hash_password(payload.new_password)
    )
    session.commit()
    return {"status": "password_changed"}
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_password_reset.py -v`
Expected: all tests still pass.

- [ ] **Step 12: Fix `google.py` (1 site — `google_callback` already goes through `_create_session_response`, already safe, do not touch it)**

In `google_login` (`GET /login`), change:
```python
    state_repo.delete_states_before(now - _STATE_RETENTION)
    state_repo.create_state(state=state, created_at=now, expires_at=now + _STATE_TTL)
    url = google_client.build_authorization_url(_redirect_uri(), state)
    return RedirectResponse(url, status_code=302)
```
to:
```python
    state_repo.delete_states_before(now - _STATE_RETENTION)
    state_repo.create_state(state=state, created_at=now, expires_at=now + _STATE_TTL)
    session.commit()
    url = google_client.build_authorization_url(_redirect_uri(), state)
    return RedirectResponse(url, status_code=302)
```

Run: `accounts/.venv/bin/pytest accounts/tests/test_google_login.py -v`
Expected: all tests still pass.

- [ ] **Step 13: Run the full `accounts/` suite**

Run: `accounts/.venv/bin/pytest accounts/tests/`
Expected: all tests pass, same count as before this task started.

- [ ] **Step 14: Commit**

```bash
git add accounts/src/normly_accounts/routers/email_verification.py accounts/src/normly_accounts/routers/password.py accounts/src/normly_accounts/routers/email_change.py accounts/src/normly_accounts/routers/login.py accounts/src/normly_accounts/routers/notifications.py accounts/src/normly_accounts/routers/profile.py accounts/src/normly_accounts/routers/watchlist.py accounts/src/normly_accounts/routers/magic_link.py accounts/src/normly_accounts/routers/sessions.py accounts/src/normly_accounts/routers/password_reset.py accounts/src/normly_accounts/routers/google.py
git commit -s -m "fix(accounts): commit writes before returning across 17 endpoints

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Test hardening — new fixture + two genuine second-connection durability tests

**Files:**
- Modify: `accounts/tests/conftest.py`
- Modify: `accounts/tests/test_account_management.py`
- Modify: `accounts/tests/test_set_password.py`

**Interfaces:**
- Consumes: Task 1's fix to `password.py` (the new test exercises that code path, though — per this plan's own correction below — it cannot actually distinguish fixed-vs-unfixed behavior; it runs after Task 1 purely for a coherent commit history).
- Produces: a new pytest fixture other future tests in this file could reuse (name it clearly, document why it exists).

**Context — read this before writing anything:** `accounts/tests/conftest.py`'s existing `client` fixture overrides `get_session` with `lambda: db_session` — the exact same `Session` object the test itself holds. The real `get_session()` function (with its own `session.commit()` at teardown) never runs at all under this override. `accounts/tests/test_account_management.py`'s existing `test_deleting_an_account_commits_before_the_response_is_returned` reads back through that same shared session, so it passes regardless of whether anything was ever really committed — it is not a real regression test.

**Important correction (already applied to the spec, carry it into this task's test comments verbatim in spirit):** a `TestClient` call runs the ENTIRE request lifecycle — including `get_session()`'s own deferred commit at dependency teardown — synchronously, before control returns to the test. There is no window within a single `TestClient` call where a second connection could observe "response sent, commit not yet run." The original production race needed a live server and two real, concurrent HTTP connections. **The tests in this task do NOT reproduce that race.** What they DO prove: the write is genuinely durable in the real database, visible from a truly independent second connection — not merely visible because the test happens to share the exact same in-memory `Session` object as the code under test. That is still a real, meaningful improvement over the current test (which would pass even if `commit()` were never called anywhere), and it protects against a real future regression class (e.g. someone breaking `get_session()`'s own commit, or routing an endpoint through a session that never commits).

`accounts/tests/conftest.py` already has a session-scoped `migrated_engine` fixture (a real `sqlalchemy.Engine`, independent of `db_session`'s savepoint-wrapped connection) built against a real Postgres testcontainer — `migrated_engine.connect()` opens a genuinely separate connection. `accounts/src/normly_accounts/main.py`'s `create_app()` reads `NORMLY_DATABASE_URL` from the environment (already set by the existing `client` fixture's `monkeypatch.setenv` call) and builds its own real engine, stored on `app.state.engine` — this is what the real `get_session()` uses.

- [ ] **Step 1: Add the new fixture to `accounts/tests/conftest.py`**

Add this fixture after the existing `client` fixture:

```python
@pytest.fixture()
def real_client(db_url, monkeypatch, email_sender):
    # Unlike `client`, this does NOT override get_session -- the app builds
    # its own real Session against its own real engine, so get_session()'s
    # own session.commit() at dependency teardown genuinely runs. Use this
    # fixture only for tests that specifically need to prove a write is
    # durable via an independent connection (see test_account_management.py
    # and test_set_password.py for examples) -- everything else should keep
    # using the faster, transactionally-isolated `client` fixture.
    monkeypatch.setenv("NORMLY_DATABASE_URL", db_url)
    from normly_accounts.dependencies import get_email_sender
    from normly_accounts.main import create_app

    app = create_app()
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 2: Rewrite the delete-account test in `accounts/tests/test_account_management.py`**

Find `test_deleting_an_account_commits_before_the_response_is_returned` and replace it with:

```python
def test_deleting_an_account_commits_before_the_response_is_returned(real_client, migrated_engine):
    """
    Proves the deleted row is gone via a genuinely independent second
    connection (migrated_engine.connect(), not db_session) -- NOT that the
    commit happens before the response is sent. A TestClient call runs the
    whole request lifecycle, including get_session()'s own deferred commit,
    synchronously before this test function resumes -- there is no window
    for a second connection to race the response. What this DOES prove:
    the row is really durable in Postgres, not merely visible because the
    test and the app happened to share one uncommitted Session (the bug in
    the old version of this test).
    """
    headers = _register(real_client, email="commit-check-2@example.de", password="correct horse")
    account_id = real_client.get("/v1/accounts/session", headers=headers).json()["account_id"]

    response = real_client.request(
        "DELETE", "/v1/accounts/me", json={"password": "correct horse"}, headers=headers,
    )
    assert response.status_code == 200

    with migrated_engine.connect() as connection:
        account = PostgresAccountRepository(Session(bind=connection)).get_account_by_id(
            uuid.UUID(account_id)
        )
    assert account is None
```

Check the top of `accounts/tests/test_account_management.py` for its existing imports — `uuid`, `PostgresAccountRepository`, and `_register` should already be imported/defined there (the file already has a local `_register` helper and imports `PostgresAccountRepository`, confirmed earlier this session); add `from sqlalchemy.orm import Session` to the file's imports if it isn't already there.

Run: `accounts/.venv/bin/pytest accounts/tests/test_account_management.py -v`
Expected: all tests pass, including the rewritten one.

- [ ] **Step 3: Add the new password-change durability test to `accounts/tests/test_set_password.py`**

This file's own existing convention (both `test_changing_an_existing_password_with_the_correct_current_one_succeeds` and `test_setting_a_password_for_a_passwordless_account_needs_no_current_password`, confirmed by reading the file this session) already proves a password change stuck by logging in again with the new password, through a SECOND, separate request — not by reading the row directly. Follow that exact convention, but with `real_client` instead of `client`: since `real_client` doesn't override `get_session`, each request gets its own freshly-constructed `Session` from the real engine (not the shared `db_session` the default `client` fixture reuses across every request in a test) — so a second request genuinely re-reads through independent session construction, not a shared in-memory object.

Add this test to the end of `accounts/tests/test_set_password.py`:

```python
def test_changing_a_password_via_real_client_is_durable_across_independent_requests(real_client):
    """
    Uses `real_client` (not `client`) so get_session()'s own commit-at-
    teardown genuinely runs against the real engine, and proves the change
    is durable by logging in again in a SEPARATE request -- each request
    through real_client gets its own freshly-constructed Session, not the
    one shared db_session the default `client` fixture reuses. This does
    NOT reproduce the original before-response-sent timing race (a
    TestClient call runs the whole request lifecycle, including the
    deferred commit, synchronously before this test function resumes) --
    it proves the new password hash is really durable and independently
    re-queryable, not merely visible within one shared, possibly-
    uncommitted session (the bug the old delete-account test had).
    """
    register = real_client.post(
        "/v1/accounts/register",
        json={"email": "real-client-password@example.de", "password": "old secret"},
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = real_client.post(
        "/v1/accounts/password",
        json={"current_password": "old secret", "new_password": "new secret"},
        headers=headers,
    )
    assert response.status_code == 200

    login_check = real_client.post(
        "/v1/accounts/login",
        json={"email": "real-client-password@example.de", "password": "new secret"},
    )
    assert login_check.status_code == 200
```

No new imports needed — this test only uses `real_client`, already provided by the fixture added in Step 1.

Run: `accounts/.venv/bin/pytest accounts/tests/test_set_password.py -v`
Expected: all tests pass, including the new one.

- [ ] **Step 4: Run the full `accounts/` suite**

Run: `accounts/.venv/bin/pytest accounts/tests/`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add accounts/tests/conftest.py accounts/tests/test_account_management.py accounts/tests/test_set_password.py
git commit -s -m "test(accounts): harden the commit-durability tests with a real second connection

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Two small, independent `core/` fixes

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Modify: `core/src/normly_core/graph/domain.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py`
- Test: (find the existing test file(s) for `find_previous_edition` and for `PostgresRightsNotificationBaselineRepository` — see steps below)

**Interfaces:**
- Consumes: nothing from Tasks 1-2 — entirely independent, `core/`-only.
- Produces: nothing another task depends on.

- [ ] **Step 1: Document the `edition`-sortability assumption on `find_previous_edition`**

In `core/src/normly_core/graph/postgres/repositories.py`, the method currently reads (starting at line 635):

```python
    def find_previous_edition(
        self, issuer: str, designation: str, before_edition: str
    ) -> Document | None:
        # Unlike find_by_designation's edition-less fallback (which answers
        # "most recently INSERTED"), this answers "the greatest edition
        # value strictly less than before_edition" -- the actual predecessor
        # in edition order, regardless of ingestion order. Out-of-order
        # ingestion (e.g. a 2013 archive arriving after its 2022 successor
        # is already known) or same-transaction batches (where created_at
        # ties are common) must not produce an inverted or nondeterministic
        # REPLACES edge -- see the final-review finding this method fixes.
```

Add a second comment block directly after that existing one (keep the existing comment word-for-word, add this below it, still before the `orm = self._session.execute(...)` line):

```python
        # ASSUMPTION this method relies on: `edition` strings are
        # lexicographically sortable in an order that matches their real
        # chronological order (a plain `<` comparison, below). This is true
        # today only because the sole producer of this field, the DGUV
        # adapter's _normalise_issue_date() (core/src/normly_core/pipeline/
        # adapters/dguv.py), always emits ISO-8601 `YYYY-MM-DD` strings,
        # where lexicographic and chronological order coincide. Neither
        # eur_lex.py nor baua.py ever sets `edition`. A future adapter that
        # sets `edition` in a different, non-ISO-8601-sortable format would
        # silently break this method's correctness -- no error would be
        # raised, `find_previous_edition` would simply return the wrong
        # document as "the predecessor." See also the matching note on
        # DocumentDesignation.edition in domain.py.
```

Run: `grep -rln "find_previous_edition" core/tests/` to find the test file(s) covering this method, then run: `core/.venv/bin/pytest <that file> -v` (or `accounts/.venv/bin/pytest <that file> -v` if `core/.venv` doesn't exist in your worktree — use whichever venv has `normly-core` installed editable).
Expected: all tests still pass (this step is comment-only, no behavior change).

- [ ] **Step 2: Add the matching note to `DocumentDesignation.edition` in `domain.py`**

In `core/src/normly_core/graph/domain.py`, the `DocumentDesignation` dataclass currently reads (starting around line 98):

```python
class DocumentDesignation:
    id: uuid.UUID
    document_id: uuid.UUID
    issuer: str
    designation: str
    language: str
    edition: str | None
    is_primary: bool
    delivery_id: uuid.UUID
```

Change the `edition: str | None` line to add a comment directly above it:

```python
class DocumentDesignation:
    id: uuid.UUID
    document_id: uuid.UUID
    issuer: str
    designation: str
    language: str
    # If an adapter sets this, it MUST be a lexicographically-sortable
    # string whose sort order matches real chronological order (e.g.
    # ISO-8601 "YYYY-MM-DD", the only format any adapter emits today --
    # see the DGUV adapter's _normalise_issue_date()). This field is
    # compared with a plain `<` in
    # PostgresDocumentRepository.find_previous_edition (repositories.py) --
    # a non-sortable format there would silently produce a wrong result,
    # not an error.
    edition: str | None
    is_primary: bool
    delivery_id: uuid.UUID
```

Run: `accounts/.venv/bin/pytest` (or `core/.venv/bin/pytest`) against whichever test file(s) import `DocumentDesignation` directly if any exist, otherwise skip straight to Step 5's full-suite run — this is comment-only, no behavior change is possible to break.

- [ ] **Step 3: Add `onupdate` to `RightsNotificationBaselineORM.updated_at`**

In `core/src/normly_core/graph/postgres/orm.py`, change:

```python
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

to:

```python
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
```

(This is the only ORM class this task touches — `RightsNotificationBaselineORM`, currently starting at line 604 of `orm.py`.)

- [ ] **Step 4: Write the failing test for the `onupdate` fix**

The exact file is `core/tests/graph/test_rights_notification_baseline_repository.py` — it already has local helpers `_make_account(db_session, email)`, `_make_work(db_session)`, `_make_delivery(db_session, content_hash=...)`, and `_make_document(db_session, delivery.id)` (all confirmed by reading the file this session), used by its 3 existing tests (`test_get_baseline_returns_none_when_absent`, `test_upsert_baseline_creates_on_first_call`, `test_upsert_baseline_updates_in_place_on_a_second_call`). Use those exact same helpers — do not invent new ones.

It needs an explicit backdate of `updated_at` after the first upsert, because Postgres's `now()` is transaction-scoped (identical for every statement in one test transaction) — the established pattern for this in this codebase (see `core/tests/notifications/test_detection.py`'s `_set_created_at` helper) is a direct `UPDATE ... SET <column> = <explicit datetime>` + `flush()`, never `time.sleep()`. `RightsNotificationBaselineORM` has a composite primary key (`account_id`, `work_id`, `trigger_document_id`, `trigger_jurisdiction`), not a single `id` column, so the `WHERE` clause needs all four.

Add these two imports to the file's existing import block (it currently imports `date, datetime, timezone` from `datetime`, and `LegalBasisCategory, WorkCreatedVia` from `normly_core.graph.domain`, plus 6 `Postgres*Repository` classes from `normly_core.graph.postgres.repositories` — add to those, don't replace them):

```python
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.postgres.orm import RightsNotificationBaselineORM
```

Then add this test at the end of the file:

```python
def test_upsert_baseline_updates_updated_at_on_a_second_upsert(db_session):
    account = _make_account(db_session, "baseline-updated-at@example.de")
    work = _make_work(db_session)
    delivery = _make_delivery(db_session, content_hash="sha256:baseline-updated-at-fixture")
    document = _make_document(db_session, delivery.id)
    repo = PostgresRightsNotificationBaselineRepository(db_session)

    repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )

    # Postgres's now() is transaction-scoped -- force the first row's
    # updated_at to an explicit, unambiguous OLDER value so a second upsert
    # in this same test transaction produces a genuinely different value,
    # not a coincidentally-identical one. Same idiom as
    # test_detection.py's _set_created_at, adapted for this table's
    # composite primary key.
    old = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.execute(
        sa.update(RightsNotificationBaselineORM)
        .where(
            RightsNotificationBaselineORM.account_id == account.id,
            RightsNotificationBaselineORM.work_id == work.id,
            RightsNotificationBaselineORM.trigger_document_id == document.id,
            RightsNotificationBaselineORM.trigger_jurisdiction == "DE",
        )
        .values(updated_at=old)
    )
    db_session.flush()

    second = repo.upsert_baseline(
        account_id=account.id, work_id=work.id, trigger_document_id=document.id,
        trigger_jurisdiction="DE", may_process=False, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=False,
    )

    assert second.updated_at > old
```

Run: `accounts/.venv/bin/pytest <that test file> -v -k updated_at`
Expected: FAILS before Step 3's fix is applied (if you're doing this in strict TDD order — write this test against the pre-fix ORM first to confirm it fails, then apply Step 3, then re-run to confirm it passes). If you already applied Step 3 first, that's fine too — just confirm the test passes now and, if you want the TDD proof, temporarily revert Step 3's one-line change, confirm this test fails, then reapply it.

- [ ] **Step 5: Run the full `core/` and `accounts/` suites**

Run: `accounts/.venv/bin/pytest core/tests/` (or `core/.venv/bin/pytest core/tests/` if that venv exists in your worktree) and `accounts/.venv/bin/pytest accounts/tests/`.
Expected: both fully green, no regressions.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py <the test file you edited>
git commit -s -m "fix(core): document the edition-sortability assumption, fix baseline updated_at

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
