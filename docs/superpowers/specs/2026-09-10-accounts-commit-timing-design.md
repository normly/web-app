# accounts/ Commit-Timing Sweep, Test Hardening, and Two Small Data Fixes — Design

## Context

A 10-day-old memory entry from the "profile management" sub-project
listed several deferred follow-ups. A direct re-check against the
current code (main @ 85a464fe) showed: one of the items is already solved
(the magic link email has had a real URL and a
working frontend consumer since 2026-09-08, verified), one is bigger than
thought (the "response before commit" problem affects not just two but
17 endpoints), and one needs a real technical decision (how a
regression test for commit timing can work at all, given the
existing test fixture architecture). This spec bundles the four items
that could be classified as "mechanical/low-risk" — bigger items
that need design (avatar redesign, notification cleanup policy,
search threshold/index) are deliberately NOT handled here, but
get brainstorming rounds of their own later.

## The core problem (items 1 and 2 of this spec)

`accounts/src/normly_accounts/dependencies.py`'s `get_session()`:
```python
def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()
```
The `session.commit()` only runs when FastAPI resumes the yield dependency generator
while tearing down the `AsyncExitStack` — this happens **after** the
HTTP response has already been sent to the client. An endpoint without
its own explicit `session.commit()` before its `return` therefore returns a
success response before the write is durable.
A client that immediately afterwards queries something that depends on this write
can get a stale answer under READ COMMITTED — exactly
this race has already been measured for real and fixed twice (session creation
on login/register/magic link/Google OAuth via `_create_session_response()`
in `login.py`, and account deletion in `account_management.py`'s
`delete_account`).

**The re-check showed: 17 further endpoints are exposed to exactly the same class
of hazard**, not just the two already fixed:

| File | Endpoint(s) | Line(s) |
|---|---|---|
| `email_verification.py` | `POST /verify-email/resend` | 49 |
| `email_verification.py` | `GET /verify-email` (writes via GET) | 35 |
| `password.py` | `POST /password` | 19 |
| `email_change.py` | `POST /email/change` | 37 |
| `email_change.py` | `GET /email/confirm` (writes via GET) | 81 |
| `login.py` | `POST /logout` | 91 |
| `notifications.py` | `PATCH /notifications/{id}` | 50 |
| `profile.py` | `PATCH /profile` | 37 |
| `profile.py` | `POST /avatar` | 59 |
| `profile.py` | `DELETE /avatar` | 104 |
| `watchlist.py` | `POST /watchlist` | 22 |
| `watchlist.py` | `DELETE /watchlist/{work_id}` | 42 |
| `magic_link.py` | `POST /magic-link/request` | 38 |
| `sessions.py` | `DELETE /sessions/{session_id}` | 43 |
| `password_reset.py` | `POST /password-reset/request` | 36 |
| `password_reset.py` | `POST /password-reset/confirm` | 72 |
| `google.py` | `GET /google/login` (writes the new `oauth_state`) | 40 |

Fix: an explicit `session.commit()` before every `return`, exactly the
existing pattern from `_create_session_response()`/`delete_account`. No
behavior change other than the point in time at which the write becomes durable.

## Test hardening (item 3 of this spec)

`accounts/tests/test_account_management.py`'s existing
`test_deleting_an_account_commits_before_the_response_is_returned` cannot
structurally prove what it claims: `accounts/tests/conftest.py`'s
`client` fixture overrides `get_session` with `lambda: db_session` —
so the test and the app share the same `Session` object. The real
`get_session()` code path (incl. `session.commit()`) does not run at all;
the test's read-back check sees the deletion regardless of whether it was
committed, because both look through the same open transaction.

**Confirmed, existing way out**: `accounts/tests/conftest.py` already has
a session-wide, raw `migrated_engine` fixture (a real
`sqlalchemy.Engine`, independent of the savepoint-wrapped `db_session`),
built against a real Postgres test container. `core/tests/pipeline/test_cli.py`'s
`committed_db` fixture already shows the right pattern in the repo: let the real
code commit, then read back via a **second, independent** connection.

**Important correction compared with the original version of this spec**: A
`TestClient` call runs the complete request cycle — including
`get_session()`'s own, delayed `session.commit()` during
dependency teardown — **synchronously, before the test function continues**.
Within a single `TestClient` call there is no time window in
which a second connection could interfere between "response sent" and "commit
executed" — the real production race needed
a real running server with two parallel HTTP connections. A
"second connection, no override" test therefore **cannot** prove this race property,
and would pass identically whether item 1's fix
was applied or not.

**What the test proves instead, honestly reinterpreted (owner decision)**:
not "commit happens before the response", but "the write really lands
durably in the real database, visible via a truly
independent second connection" — a weaker, but still real and
valuable guarantee. It is strictly better than the current broken test (which
would pass even if `commit()` were never called anywhere, because the test and the
app share the same session) and really protects against, e.g., a future
change that breaks `get_session()`'s own teardown commit or
accidentally lets an endpoint run over a session that never commits.

Fix design:
- A new fixture in `accounts/tests/conftest.py` that builds a `TestClient`
  that does **not** override `get_session` — the app then constructs
  its own real engine (`accounts/src/normly_accounts/main.py:34-36`
  reads `NORMLY_DATABASE_URL` and sets `app.state.engine`, exactly the URL already
  set by the `client` fixture via `monkeypatch.setenv`), so that the
  real `get_session()` code path including `session.commit()` actually
  runs.
- Two tests get this pattern (owner decision: not only the
  delete test, but also the password change, since "signing in again immediately" was explicitly named as a
  plausible race): after the respective request, the state is read back via
  `migrated_engine.connect()` (a second, independent connection).
  Both tests clean up after themselves — account deletion removes everything
  by cascade, and the password change leaves only the expected
  changed state of the account created for the test anyway, no leak
  into other tests.
- The remaining 16 of the 17 endpoint fixes get NO new
  "second connection" test of their own — they are covered by their existing functional
  test suite (unchanged behavior, only a different commit time) and by
  code review, not by 16 further elaborate durability tests.

## Two small, independent data fixes (items 4 and 5 of this spec)

**`find_previous_edition`'s edition string comparison** (`core/src/normly_core/graph/postgres/repositories.py:635-661`):
currently a plain `edition < before_edition` string comparison that only
works because the only producer of this field (the DGUV adapter)
always supplies ISO 8601 dates. No safeguard against a future format.
**Decision: document only**, no runtime guard — with currently exactly
one producer, validation for a hypothetical future
adapter format would be premature YAGNI. Fix: a clear docstring addition to
`find_previous_edition` AND to the `edition` field of the `DocumentDesignation`
domain class (`core/src/normly_core/graph/domain.py`) that makes the assumption
explicit — every future adapter that sets `edition` is bound to come across
it there.

**`rights_notification_baseline.updated_at` without `onupdate`**
(`core/src/normly_core/graph/postgres/orm.py:629-631`): the column gets
a value only on INSERT, never on subsequent upserts (the model is
updated via merge-on-conflict, see the class docstring). Fix: an
`onupdate=sa.func.now()` addition to the existing `mapped_column` definition,
no migration needed (no schema change, only different
application behavior on UPDATE).

## Testing

- All 17 commit-timing fixes: the existing functional tests of every
  affected endpoint pass unchanged (behavior does not change
  visibly).
- Two new "real second connection" tests (account deletion — replacing the
  existing, ineffective test; password change — new) prove real
  durability via an independent connection (not the original
  timing race property, which only a live server setup could show —
  see the correction above).
- The edition docstring fix: no new test obligation (pure documentation),
  but the existing test suite for `find_previous_edition` must stay
  green.
- The `updated_at` fix: a new, small test that performs two upserts in a row
  and confirms that `updated_at` really changes on the second one
  (not just `created_at`).

## Global guardrails

- DCO `Signed-off-by` (`git commit -s`), Conventional Commits, a separate
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
- No behavior change other than the commit time for the 17
  endpoint fixes — no new features, no API contract changes.
- `accounts/` for the commit-timing fixes and the test hardening; `core/` for
  the two small data fixes — independent areas, one shared plan,
  since all four items are equally low-risk/mechanical.
- No push/PR/merge without asking explicitly first (STACKIT CI runs are
  billed, no working cancel). A direct push to `main`
  is ruled out — also not as a local merge that is pushed
  afterwards (see the corresponding lesson from the previous
  sub-project of this session).
