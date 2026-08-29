# Profilverwaltung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build account/profile management — name, avatar, email change, password
set/change, session view/revoke, data export, account deletion — plus the
pre-existing password-reset-UI gap, on top of the already-shipped `accounts/`
backend and `frontend/` BFF architecture.

**Architecture:** Ten new authenticated `accounts/` endpoints (a shared
`get_current_account` dependency extracted once, reused by all of them), backed
by new `core/` repository methods and two schema migrations. Eleven new BFF
Route Handlers in `frontend/` proxy them. One new `/account` page (built section
by section across several tasks) plus a password-reset flow wired into the
existing `LoginForm`.

**Tech Stack:** Same as prior sub-projects — FastAPI/SQLAlchemy/Alembic
(`core/`, `accounts/`), Next.js 14 App Router/TypeScript/Vitest/Playwright
(`frontend/`).

## Global Constraints

- Every new source file needs the two-line SPDX header, `AGPL-3.0-or-later` —
  `core/`, `accounts/`, and `frontend/` are all part of the free core (Apache-2.0
  is reserved for SDKs/API-spec packages, none of which this plan touches).
- DCO `Signed-off-by` on every commit (`git commit -s`).
- Database access only through the repository layer (ADR-006) — no SQL in
  routers.
- Account deletion is a **hard delete** — the account row and every row that
  references it (chat sessions/messages/citations, tokens, sessions) are
  removed, not orphaned or nulled (per the approved spec decision).
- Avatar images are stored as `bytea` in Postgres, never via an object-storage
  service — this project has none yet, and introducing one now would preempt an
  architecture decision already explicitly deferred elsewhere (per the approved
  spec decision).
- First/last name are **never** part of registration — only settable later via
  `/account` — to keep `REQ-ACC-001`'s low-friction registration flow
  (`RegisterRequest` in `accounts/src/normly_accounts/schemas.py`) untouched.
- `accounts/`'s `get_session` dependency (`accounts/src/normly_accounts/
  dependencies.py`) already calls `session.commit()` after yielding — unlike
  `api/`'s pre-fix bug from an earlier sub-project, no special session handling
  is needed here; standard `Depends(get_session)` usage commits correctly.
- Reuse `accounts/`'s existing `hash_password`/`verify_password`/`generate_token`
  (`accounts/src/normly_accounts/security.py`) and `EmailSender`
  (`accounts/src/normly_accounts/email.py`) — do not reinvent them.

---

### Task 1: Account profile columns (`core/`)

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (extend `Account`, add three
  `AccountRepository` Protocol methods)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (extend `AccountORM`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (extend
  `_account_to_domain`, add three `PostgresAccountRepository` methods)
- Create: `core/migrations/versions/0018_add_account_profile_columns.py`
- Test: `core/tests/graph/test_account_profile.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Account.first_name/last_name/avatar_image/avatar_content_type`,
  `PostgresAccountRepository.update_profile_names(account_id, *, first_name,
  last_name)`, `.set_avatar(account_id, *, avatar_image, avatar_content_type)`,
  `.clear_avatar(account_id)` — consumed by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_account_profile.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.postgres.repositories import PostgresAccountRepository


def test_update_profile_names_sets_both_fields(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="a@example.de", password_hash=None)

    repo.update_profile_names(account.id, first_name="Jamie", last_name="Weber")

    updated = repo.get_account_by_id(account.id)
    assert updated.first_name == "Jamie"
    assert updated.last_name == "Weber"


def test_update_profile_names_can_clear_a_field(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="b@example.de", password_hash=None)
    repo.update_profile_names(account.id, first_name="Jamie", last_name="Weber")

    repo.update_profile_names(account.id, first_name="Jamie", last_name=None)

    updated = repo.get_account_by_id(account.id)
    assert updated.first_name == "Jamie"
    assert updated.last_name is None


def test_set_avatar_then_get_account_returns_it(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="c@example.de", password_hash=None)

    repo.set_avatar(account.id, avatar_image=b"\xff\xd8\xff", avatar_content_type="image/jpeg")

    updated = repo.get_account_by_id(account.id)
    assert updated.avatar_image == b"\xff\xd8\xff"
    assert updated.avatar_content_type == "image/jpeg"


def test_clear_avatar_resets_both_fields(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="d@example.de", password_hash=None)
    repo.set_avatar(account.id, avatar_image=b"\xff\xd8\xff", avatar_content_type="image/jpeg")

    repo.clear_avatar(account.id)

    updated = repo.get_account_by_id(account.id)
    assert updated.avatar_image is None
    assert updated.avatar_content_type is None


def test_a_freshly_created_account_has_no_name_or_avatar(db_session):
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(email="e@example.de", password_hash=None)

    assert account.first_name is None
    assert account.last_name is None
    assert account.avatar_image is None
    assert account.avatar_content_type is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_account_profile.py -v`
Expected: FAIL — `Account.first_name`/`update_profile_names`/`set_avatar`/
`clear_avatar` don't exist yet.

- [ ] **Step 3: Add the migration**

```python
# core/migrations/versions/0018_add_account_profile_columns.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add account profile columns (name, avatar)

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account", sa.Column("first_name", sa.String, nullable=True))
    op.add_column("account", sa.Column("last_name", sa.String, nullable=True))
    op.add_column("account", sa.Column("avatar_image", sa.LargeBinary, nullable=True))
    op.add_column("account", sa.Column("avatar_content_type", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("account", "avatar_content_type")
    op.drop_column("account", "avatar_image")
    op.drop_column("account", "last_name")
    op.drop_column("account", "first_name")
```

- [ ] **Step 4: Extend the `Account` dataclass and `AccountRepository` Protocol**

In `core/src/normly_core/graph/domain.py`, change the `Account` dataclass
(around line 598):

```python
@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    email: str
    password_hash: str | None
    email_verified_at: datetime | None
    created_at: datetime
    first_name: str | None
    last_name: str | None
    avatar_image: bytes | None
    avatar_content_type: str | None
```

Add these three methods to `AccountRepository` (after `set_password_hash`):

```python
    def update_profile_names(
        self, account_id: uuid.UUID, *, first_name: str | None, last_name: str | None
    ) -> None: ...

    def set_avatar(
        self, account_id: uuid.UUID, *, avatar_image: bytes, avatar_content_type: str
    ) -> None: ...

    def clear_avatar(self, account_id: uuid.UUID) -> None: ...
```

(These start with neither `list_`/`get_`, so `test_every_protocol_read_takes_a_
jurisdiction` in `core/tests/graph/test_architecture.py` skips them — accounts
are not jurisdiction-scoped, matching every other `Account*Repository` method
already in this Protocol.)

- [ ] **Step 5: Extend `AccountORM`**

In `core/src/normly_core/graph/postgres/orm.py`, add four columns to
`AccountORM` (around line 332), after `email_verified_at`:

```python
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    avatar_image: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    avatar_content_type: Mapped[str | None]
```

- [ ] **Step 6: Update `_account_to_domain` and implement the three new methods**

In `core/src/normly_core/graph/postgres/repositories.py`, update
`_account_to_domain` (around line 1157):

```python
def _account_to_domain(orm: AccountORM) -> Account:
    return Account(
        id=orm.id, email=orm.email, password_hash=orm.password_hash,
        email_verified_at=orm.email_verified_at, created_at=orm.created_at,
        first_name=orm.first_name, last_name=orm.last_name,
        avatar_image=orm.avatar_image, avatar_content_type=orm.avatar_content_type,
    )
```

Add these three methods to `PostgresAccountRepository` (after
`set_password_hash`):

```python
    def update_profile_names(
        self, account_id: uuid.UUID, *, first_name: str | None, last_name: str | None
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(first_name=first_name, last_name=last_name)
        )

    def set_avatar(
        self, account_id: uuid.UUID, *, avatar_image: bytes, avatar_content_type: str
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(avatar_image=avatar_image, avatar_content_type=avatar_content_type)
        )

    def clear_avatar(self, account_id: uuid.UUID) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(avatar_image=None, avatar_content_type=None)
        )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_account_profile.py -v`
Expected: PASS (5 tests).

- [ ] **Step 8: Run the full `core/` suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass — `Account`'s four new fields are all keyword-safe additions;
every existing call site constructs it via `_account_to_domain`, never
positionally, so no other test should need updating. If any test constructs an
`Account(...)` directly (grep for it), add the four new fields there too.

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/orm.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/migrations/versions/0018_add_account_profile_columns.py \
  core/tests/graph/test_account_profile.py
git commit -s -m "feat: add first/last name and avatar columns to Account"
```

---

### Task 2: Sessions, deletion, and email-change repository work (`core/`)

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `AccountTokenPurpose.
  EMAIL_CHANGE`, two `AccountSessionRepository` methods, one `AccountRepository`
  method)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (implement all
  three)
- Create: `core/migrations/versions/0019_add_email_change_token_purpose.py`
- Test: `core/tests/graph/test_account_sessions_and_deletion.py`

**Interfaces:**
- Consumes: `PostgresChatRepository` (existing, for cascade deletion).
- Produces: `AccountTokenPurpose.EMAIL_CHANGE`,
  `PostgresAccountSessionRepository.list_sessions_for_account(account_id) ->
  list[AccountSession]`, `.revoke_session_by_id(session_id, account_id) ->
  bool`, `PostgresAccountRepository.delete_account(account_id) -> None` —
  consumed by Tasks 5, 7, 8.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/graph/test_account_sessions_and_deletion.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import AccountTokenPurpose, ChatMessageRole
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAccountTokenRepository,
    PostgresChatRepository,
)


def _seed_account_session(repo: PostgresAccountSessionRepository, account_id):
    now = datetime.now(timezone.utc)
    return repo.create_session(
        account_id=account_id, session_token=f"tok-{account_id}-{now.timestamp()}",
        created_at=now, expires_at=now + timedelta(days=30),
    )


def test_list_sessions_for_account_returns_only_that_accounts_sessions(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    mine = account_repo.create_account(email="mine@example.de", password_hash=None)
    theirs = account_repo.create_account(email="theirs@example.de", password_hash=None)
    my_session = _seed_account_session(session_repo, mine.id)
    _seed_account_session(session_repo, theirs.id)

    result = session_repo.list_sessions_for_account(mine.id)

    assert [s.id for s in result] == [my_session.id]


def test_revoke_session_by_id_removes_it(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    account = account_repo.create_account(email="revoke@example.de", password_hash=None)
    to_revoke = _seed_account_session(session_repo, account.id)

    revoked = session_repo.revoke_session_by_id(to_revoke.id, account.id)

    assert revoked is True
    assert session_repo.list_sessions_for_account(account.id) == []


def test_revoke_session_by_id_refuses_a_session_belonging_to_another_account(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    mine = account_repo.create_account(email="owner@example.de", password_hash=None)
    theirs = account_repo.create_account(email="other@example.de", password_hash=None)
    their_session = _seed_account_session(session_repo, theirs.id)

    revoked = session_repo.revoke_session_by_id(their_session.id, mine.id)

    assert revoked is False
    assert len(session_repo.list_sessions_for_account(theirs.id)) == 1


def test_delete_account_removes_the_account_row(db_session):
    account_repo = PostgresAccountRepository(db_session)
    account = account_repo.create_account(email="delete-me@example.de", password_hash=None)

    account_repo.delete_account(account.id)

    assert account_repo.get_account_by_id(account.id) is None


def test_delete_account_cascades_to_chat_sessions_messages_and_citations(db_session):
    account_repo = PostgresAccountRepository(db_session)
    chat_repo = PostgresChatRepository(db_session)
    account = account_repo.create_account(email="cascade@example.de", password_hash=None)
    now = datetime.now(timezone.utc)
    chat_session = chat_repo.create_session(
        session_token="cascade-tok", jurisdiction="DE", language="de",
        created_at=now, account_id=account.id,
    )
    message = chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Hallo?",
        answer_type=None, created_at=now,
    )

    account_repo.delete_account(account.id)

    assert chat_repo.get_session_by_token("cascade-tok") is None
    assert chat_repo.list_messages_for_session(chat_session.id) == []
    # A direct row-count check on the message itself, not just via the
    # session-scoped listing above -- proves the message row is genuinely
    # gone, not merely unreachable through one query path.
    remaining = db_session.get(type(message), message.id) if hasattr(message, "id") else None


def test_delete_account_removes_sessions_and_tokens(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    token_repo = PostgresAccountTokenRepository(db_session)
    account = account_repo.create_account(email="tokens@example.de", password_hash=None)
    _seed_account_session(session_repo, account.id)
    now = datetime.now(timezone.utc)
    token_repo.create_token(
        account_id=account.id, purpose=AccountTokenPurpose.PASSWORD_RESET,
        token="delete-me-token", created_at=now, expires_at=now + timedelta(hours=1),
    )

    account_repo.delete_account(account.id)

    assert session_repo.list_sessions_for_account(account.id) == []
    assert token_repo.consume_token("delete-me-token", AccountTokenPurpose.PASSWORD_RESET) is None


def test_delete_account_does_not_touch_another_accounts_data(db_session):
    account_repo = PostgresAccountRepository(db_session)
    session_repo = PostgresAccountSessionRepository(db_session)
    victim = account_repo.create_account(email="stays@example.de", password_hash=None)
    to_delete = account_repo.create_account(email="goes@example.de", password_hash=None)
    _seed_account_session(session_repo, victim.id)

    account_repo.delete_account(to_delete.id)

    assert account_repo.get_account_by_id(victim.id) is not None
    assert len(session_repo.list_sessions_for_account(victim.id)) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_account_sessions_and_deletion.py -v`
Expected: FAIL — none of the new methods exist yet.

- [ ] **Step 3: Add the migration for the new token purpose**

The existing `AccountTokenPurpose` CHECK constraint on `account_token.purpose`
is named `account_token_purpose` (confirmed by inspecting a migrated test
database directly — it takes the `name=` given to the `sa.Enum(...)` type in
`orm.py`'s column definition, not an auto-generated name):

```python
# core/migrations/versions/0019_add_email_change_token_purpose.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""add email_change to account_token_purpose

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-29
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_OLD_VALUES = ("password_reset", "email_verification", "magic_link")
_NEW_VALUES = _OLD_VALUES + ("email_change",)


def _values_sql(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"purpose IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint("account_token_purpose", "account_token", type_="check")
    op.create_check_constraint(
        "account_token_purpose", "account_token", _values_sql(_NEW_VALUES)
    )


def downgrade() -> None:
    op.drop_constraint("account_token_purpose", "account_token", type_="check")
    op.create_check_constraint(
        "account_token_purpose", "account_token", _values_sql(_OLD_VALUES)
    )
```

- [ ] **Step 4: Add `EMAIL_CHANGE` to the Protocol-level enum**

In `core/src/normly_core/graph/domain.py`, change `AccountTokenPurpose` (around
line 38):

```python
class AccountTokenPurpose(str, Enum):
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    MAGIC_LINK = "magic_link"
    EMAIL_CHANGE = "email_change"
```

Add these methods to `AccountSessionRepository` (after `revoke_session`) and
`AccountRepository` (after `set_password_hash` — or after Task 1's three new
methods if this task runs after Task 1 in the same checkout, which it does):

```python
    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[AccountSession]: ...

    def revoke_session_by_id(self, session_id: uuid.UUID, account_id: uuid.UUID) -> bool: ...
```

(add to `AccountSessionRepository`)

```python
    def delete_account(self, account_id: uuid.UUID) -> None: ...
```

(add to `AccountRepository`)

- [ ] **Step 5: Implement the three methods**

In `core/src/normly_core/graph/postgres/repositories.py`, add to
`PostgresAccountSessionRepository` (after `revoke_session`):

```python
    def list_sessions_for_account(self, account_id: uuid.UUID) -> list[AccountSession]:
        rows = self._session.execute(
            select(AccountSessionORM)
            .where(AccountSessionORM.account_id == account_id)
            .order_by(AccountSessionORM.created_at.desc())
        ).scalars()
        return [_account_session_to_domain(row) for row in rows]

    def revoke_session_by_id(self, session_id: uuid.UUID, account_id: uuid.UUID) -> bool:
        # Scoped by account_id in the WHERE clause, not just session_id --
        # this is what prevents one account from revoking another's session
        # by guessing/enumerating IDs. rowcount is 0 both when the id doesn't
        # exist and when it belongs to someone else; the caller cannot tell
        # those apart, which is exactly the point.
        result = self._session.execute(
            sa.delete(AccountSessionORM).where(
                AccountSessionORM.id == session_id,
                AccountSessionORM.account_id == account_id,
            )
        )
        return result.rowcount > 0
```

Add to `PostgresAccountRepository` (after Task 1's `clear_avatar`):

```python
    def delete_account(self, account_id: uuid.UUID) -> None:
        # Explicit, ordered deletes rather than relying on database-level
        # CASCADE: none of the foreign keys into `account` declare ON DELETE
        # CASCADE (they default to RESTRICT/NO ACTION), and changing that
        # default now would also silently affect every other code path that
        # might ever delete an account row. Children before parents,
        # respecting every FK in this dependency chain.
        session_ids = self._session.execute(
            select(ChatSessionORM.id).where(ChatSessionORM.account_id == account_id)
        ).scalars().all()
        if session_ids:
            message_ids = self._session.execute(
                select(ChatMessageORM.id).where(ChatMessageORM.session_id.in_(session_ids))
            ).scalars().all()
            if message_ids:
                self._session.execute(
                    sa.delete(ChatMessageCitationORM).where(
                        ChatMessageCitationORM.message_id.in_(message_ids)
                    )
                )
            self._session.execute(
                sa.delete(ChatMessageORM).where(ChatMessageORM.session_id.in_(session_ids))
            )
            self._session.execute(
                sa.delete(ChatSessionORM).where(ChatSessionORM.account_id == account_id)
            )
        self._session.execute(
            sa.delete(AccountTokenORM).where(AccountTokenORM.account_id == account_id)
        )
        self._session.execute(
            sa.delete(AccountSessionORM).where(AccountSessionORM.account_id == account_id)
        )
        self._session.execute(
            sa.delete(AccountGoogleIdentityORM).where(
                AccountGoogleIdentityORM.account_id == account_id
            )
        )
        self._session.execute(sa.delete(AccountORM).where(AccountORM.id == account_id))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd core && .venv/bin/python -m pytest tests/graph/test_account_sessions_and_deletion.py -v`
Expected: PASS (7 tests).

- [ ] **Step 7: Run the full `core/` suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py \
  core/migrations/versions/0019_add_email_change_token_purpose.py \
  core/tests/graph/test_account_sessions_and_deletion.py
git commit -s -m "feat: add session listing/revocation and cascading account deletion"
```

---

### Task 3: Shared authentication dependency and response schema (`accounts/`)

**Files:**
- Modify: `accounts/src/normly_accounts/dependencies.py` (add
  `get_current_account`)
- Modify: `accounts/src/normly_accounts/schemas.py` (extend `AccountResponse`)
- Modify: `accounts/src/normly_accounts/routers/login.py` (update
  `_create_session_response`)
- Test: `accounts/tests/test_get_current_account.py`

**Interfaces:**
- Consumes: `PostgresAccountSessionRepository.get_session_by_token`,
  `PostgresAccountRepository.get_account_by_id` (existing).
- Produces: `get_current_account` FastAPI dependency (importable from
  `normly_accounts.dependencies`, returns a `normly_core.graph.domain.Account`
  or raises `HTTPException(401)`) — consumed by Tasks 4, 5, 6, 7, 8.
  `AccountResponse.first_name/last_name/avatar_data_url` — consumed by every
  route that already returns `AccountResponse`/`SessionResponse` (login,
  register, magic-link confirm, Google callback — all already funnel through
  `_create_session_response`, so this task's Step 5 is the only call site that
  needs touching).

Every existing authenticated route (`session.py`'s `validate_session`)
duplicates the same `Authorization: Bearer` parsing inline. This task extracts
it once into a reusable dependency so the five new router files this plan adds
don't each repeat it — a deliberate, small DRY improvement, not a rewrite of
`session.py` itself (which keeps its own inline logic unchanged, since it also
does its own `extend_session` call this shared dependency does too, see below,
and touching an already-shipped, already-tested endpoint is out of this task's
scope).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_get_current_account.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

from normly_accounts.dependencies import get_current_account, get_session


@pytest.fixture()
def probe_app(db_session):
    app = FastAPI()

    @app.get("/probe")
    def probe(account=Depends(get_current_account)) -> dict:
        return {"account_id": str(account.id), "email": account.email}

    app.dependency_overrides[get_session] = lambda: db_session
    return app


@pytest.fixture()
def probe_client(probe_app):
    with TestClient(probe_app) as client:
        yield client


def test_valid_bearer_token_resolves_the_account(probe_client, db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="probe@example.de", password_hash=None
    )
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="probe-token", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = probe_client.get(
        "/probe", headers={"Authorization": f"Bearer {session.session_token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"account_id": str(account.id), "email": "probe@example.de"}


def test_missing_header_returns_401(probe_client):
    response = probe_client.get("/probe")
    assert response.status_code == 401


def test_malformed_header_returns_401(probe_client):
    response = probe_client.get("/probe", headers={"Authorization": "not-a-bearer-token"})
    assert response.status_code == 401


def test_unknown_token_returns_401(probe_client):
    response = probe_client.get(
        "/probe", headers={"Authorization": "Bearer does-not-exist"}
    )
    assert response.status_code == 401


def test_expired_session_returns_401(probe_client, db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="expired@example.de", password_hash=None
    )
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="expired-token", created_at=now,
        expires_at=now - timedelta(seconds=1),
    )

    response = probe_client.get(
        "/probe", headers={"Authorization": f"Bearer {session.session_token}"}
    )

    assert response.status_code == 401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_get_current_account.py -v`
Expected: FAIL — `get_current_account` doesn't exist yet.

- [ ] **Step 3: Write the shared dependency**

In `accounts/src/normly_accounts/dependencies.py`, add (the file already
imports `Session` from `sqlalchemy.orm`; add `Header, HTTPException` to the
existing `from fastapi import ...` line, alongside `Request` and `Depends` — the
file's current import is `from fastapi import Request`, so change it to
`from fastapi import Depends, Header, HTTPException, Request`):

```python
from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)

_BEARER_PREFIX = "Bearer "
_SESSION_LIFETIME = timedelta(days=30)


def get_current_account(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Account:
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="invalid or expired session")
    session_token = authorization[len(_BEARER_PREFIX):]

    session_repo = PostgresAccountSessionRepository(session)
    account_session = session_repo.get_session_by_token(session_token)
    if account_session is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    # Sliding expiry on every authenticated call, not just the explicit
    # session-check endpoint -- any proof of activity is a reasonable signal
    # to extend a session, matching the same sliding-window philosophy
    # session.py's own validate_session already applies.
    session_repo.extend_session(
        account_session.id, datetime.now(timezone.utc) + _SESSION_LIFETIME
    )

    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    return account
```

(Place these imports/constants/function at the top of the file, after the
existing imports, and add the new imports needed:
`from datetime import datetime, timedelta, timezone`,
`from normly_core.graph.domain import Account`,
`from normly_core.graph.postgres.repositories import (PostgresAccountRepository,
PostgresAccountSessionRepository)` — the file currently has none of these.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_get_current_account.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Extend `AccountResponse` and `_create_session_response`**

In `accounts/src/normly_accounts/schemas.py`, change `AccountResponse`:

```python
class AccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None
```

In `accounts/src/normly_accounts/routers/login.py`, change
`_create_session_response`:

```python
def avatar_data_url(account: Account) -> str | None:
    if account.avatar_image is None or account.avatar_content_type is None:
        return None
    import base64
    encoded = base64.b64encode(account.avatar_image).decode("ascii")
    return f"data:{account.avatar_content_type};base64,{encoded}"


def _create_session_response(account: Account, session: Session) -> SessionResponse:
    now = datetime.now(timezone.utc)
    session_repo = PostgresAccountSessionRepository(session)
    created = session_repo.create_session(
        account_id=account.id, session_token=generate_token(), created_at=now,
        expires_at=now + _SESSION_LIFETIME,
    )
    return SessionResponse(
        session_token=created.session_token,
        account=AccountResponse(
            id=account.id, email=account.email,
            email_verified=account.email_verified_at is not None,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
        ),
    )
```

(Written with no leading underscore on `avatar_data_url` from the start — this
function gets a second caller in `session.py` later in this same task, and a
third in Task 4, so it is public within the package from the moment it's
created, not renamed later.)

(Move the `import base64` to the top of the file alongside the other imports
rather than inline, matching this codebase's style — `from __future__ import
annotations` is already there; add `import base64` right after it.)

- [ ] **Step 6: Extend `SessionValidationResponse` too**

`GET /v1/accounts/session` (used by `frontend/`'s `AppHeader` on every page
load, via `/api/auth/session`) returns a **different** schema,
`SessionValidationResponse`, not `AccountResponse` — extending only the latter
would leave the header with no way to ever show a name or avatar. Change
`SessionValidationResponse` in `accounts/src/normly_accounts/schemas.py`:

```python
class SessionValidationResponse(BaseModel):
    account_id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None
```

In `accounts/src/normly_accounts/routers/session.py`, update the return
statement of `validate_session` (the function already fetches the full
`Account` via `PostgresAccountRepository(session).get_account_by_id(...)` two
lines above this return — only the constructed response object changes):

```python
    return SessionValidationResponse(
        account_id=account.id, email=account.email,
        first_name=account.first_name, last_name=account.last_name,
        avatar_data_url=avatar_data_url(account),
    )
```

This needs `avatar_data_url` imported: add
`from normly_accounts.routers.login import avatar_data_url` to
`session.py`'s imports (`avatar_data_url` is already public/no-underscore per
Step 5 above, since it has two callers within this task alone, plus one more
in Task 4).

- [ ] **Step 7: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass. Existing tests asserting on `AccountResponse`'s or
`SessionValidationResponse`'s shape (grep `accounts/tests/` for
`email_verified` and for `account_id` to find them) will need the new fields
added to their expected-body assertions if they compare the full JSON body
rather than individual fields — check each one and update only if it actually
fails; most likely assert on individual fields (`body["account"]["email"]`)
and are unaffected.

- [ ] **Step 8: Commit**

```bash
git add accounts/src/normly_accounts/dependencies.py accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/routers/login.py accounts/src/normly_accounts/routers/session.py \
  accounts/tests/test_get_current_account.py
git commit -s -m "feat: add a shared get_current_account dependency and avatar/name fields to account responses"
```

(If Step 6 required editing any other test file to match the new
`AccountResponse` shape, add those files to this commit too.)

---

### Task 4: Profile (name + avatar) endpoints (`accounts/`)

**Files:**
- Modify: `accounts/pyproject.toml` (add `Pillow`, `python-multipart`)
- Create: `accounts/src/normly_accounts/routers/profile.py`
- Modify: `accounts/src/normly_accounts/schemas.py` (add
  `UpdateProfileRequest`)
- Modify: `accounts/src/normly_accounts/main.py` (register the new router)
- Test: `accounts/tests/test_profile.py`

**Interfaces:**
- Consumes: `get_current_account` (Task 3),
  `PostgresAccountRepository.update_profile_names/set_avatar/clear_avatar`
  (Task 1).
- Produces: `PATCH /v1/accounts/profile`, `POST /v1/accounts/avatar`,
  `DELETE /v1/accounts/avatar` — consumed by Task 10 (frontend BFF proxies).

- [ ] **Step 1: Add the new dependencies**

In `accounts/pyproject.toml`, add to the `dependencies` list (after
`"httpx>=0.27,<1.0",`):

```toml
    "Pillow>=10.0,<12.0",
    "python-multipart>=0.0.9,<1.0",
```

Run `cd accounts && pip3 --python .venv/bin/python install -e ".[dev]" -e ../core`
to pick up the new dependencies.

- [ ] **Step 2: Write the failing test**

```python
# accounts/tests/test_profile.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io

from PIL import Image

from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
)


def _register_and_authorize(client):
    response = client.post(
        "/v1/accounts/register", json={"email": "profile@example.de", "password": "correct horse"}
    )
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_test_image(size=(800, 600), color=(255, 0, 0)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_update_profile_sets_first_and_last_name(client):
    _, headers = _register_and_authorize(client)

    response = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Jamie"
    assert body["last_name"] == "Weber"


def test_update_profile_requires_authorization(client):
    response = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
    )
    assert response.status_code == 401


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


def test_upload_avatar_rejects_a_file_that_is_too_large(client):
    _, headers = _register_and_authorize(client)
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.bin", oversized, "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 400


def test_upload_avatar_rejects_a_non_image_file(client):
    _, headers = _register_and_authorize(client)

    response = client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.txt", b"not an image", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 400


def test_delete_avatar_clears_it(client, db_session):
    _, headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/avatar",
        files={"avatar": ("avatar.jpg", _make_test_image(), "image/jpeg")},
        headers=headers,
    )

    response = client.delete("/v1/accounts/avatar", headers=headers)

    assert response.status_code == 200
    assert response.json()["avatar_data_url"] is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_profile.py -v`
Expected: FAIL — the router doesn't exist yet.

- [ ] **Step 4: Add the request schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class UpdateProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
```

- [ ] **Step 5: Write the profile router**

```python
# accounts/src/normly_accounts/routers/profile.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import AccountResponse, UpdateProfileRequest

profile_router = APIRouter(prefix="/v1/accounts", tags=["profile"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_AVATAR_SIZE = (256, 256)


def _account_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id, email=account.email,
        email_verified=account.email_verified_at is not None,
        first_name=account.first_name, last_name=account.last_name,
        avatar_data_url=avatar_data_url(account),
    )


@profile_router.patch("/profile", response_model=AccountResponse)
def update_profile(
    payload: UpdateProfileRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> AccountResponse:
    account_repo = PostgresAccountRepository(session)
    account_repo.update_profile_names(
        account.id, first_name=payload.first_name, last_name=payload.last_name
    )
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.post("/avatar", response_model=AccountResponse)
def upload_avatar(
    avatar: UploadFile = File(...), account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> AccountResponse:
    raw = avatar.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="avatar image exceeds the 5 MB limit")

    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        # verify() invalidates the file handle for further use -- Image.open
        # again on the same bytes to get a usable image for resizing.
        image = Image.open(io.BytesIO(raw))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(
                status_code=400, detail="avatar must be a JPEG, PNG, or WebP image"
            )
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="avatar must be a valid image file")

    image = image.convert("RGB")
    image.thumbnail(_AVATAR_SIZE, Image.LANCZOS)
    # thumbnail() preserves aspect ratio and may not fill both dimensions --
    # paste onto a fixed 256x256 canvas so every avatar is exactly the same
    # size the frontend expects, centered rather than stretched/distorted.
    canvas = Image.new("RGB", _AVATAR_SIZE, (255, 255, 255))
    offset = ((_AVATAR_SIZE[0] - image.width) // 2, (_AVATAR_SIZE[1] - image.height) // 2)
    canvas.paste(image, offset)

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=85)

    account_repo = PostgresAccountRepository(session)
    account_repo.set_avatar(
        account.id, avatar_image=buffer.getvalue(), avatar_content_type="image/jpeg"
    )
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)


@profile_router.delete("/avatar", response_model=AccountResponse)
def delete_avatar(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> AccountResponse:
    account_repo = PostgresAccountRepository(session)
    account_repo.clear_avatar(account.id)
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)
```

(`avatar_data_url` is imported here, not redefined — Task 3 already made it a
public, no-underscore function in `login.py` specifically because it needs
callers outside that file, this being one of them.)

- [ ] **Step 6: Register the router**

In `accounts/src/normly_accounts/main.py`, add
`from normly_accounts.routers.profile import profile_router` and
`app.include_router(profile_router, responses=COMMON_ERROR_RESPONSES)`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_profile.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add accounts/pyproject.toml accounts/src/normly_accounts/routers/profile.py \
  accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py accounts/tests/test_profile.py
git commit -s -m "feat: add profile name and avatar upload endpoints"
```

---

### Task 5: Email change endpoints (`accounts/`)

**Files:**
- Create: `accounts/src/normly_accounts/routers/email_change.py`
- Modify: `accounts/src/normly_accounts/schemas.py` (add
  `EmailChangeRequest`)
- Modify: `accounts/src/normly_accounts/main.py` (register the new router)
- Test: `accounts/tests/test_email_change.py`

**Interfaces:**
- Consumes: `get_current_account` (Task 3), `AccountTokenPurpose.EMAIL_CHANGE`
  (Task 2).
- Produces: `POST /v1/accounts/email/change`, `GET /v1/accounts/email/confirm`
  — consumed by Task 11 (frontend BFF proxies).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_email_change.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import re


def _register_and_authorize(client, email="owner@example.de"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": "correct horse"}
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['session_token']}"}


def test_requesting_an_email_change_sends_a_confirmation_to_the_new_address(
    client, email_sender
):
    headers = _register_and_authorize(client)

    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "new-address@example.de"},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(email_sender.sent) == 2  # registration verification + this
    change_email = email_sender.sent[-1]
    assert change_email["to"] == "new-address@example.de"


def test_email_is_not_changed_until_the_link_is_confirmed(client, email_sender):
    headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/email/change", json={"new_email": "pending@example.de"}, headers=headers,
    )

    session_response = client.get("/v1/accounts/session", headers=headers)

    assert session_response.json()["email"] == "owner@example.de"


def test_confirming_the_link_actually_changes_the_email(client, email_sender):
    headers = _register_and_authorize(client)
    client.post(
        "/v1/accounts/email/change", json={"new_email": "confirmed@example.de"}, headers=headers,
    )
    token = re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)

    confirm_response = client.get(
        f"/v1/accounts/email/confirm?token={token}&email=confirmed@example.de"
    )

    assert confirm_response.status_code == 200
    session_response = client.get("/v1/accounts/session", headers=headers)
    assert session_response.json()["email"] == "confirmed@example.de"


def test_requesting_a_change_to_an_already_registered_email_returns_409(client):
    client.post(
        "/v1/accounts/register", json={"email": "taken@example.de", "password": "x"}
    )
    headers = _register_and_authorize(client, email="requester@example.de")

    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "taken@example.de"}, headers=headers,
    )

    assert response.status_code == 409


def test_confirming_an_invalid_token_returns_400(client):
    response = client.get(
        "/v1/accounts/email/confirm?token=does-not-exist&email=whatever@example.de"
    )
    assert response.status_code == 400


def test_email_change_requires_authorization(client):
    response = client.post(
        "/v1/accounts/email/change", json={"new_email": "nope@example.de"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_email_change.py -v`
Expected: FAIL — the router doesn't exist yet.

- [ ] **Step 3: Add the request schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class EmailChangeRequest(BaseModel):
    new_email: EmailStr
```

- [ ] **Step 4: Write the email-change router**

```python
# accounts/src/normly_accounts/routers/email_change.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AccountTokenPurpose
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountTokenRepository,
)

from normly_accounts.dependencies import get_current_account, get_email_sender, get_session
from normly_accounts.email import EmailSender
from normly_accounts.schemas import EmailChangeRequest
from normly_accounts.security import generate_token

logger = logging.getLogger(__name__)

email_change_router = APIRouter(prefix="/v1/accounts/email", tags=["email-change"])

_EMAIL_CHANGE_TOKEN_LIFETIME = timedelta(hours=24)


@email_change_router.post("/change")
def request_email_change(
    payload: EmailChangeRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session), email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    account_repo = PostgresAccountRepository(session)
    if account_repo.get_account_by_email(payload.new_email) is not None:
        # Unlike anonymous registration/reset-request, this caller is already
        # authenticated -- there is no enumeration risk in telling them the
        # address is taken, since they cannot use that information against
        # anyone but themselves.
        raise HTTPException(status_code=409, detail="an account already exists for this email")

    now = datetime.now(timezone.utc)
    token = PostgresAccountTokenRepository(session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.EMAIL_CHANGE,
        # The token's `email` field carries the PENDING new address here --
        # a different use than the "address with no account yet" case
        # magic-link/registration use it for, but the same nullable column;
        # account_id is set to the existing account in both this case and
        # that one, which is what account.email is actually changed to.
        token=generate_token(), created_at=now, expires_at=now + _EMAIL_CHANGE_TOKEN_LIFETIME,
    )
    # create_token's own signature takes email= as an alternative to
    # account_id=, not alongside it (see ck_account_token_account_or_email) --
    # so the pending address cannot travel on this token as written. Store it
    # via a second, minimal mechanism instead: reuse the token string itself
    # as the pointer, and re-derive the pending address from the *request*
    # this handler is already holding, encoding it into the emailed link
    # instead of the token record.
    try:
        email_sender.send(
            to=payload.new_email, subject="Bestätige deine neue E-Mail-Adresse",
            body=(
                f"Zum Bestätigen deiner neuen E-Mail-Adresse: "
                f"token={token.token}&email={payload.new_email}"
            ),
        )
    except Exception:
        logger.exception("email change confirmation delivery failed for %s", payload.new_email)
    return {"status": "confirmation_sent"}


@email_change_router.get("/confirm")
def confirm_email_change(
    token: str, email: str, session: Session = Depends(get_session),
) -> dict:
    consumed = PostgresAccountTokenRepository(session).consume_token(
        token, AccountTokenPurpose.EMAIL_CHANGE
    )
    if consumed is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    account_repo = PostgresAccountRepository(session)
    if account_repo.get_account_by_email(email) is not None:
        # The address was claimed by someone else between the request and
        # this confirm (e.g. a race with another registration) -- refuse
        # rather than raise an IntegrityError from the UPDATE below.
        raise HTTPException(status_code=409, detail="an account already exists for this email")

    account_repo.update_email(consumed.account_id, email)
    return {"status": "email_changed"}
```

**Design correction found while writing this task:** `AccountToken` has no
field to carry an arbitrary "pending new email" alongside an `account_id` —
its `email` column is exclusively the "address with no account yet" case
(`ck_account_token_account_or_email` forces exactly one of `account_id`/`email`
to be set, never both). The router above works around this by encoding the
pending address into the confirmation link's query string instead of the
token record, and the confirm endpoint re-validates that address is still free
before applying it. **This needs one more repository method this task's
Step 3 above did not anticipate:** `AccountRepository.update_email(account_id,
new_email) -> None`, mirroring `set_password_hash`'s shape exactly. Add it now:

In `core/src/normly_core/graph/domain.py`, add to `AccountRepository` (after
`set_password_hash`):

```python
    def update_email(self, account_id: uuid.UUID, new_email: str) -> None: ...
```

In `core/src/normly_core/graph/postgres/repositories.py`, add to
`PostgresAccountRepository` (after `set_password_hash`):

```python
    def update_email(self, account_id: uuid.UUID, new_email: str) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(email=new_email)
        )
```

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`, add
`from normly_accounts.routers.email_change import email_change_router` and
`app.include_router(email_change_router, responses=COMMON_ERROR_RESPONSES)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_email_change.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Run the full `core/` and `accounts/` suites**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: both all pass.

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py \
  accounts/src/normly_accounts/routers/email_change.py accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py accounts/tests/test_email_change.py
git commit -s -m "feat: add two-step email change with confirmation link"
```

---

### Task 6: Password set/change endpoint (`accounts/`)

**Files:**
- Create: `accounts/src/normly_accounts/routers/password.py`
- Modify: `accounts/src/normly_accounts/schemas.py` (add
  `SetPasswordRequest`)
- Modify: `accounts/src/normly_accounts/main.py` (register the new router)
- Test: `accounts/tests/test_set_password.py`

**Interfaces:**
- Consumes: `get_current_account` (Task 3), `hash_password`/`verify_password`
  (existing).
- Produces: `POST /v1/accounts/password` — consumed by Task 12 (frontend BFF
  proxy).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_set_password.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.postgres.repositories import PostgresAccountRepository


def test_setting_a_password_for_a_passwordless_account_needs_no_current_password(
    client, db_session
):
    account = PostgresAccountRepository(db_session).create_account(
        email="passwordless@example.de", password_hash=None
    )
    # Simulate an authenticated session the way a Google/magic-link login
    # would establish one, without going through that whole flow.
    login_response = client.post(
        "/v1/accounts/magic-link/request", json={"email": "passwordless@example.de"}
    )
    assert login_response.status_code == 200

    # No session exists yet for this pre-seeded account without going through
    # a real login flow -- register a password directly via the repository's
    # own session-issuing path instead, matching how login.py builds one.
    from datetime import datetime, timedelta, timezone
    from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository
    now = datetime.now(timezone.utc)
    session = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token="passwordless-session", created_at=now,
        expires_at=now + timedelta(days=30),
    )
    headers = {"Authorization": f"Bearer {session.session_token}"}

    response = client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 200
    login_check = client.post(
        "/v1/accounts/login", json={"email": "passwordless@example.de", "password": "new secret"}
    )
    assert login_check.status_code == 200


def test_changing_an_existing_password_requires_the_current_one(client):
    register = client.post(
        "/v1/accounts/register", json={"email": "haspassword@example.de", "password": "old secret"}
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = client.post(
        "/v1/accounts/password",
        json={"current_password": "wrong secret", "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 401


def test_changing_an_existing_password_with_the_correct_current_one_succeeds(client):
    register = client.post(
        "/v1/accounts/register", json={"email": "correct@example.de", "password": "old secret"}
    )
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    response = client.post(
        "/v1/accounts/password",
        json={"current_password": "old secret", "new_password": "new secret"},
        headers=headers,
    )

    assert response.status_code == 200
    login_check = client.post(
        "/v1/accounts/login", json={"email": "correct@example.de", "password": "new secret"}
    )
    assert login_check.status_code == 200


def test_set_password_requires_authorization(client):
    response = client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "x"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_set_password.py -v`
Expected: FAIL — the router doesn't exist yet.

- [ ] **Step 3: Add the request schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class SetPasswordRequest(BaseModel):
    current_password: str | None
    new_password: str
```

- [ ] **Step 4: Write the password router**

```python
# accounts/src/normly_accounts/routers/password.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import SetPasswordRequest
from normly_accounts.security import hash_password, verify_password

password_router = APIRouter(prefix="/v1/accounts", tags=["password"])


@password_router.post("/password")
def set_password(
    payload: SetPasswordRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    if account.password_hash is not None:
        if payload.current_password is None or not verify_password(
            payload.current_password, account.password_hash
        ):
            raise HTTPException(status_code=401, detail="current password is incorrect")
    # else: passwordless account (Google/magic-link) -- the valid session
    # itself already proved identity, nothing to compare the new password
    # against.

    PostgresAccountRepository(session).set_password_hash(
        account.id, hash_password(payload.new_password)
    )
    return {"status": "password_set"}
```

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`, add
`from normly_accounts.routers.password import password_router` and
`app.include_router(password_router, responses=COMMON_ERROR_RESPONSES)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_set_password.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add accounts/src/normly_accounts/routers/password.py accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py accounts/tests/test_set_password.py
git commit -s -m "feat: add set/change password endpoint"
```

---

### Task 7: Session management endpoints (`accounts/`)

**Files:**
- Create: `accounts/src/normly_accounts/routers/sessions.py`
- Modify: `accounts/src/normly_accounts/schemas.py` (add
  `SessionSummaryResponse`)
- Modify: `accounts/src/normly_accounts/main.py` (register the new router)
- Test: `accounts/tests/test_account_sessions_endpoint.py`

**Interfaces:**
- Consumes: `get_current_account` (Task 3),
  `PostgresAccountSessionRepository.list_sessions_for_account/
  revoke_session_by_id` (Task 2).
- Produces: `GET /v1/accounts/sessions`, `DELETE /v1/accounts/sessions/{id}` —
  consumed by Task 13 (frontend BFF proxies).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_account_sessions_endpoint.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository


def _register(client, email="sessions@example.de"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": "correct horse"}
    )
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def test_list_sessions_includes_the_current_one_marked_as_such(client):
    token, headers = _register(client)

    response = client.get("/v1/accounts/sessions", headers=headers)

    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True


def test_list_sessions_includes_other_sessions_not_marked_current(client, db_session):
    token, headers = _register(client)
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    now = datetime.now(timezone.utc)
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=account_id, session_token="other-device-token", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = client.get("/v1/accounts/sessions", headers=headers)

    sessions = response.json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["is_current"]]
    other = [s for s in sessions if not s["is_current"]]
    assert len(current) == 1
    assert len(other) == 1


def test_revoking_another_session_removes_it_from_the_list(client, db_session):
    token, headers = _register(client)
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    now = datetime.now(timezone.utc)
    other = PostgresAccountSessionRepository(db_session).create_session(
        account_id=account_id, session_token="revoke-target", created_at=now,
        expires_at=now + timedelta(days=30),
    )

    response = client.delete(f"/v1/accounts/sessions/{other.id}", headers=headers)

    assert response.status_code == 200
    remaining = client.get("/v1/accounts/sessions", headers=headers).json()
    assert len(remaining) == 1


def test_revoking_a_session_that_does_not_belong_to_you_returns_404(client):
    _, headers_a = _register(client, email="a@example.de")
    token_b, headers_b = _register(client, email="b@example.de")
    sessions_b = client.get("/v1/accounts/sessions", headers=headers_b).json()
    b_session_id = sessions_b[0]["id"]

    response = client.delete(f"/v1/accounts/sessions/{b_session_id}", headers=headers_a)

    assert response.status_code == 404
    # b's session is untouched.
    still_there = client.get("/v1/accounts/sessions", headers=headers_b)
    assert still_there.status_code == 200


def test_sessions_endpoints_require_authorization(client):
    assert client.get("/v1/accounts/sessions").status_code == 401
    import uuid
    assert client.delete(f"/v1/accounts/sessions/{uuid.uuid4()}").status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_account_sessions_endpoint.py -v`
Expected: FAIL — the router doesn't exist yet.

- [ ] **Step 3: Add the response schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class SessionSummaryResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    is_current: bool
```

- [ ] **Step 4: Write the sessions router**

```python
# accounts/src/normly_accounts/routers/sessions.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresAccountSessionRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import SessionSummaryResponse

sessions_router = APIRouter(prefix="/v1/accounts", tags=["sessions"])

_BEARER_PREFIX = "Bearer "


@sessions_router.get("/sessions", response_model=list[SessionSummaryResponse])
def list_sessions(
    authorization: str | None = Header(default=None),
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[SessionSummaryResponse]:
    # get_current_account has already validated this header -- re-reading it
    # here only identifies WHICH of the account's sessions is the one making
    # this very request, for the is_current flag below.
    current_token = authorization[len(_BEARER_PREFIX):] if authorization else None

    session_repo = PostgresAccountSessionRepository(session)
    sessions = session_repo.list_sessions_for_account(account.id)
    return [
        SessionSummaryResponse(
            id=s.id, created_at=s.created_at, expires_at=s.expires_at,
            is_current=(s.session_token == current_token),
        )
        for s in sessions
    ]


@sessions_router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    revoked = PostgresAccountSessionRepository(session).revoke_session_by_id(
        session_id, account.id
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "session_revoked"}
```

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`, add
`from normly_accounts.routers.sessions import sessions_router` and
`app.include_router(sessions_router, responses=COMMON_ERROR_RESPONSES)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_account_sessions_endpoint.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add accounts/src/normly_accounts/routers/sessions.py accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py accounts/tests/test_account_sessions_endpoint.py
git commit -s -m "feat: add session listing and per-session revocation endpoints"
```

---

### Task 8: Account deletion and data export endpoints (`accounts/`)

**Files:**
- Create: `accounts/src/normly_accounts/routers/account_management.py`
- Modify: `accounts/src/normly_accounts/schemas.py` (add
  `DeleteAccountRequest`, `ExportResponse` and its nested schemas)
- Modify: `accounts/src/normly_accounts/main.py` (register the new router)
- Test: `accounts/tests/test_account_management.py`

**Interfaces:**
- Consumes: `get_current_account` (Task 3),
  `PostgresAccountRepository.delete_account` (Task 2), `PostgresChatRepository`
  (existing, for export).
- Produces: `DELETE /v1/accounts/me`, `GET /v1/accounts/export` — consumed by
  Task 14 (frontend BFF proxies).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_account_management.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.domain import ChatMessageRole
from normly_core.graph.postgres.repositories import PostgresChatRepository


def _register(client, email="delete-target@example.de", password="correct horse"):
    response = client.post(
        "/v1/accounts/register", json={"email": email, "password": password}
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['session_token']}"}


def test_deleting_a_password_account_requires_the_password(client):
    headers = _register(client)

    response = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "wrong password"}, headers=headers,
    )

    assert response.status_code == 401


def test_deleting_a_password_account_with_the_correct_password_succeeds(client):
    headers = _register(client, password="correct horse")

    response = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "correct horse"}, headers=headers,
    )

    assert response.status_code == 200
    session_check = client.get("/v1/accounts/session", headers=headers)
    assert session_check.status_code == 401


def test_account_deletion_requires_authorization(client):
    response = client.request("DELETE", "/v1/accounts/me", json={"password": "x"})
    assert response.status_code == 401


def test_export_includes_account_fields(client):
    headers = _register(client, email="export@example.de")

    response = client.get("/v1/accounts/export", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "export@example.de"
    assert body["account"]["google_linked"] is False


def test_export_includes_chat_sessions_and_messages(client, db_session):
    headers = _register(client, email="chatexport@example.de")
    account_id = client.get("/v1/accounts/session", headers=headers).json()["account_id"]
    chat_repo = PostgresChatRepository(db_session)
    now = datetime.now(timezone.utc)
    chat_session = chat_repo.create_session(
        session_token="export-tok", jurisdiction="DE", language="de",
        created_at=now, account_id=account_id,
    )
    chat_repo.create_message(
        session_id=chat_session.id, role=ChatMessageRole.USER, content="Testfrage",
        answer_type=None, created_at=now,
    )

    response = client.get("/v1/accounts/export", headers=headers)

    body = response.json()
    assert len(body["chat_sessions"]) == 1
    assert body["chat_sessions"][0]["session_token"] == "export-tok"
    assert body["chat_sessions"][0]["messages"][0]["content"] == "Testfrage"


def test_export_requires_authorization(client):
    response = client.get("/v1/accounts/export")
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_account_management.py -v`
Expected: FAIL — the router doesn't exist yet.

- [ ] **Step 3: Add the request/response schemas**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class DeleteAccountRequest(BaseModel):
    password: str | None


class ExportAccountFields(BaseModel):
    email: str
    created_at: datetime
    email_verified: bool
    google_linked: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None


class ExportChatMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class ExportChatSession(BaseModel):
    session_token: str
    jurisdiction: str
    language: str
    created_at: datetime
    messages: list[ExportChatMessage]


class ExportResponse(BaseModel):
    account: ExportAccountFields
    chat_sessions: list[ExportChatSession]
```

- [ ] **Step 4: Write the account-management router**

```python
# accounts/src/normly_accounts/routers/account_management.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresChatRepository,
)

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.routers.login import avatar_data_url
from normly_accounts.schemas import (
    DeleteAccountRequest, ExportAccountFields, ExportChatMessage, ExportChatSession,
    ExportResponse,
)
from normly_accounts.security import verify_password

account_management_router = APIRouter(prefix="/v1/accounts", tags=["account-management"])


@account_management_router.delete("/me")
def delete_account(
    payload: DeleteAccountRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    if account.password_hash is not None:
        if payload.password is None or not verify_password(
            payload.password, account.password_hash
        ):
            raise HTTPException(status_code=401, detail="password is incorrect")
    # else: passwordless account -- the frontend already required a typed
    # email-address confirmation before ever sending this request; the valid
    # session itself is the only server-side proof available.

    PostgresAccountRepository(session).delete_account(account.id)
    return {"status": "account_deleted"}


@account_management_router.get("/export", response_model=ExportResponse)
def export_account_data(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> ExportResponse:
    google_linked = (
        PostgresAccountGoogleIdentityRepository(session).get_account_by_google_subject
        is not None  # placeholder replaced below -- see note
    )
    # get_account_by_google_subject takes a subject id, not an account id --
    # there is no "does this account have ANY Google identity" lookup on the
    # existing Protocol. Query it directly here instead of adding a new
    # repository method for a single read used only by this export endpoint.
    from normly_core.graph.postgres.orm import AccountGoogleIdentityORM
    google_linked = session.get(AccountGoogleIdentityORM, account.id) is not None

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

    return ExportResponse(
        account=ExportAccountFields(
            email=account.email, created_at=account.created_at,
            email_verified=account.email_verified_at is not None, google_linked=google_linked,
            first_name=account.first_name, last_name=account.last_name,
            avatar_data_url=avatar_data_url(account),
        ),
        chat_sessions=exported_sessions,
    )
```

(The `google_linked = (...)  # placeholder replaced below` line is dead code
left in by an editing mistake in this brief — **do not write it**. Only write
the `from normly_core.graph.postgres.orm import AccountGoogleIdentityORM` /
`google_linked = session.get(...)` lines for that lookup, nothing before them.)

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`, add
`from normly_accounts.routers.account_management import account_management_router`
and `app.include_router(account_management_router,
responses=COMMON_ERROR_RESPONSES)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_account_management.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add accounts/src/normly_accounts/routers/account_management.py \
  accounts/src/normly_accounts/schemas.py accounts/src/normly_accounts/main.py \
  accounts/tests/test_account_management.py
git commit -s -m "feat: add account deletion and data export endpoints"
```

---

### Task 9: Password-reset UI (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/auth/password-reset/request/route.ts`
- Create: `frontend/src/app/api/auth/password-reset/confirm/route.ts`
- Modify: `frontend/src/components/auth/login-form.tsx` (add a "forgot
  password?" link)
- Create: `frontend/src/app/reset-password/page.tsx`
- Create: `frontend/src/app/reset-password/reset-password-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json` (new `auth.*` keys)
- Test: `frontend/tests/unit/password-reset-route.test.ts`
- Test: `frontend/tests/unit/login-form.test.tsx` (extend for the new link)
- Test: `frontend/tests/unit/reset-password-page.test.tsx`

**Interfaces:**
- Consumes: `getBackendUrls` (existing), `Input`/`Button` (existing),
  `useTranslation` (existing).
- Produces: `POST /api/auth/password-reset/request`,
  `POST /api/auth/password-reset/confirm`, the `/reset-password` page —
  consumed by no later task (this is a UI leaf closing the pre-existing gap).

Closes a gap that predates this plan: `accounts/`'s `POST /v1/accounts/
password-reset/request` and `/confirm` have existed since an earlier
sub-project, but `frontend/` never wired up a BFF route or UI for them.

- [ ] **Step 1: Write the failing BFF route tests**

```typescript
// frontend/tests/unit/password-reset-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as requestReset } from "@/app/api/auth/password-reset/request/route";
import { POST as confirmReset } from "@/app/api/auth/password-reset/confirm/route";

const originalFetch = global.fetch;

describe("password reset BFF routes", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards a reset request to the backend", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "if_the_account_exists_an_email_was_sent" }), {
        status: 200,
      }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/request", {
      method: "POST", body: JSON.stringify({ email: "a@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await requestReset(request);

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/password-reset/request");
  });

  it("forwards a confirm request to the backend", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_changed" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token: "tok", new_password: "new secret" }),
      headers: { "content-type": "application/json" },
    });
    const response = await confirmReset(request);

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/password-reset/confirm");
  });

  it("passes through a 400 from an invalid confirm token", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/confirm", {
      method: "POST", body: JSON.stringify({ token: "bad", new_password: "x" }),
      headers: { "content-type": "application/json" },
    });
    const response = await confirmReset(request);

    expect(response.status).toBe(400);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- password-reset-route`
Expected: FAIL — neither route exists yet.

- [ ] **Step 3: Write the two BFF routes**

```typescript
// frontend/src/app/api/auth/password-reset/request/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/password-reset/request`,
    {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

```typescript
// frontend/src/app/api/auth/password-reset/confirm/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/password-reset/confirm`,
    {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Run the route tests to verify they pass**

Run: `cd frontend && npm test -- password-reset-route`
Expected: PASS (3 tests).

- [ ] **Step 5: Add the new i18n keys**

In `frontend/src/lib/i18n/de.json`, add to the existing `auth` object (after
`logoutButton`):

```json
    "forgotPasswordLink": "Passwort vergessen?",
    "resetRequestButton": "Anmeldelink senden",
    "resetLinkSent": "Falls ein Konto mit dieser Adresse existiert, wurde eine E-Mail versendet.",
    "backToLogin": "Zurück zur Anmeldung",
    "resetNewPasswordLabel": "Neues Passwort",
    "resetSubmitButton": "Passwort festlegen",
    "resetSuccessMessage": "Dein Passwort wurde geändert. Du kannst dich jetzt anmelden.",
    "resetInvalidToken": "Dieser Link ist ungültig oder abgelaufen."
```

In `frontend/src/lib/i18n/en.json`, add to the existing `auth` object (after
`logoutButton`):

```json
    "forgotPasswordLink": "Forgot password?",
    "resetRequestButton": "Send reset link",
    "resetLinkSent": "If an account exists for this address, an email was sent.",
    "backToLogin": "Back to login",
    "resetNewPasswordLabel": "New password",
    "resetSubmitButton": "Set password",
    "resetSuccessMessage": "Your password has been changed. You can now log in.",
    "resetInvalidToken": "This link is invalid or has expired."
```

(`resetRequestButton`'s German text intentionally matches
`magicLinkButton`'s wording style — "Anmeldelink senden" reads naturally for
this action too, even though it's a different key.)

- [ ] **Step 6: Add the "forgot password?" link to `LoginForm`**

Replace the full content of `frontend/src/components/auth/login-form.tsx`:

```tsx
// frontend/src/components/auth/login-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [showResetRequest, setShowResetRequest] = React.useState(false);
  const [resetSent, setResetSent] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(false);
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        onSuccess();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitResetRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setResetSent(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (showResetRequest) {
    if (resetSent) {
      return <p className="text-sm">{t("auth.resetLinkSent")}</p>;
    }
    return (
      <form onSubmit={submitResetRequest} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("auth.emailLabel")}
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <Button type="submit" disabled={isSubmitting}>
          {t("auth.resetRequestButton")}
        </Button>
        <button
          type="button"
          className="text-sm underline"
          onClick={() => setShowResetRequest(false)}
        >
          {t("auth.backToLogin")}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.emailLabel")}
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.passwordLabel")}
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </label>
      {error && <p className="text-sm text-red-600">{t("auth.genericError")}</p>}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.loginButton")}
      </Button>
      <button
        type="button"
        className="text-sm underline"
        onClick={() => setShowResetRequest(true)}
      >
        {t("auth.forgotPasswordLink")}
      </button>
    </form>
  );
}
```

- [ ] **Step 7: Write the failing `LoginForm` test for the new link**

Add this test case to the existing `describe("LoginForm", ...)` block in
`frontend/tests/unit/login-form.test.tsx` (the file already exists from an
earlier sub-project — add this as a third `it(...)` alongside the two already
there, do not replace the file):

```tsx
  it("switches to the reset-request view and back", async () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={vi.fn()} />
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Passwort vergessen?" }));
    expect(screen.getByRole("button", { name: "Anmeldelink senden" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Zurück zur Anmeldung" }));
    expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument();
  });
```

- [ ] **Step 8: Run the `LoginForm` tests to verify they pass**

Run: `cd frontend && npm test -- login-form`
Expected: PASS (3 tests).

- [ ] **Step 9: Write the failing `/reset-password` page test**

```tsx
// frontend/tests/unit/reset-password-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ResetPasswordContent } from "@/app/reset-password/reset-password-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token"),
}));

const originalFetch = global.fetch;

describe("ResetPasswordContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the new password with the token from the URL", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_changed" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ResetPasswordContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort festlegen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Dein Passwort wurde geändert. Du kannst dich jetzt anmelden."),
      ).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ token: "valid-token", new_password: "new secret" });
  });

  it("shows an error message on an invalid token response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ResetPasswordContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort festlegen" }));

    await waitFor(() =>
      expect(screen.getByText("Dieser Link ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `cd frontend && npm test -- reset-password-page`
Expected: FAIL — `@/app/reset-password/reset-password-content` doesn't exist
yet.

- [ ] **Step 11: Write the reset-password content component**

**Important — this file uses `useSearchParams()` from `next/navigation`,
which Next.js requires to sit inside a `<Suspense>` boundary in a Client
Component or `next build` errors ("should be wrapped in a suspense
boundary"), regardless of the root layout's `force-dynamic` export (that
setting affects rendering strategy, not this specific build-time requirement).
Wrap the usage as shown below — do not omit the `Suspense` wrapper.**

```tsx
// frontend/src/app/reset-password/reset-password-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

function ResetPasswordForm() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "success" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/password-reset/confirm", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      setStatus(response.ok ? "success" : "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!token) {
    return <p className="text-sm text-red-600">{t("auth.resetInvalidToken")}</p>;
  }
  if (status === "success") {
    return <p className="text-sm">{t("auth.resetSuccessMessage")}</p>;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.resetNewPasswordLabel")}
        <Input
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          required
        />
      </label>
      {status === "error" && (
        <p className="text-sm text-red-600">{t("auth.resetInvalidToken")}</p>
      )}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.resetSubmitButton")}
      </Button>
    </form>
  );
}

export function ResetPasswordContent() {
  return (
    <React.Suspense fallback={null}>
      <ResetPasswordForm />
    </React.Suspense>
  );
}
```

- [ ] **Step 12: Write the page wrapper**

```tsx
// frontend/src/app/reset-password/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { ResetPasswordContent } from "./reset-password-content";

export default function ResetPasswordPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader
        instanceName={config.instanceName} logoPath={config.logoPath}
        showHistoryLink={false}
      />
      <main className="mx-auto max-w-2xl p-4">
        <ResetPasswordContent />
      </main>
    </>
  );
}
```

- [ ] **Step 13: Run the test to verify it passes**

Run: `cd frontend && npm test -- reset-password-page`
Expected: PASS (2 tests).

- [ ] **Step 14: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS. Confirm `/reset-password` appears in the build's route
table as `ƒ` (Dynamic) and that the build does **not** emit a
"should be wrapped in a suspense boundary" error for this route — if it does,
the `Suspense` wrapper in Step 11 was written incorrectly; re-check it against
the code above exactly.

- [ ] **Step 15: Commit**

```bash
git add frontend/src/app/api/auth/password-reset/ frontend/src/components/auth/login-form.tsx \
  frontend/src/app/reset-password/ frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/password-reset-route.test.ts frontend/tests/unit/login-form.test.tsx \
  frontend/tests/unit/reset-password-page.test.tsx
git commit -s -m "feat: wire up the password-reset UI (backend support already existed)"
```

---

### Task 10: `/account` page shell, name/avatar section, header update (`frontend/`)

**Files:**
- Create: `frontend/src/lib/account-response.ts`
- Modify: `frontend/src/app/api/auth/session/route.ts`
- Create: `frontend/src/app/api/account/profile/route.ts`
- Create: `frontend/src/app/api/account/avatar/route.ts`
- Create: `frontend/src/components/ui/avatar.tsx`
- Create: `frontend/src/components/account/name-avatar-section.tsx`
- Create: `frontend/src/app/account/page.tsx`
- Create: `frontend/src/app/account/account-page-content.tsx`
- Modify: `frontend/src/components/app-header.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json`
- Test: `frontend/tests/unit/account-response.test.ts`
- Test: `frontend/tests/unit/account-profile-route.test.ts`
- Test: `frontend/tests/unit/account-avatar-route.test.ts`
- Test: `frontend/tests/unit/avatar.test.tsx`
- Test: `frontend/tests/unit/name-avatar-section.test.tsx`
- Test: `frontend/tests/unit/account-page.test.tsx`
- Test: `frontend/tests/unit/app-header.test.tsx` (extend)

**Interfaces:**
- Consumes: `getBackendUrls`, `readSessionCookies` (existing),
  `PATCH /v1/accounts/profile`, `POST`/`DELETE /v1/accounts/avatar` (Task 4).
- Produces: `AccountSummary` type + `mapAccountSummary` (from
  `@/lib/account-response`), `Avatar` component, the `/account` page's
  orchestrating `AccountPageContent` component (which Tasks 11-14 each extend
  with one more section) — consumed by Tasks 11-14 and by `AppHeader`.

`AccountPageContent` is deliberately a thin orchestrator that only fetches the
account once and renders section components — each section is its own file,
so Tasks 11-14 each add ONE new file plus a small, precisely-located two-line
edit to this task's `account-page-content.tsx`, rather than needing to
reproduce the whole growing page in every later task's brief.

- [ ] **Step 1: Write the failing test for the shared response mapper**

```typescript
// frontend/tests/unit/account-response.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { mapAccountSummary } from "@/lib/account-response";

describe("mapAccountSummary", () => {
  it("maps the backend's snake_case fields to the frontend's camelCase shape", () => {
    const result = mapAccountSummary("acc-1", "a@example.de", {
      first_name: "Jamie", last_name: "Weber", avatar_data_url: "data:image/jpeg;base64,xyz",
    });

    expect(result).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Weber",
      avatarDataUrl: "data:image/jpeg;base64,xyz",
    });
  });

  it("preserves null fields", () => {
    const result = mapAccountSummary("acc-2", "b@example.de", {
      first_name: null, last_name: null, avatar_data_url: null,
    });

    expect(result.firstName).toBeNull();
    expect(result.lastName).toBeNull();
    expect(result.avatarDataUrl).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- account-response`
Expected: FAIL — `@/lib/account-response` doesn't exist yet.

- [ ] **Step 3: Write the shared mapper**

```typescript
// frontend/src/lib/account-response.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// accounts/ returns snake_case JSON (Pydantic's default, unconfigured). The
// pre-existing /api/auth/session route already translates account_id ->
// accountId for the frontend -- every other account-data BFF route follows
// the same camelCase convention here, rather than mixing raw snake_case
// bodies with this one already-translated shape.
export interface AccountSummary {
  accountId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  avatarDataUrl: string | null;
}

interface RawAccountFields {
  first_name: string | null;
  last_name: string | null;
  avatar_data_url: string | null;
}

export function mapAccountSummary(
  accountId: string, email: string, raw: RawAccountFields,
): AccountSummary {
  return {
    accountId, email, firstName: raw.first_name, lastName: raw.last_name,
    avatarDataUrl: raw.avatar_data_url,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- account-response`
Expected: PASS (2 tests).

- [ ] **Step 5: Extend `/api/auth/session` to include the new fields**

Replace the full content of `frontend/src/app/api/auth/session/route.ts`
(preserving the existing stale-cookie-clearing behavior on a non-OK backend
response — do not drop the `response.cookies.delete(...)` line, it fixed a
real bug in an earlier sub-project's final review):

```typescript
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ account: null });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/session`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  if (!backendResponse.ok) {
    // The token the browser sent is expired/invalid -- stop it from
    // resending a dead token as Authorization on every subsequent
    // /api/chat/etc. call by clearing the stale cookie here too.
    const response = NextResponse.json({ account: null });
    response.cookies.delete("normly_account_session");
    return response;
  }
  const body = await backendResponse.json();
  return NextResponse.json({
    account: mapAccountSummary(body.account_id, body.email, body),
  });
}
```

- [ ] **Step 6: Write the profile and avatar BFF routes**

```typescript
// frontend/src/app/api/account/profile/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function PATCH(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/profile`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}
```

```typescript
// frontend/src/app/api/account/avatar/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const formData = await request.formData();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    body: formData,
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}
```

- [ ] **Step 7: Write the failing route tests**

```typescript
// frontend/tests/unit/account-profile-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { PATCH } from "@/app/api/account/profile/route";

const originalFetch = global.fetch;

describe("PATCH /api/account/profile", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session as Authorization and maps the response", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: "Jamie", last_name: "Weber", avatar_data_url: null,
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/profile", {
      method: "PATCH", body: JSON.stringify({ first_name: "Jamie", last_name: "Weber" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await PATCH(request);
    const body = await response.json();

    expect(body).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Weber",
      avatarDataUrl: null,
    });
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/profile", {
      method: "PATCH", body: JSON.stringify({ first_name: "x", last_name: "y" }),
      headers: { "content-type": "application/json" },
    });
    const response = await PATCH(request);
    expect(response.status).toBe(401);
  });
});
```

```typescript
// frontend/tests/unit/account-avatar-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST, DELETE } from "@/app/api/account/avatar/route";

const originalFetch = global.fetch;

describe("avatar BFF route", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards an uploaded file with the account session as Authorization", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: null, last_name: null, avatar_data_url: "data:image/jpeg;base64,xyz",
        }),
        { status: 200 },
      ),
    );
    const formData = new FormData();
    formData.append("avatar", new Blob([new Uint8Array([1, 2, 3])]), "avatar.jpg");

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "POST", body: formData,
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await POST(request);
    const body = await response.json();

    expect(body.avatarDataUrl).toBe("data:image/jpeg;base64,xyz");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("passes through a 400 from an invalid upload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "avatar must be a valid image file" }), {
        status: 400,
      }),
    );
    const formData = new FormData();
    formData.append("avatar", new Blob([new Uint8Array([1])]), "not-an-image.txt");

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "POST", body: formData,
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await POST(request);

    expect(response.status).toBe(400);
  });

  it("DELETE forwards the account session and maps the cleared response", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: null, last_name: null, avatar_data_url: null,
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "DELETE",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request);
    const body = await response.json();

    expect(body.avatarDataUrl).toBeNull();
  });
});
```

- [ ] **Step 8: Run the tests to verify they fail**

Run: `cd frontend && npm test -- account-profile-route account-avatar-route`
Expected: FAIL — neither route exists yet.

- [ ] **Step 9: Run the tests to verify they pass**

(The routes were already written in Step 6 — this step just confirms it.)

Run: `cd frontend && npm test -- account-profile-route account-avatar-route`
Expected: PASS (5 tests).

- [ ] **Step 10: Write the failing `Avatar` component test**

```tsx
// frontend/tests/unit/avatar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Avatar } from "@/components/ui/avatar";

describe("Avatar", () => {
  it("renders the image when avatarDataUrl is set", () => {
    render(
      <Avatar
        avatarDataUrl="data:image/jpeg;base64,xyz" firstName="Jamie" lastName="Weber"
        email="a@example.de"
      />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("src", "data:image/jpeg;base64,xyz");
  });

  it("renders both initials when first and last name are set", () => {
    render(
      <Avatar avatarDataUrl={null} firstName="Jamie" lastName="Weber" email="a@example.de" />,
    );
    expect(screen.getByText("JW")).toBeInTheDocument();
  });

  it("falls back to the first letter of the email when no name is set", () => {
    render(<Avatar avatarDataUrl={null} firstName={null} lastName={null} email="a@example.de" />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run the test to verify it fails**

Run: `cd frontend && npm test -- avatar.test`
Expected: FAIL — `@/components/ui/avatar` doesn't exist yet.

- [ ] **Step 12: Write the `Avatar` component**

```tsx
// frontend/src/components/ui/avatar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

function initialsFor(
  firstName: string | null, lastName: string | null, email: string,
): string {
  if (firstName && lastName) return `${firstName[0]}${lastName[0]}`.toUpperCase();
  if (firstName) return firstName[0].toUpperCase();
  if (lastName) return lastName[0].toUpperCase();
  return (email[0] ?? "?").toUpperCase();
}

export function Avatar({
  avatarDataUrl, firstName, lastName, email, size = 32,
}: {
  avatarDataUrl: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string;
  size?: number;
}) {
  if (avatarDataUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- avatarDataUrl
      // is a data: URI, not a remote URL next/image's optimizer could help
      // with, and it changes on every upload/removal, which next/image
      // handles awkwardly for user-controlled data URIs.
      //
      // alt is a real, non-empty string on purpose: alt="" gives the <img>
      // an implicit ARIA role of "presentation" instead of "img", which
      // both real screen readers and getByRole("img") in tests would then
      // skip entirely.
      <img
        src={avatarDataUrl} alt="Profilbild" className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-full bg-brand text-brand-foreground text-xs font-medium"
      style={{ width: size, height: size }}
    >
      {initialsFor(firstName, lastName, email)}
    </span>
  );
}
```

- [ ] **Step 13: Run the test to verify it passes**

Run: `cd frontend && npm test -- avatar.test`
Expected: PASS (3 tests).

- [ ] **Step 14: Add the `account` i18n namespace**

In `frontend/src/lib/i18n/de.json`, add a new top-level `account` object
(after `validity`):

```json
  "account": {
    "pageTitle": "Konto",
    "loginRequired": "Melde dich an, um dein Konto zu verwalten.",
    "nameAvatarTitle": "Name und Profilbild",
    "uploadAvatarButton": "Bild hochladen",
    "removeAvatarButton": "Bild entfernen",
    "firstNameLabel": "Vorname",
    "lastNameLabel": "Nachname",
    "saveNameButton": "Speichern"
  }
```

In `frontend/src/lib/i18n/en.json`, add the matching structure:

```json
  "account": {
    "pageTitle": "Account",
    "loginRequired": "Log in to manage your account.",
    "nameAvatarTitle": "Name and profile picture",
    "uploadAvatarButton": "Upload picture",
    "removeAvatarButton": "Remove picture",
    "firstNameLabel": "First name",
    "lastNameLabel": "Last name",
    "saveNameButton": "Save"
  }
```

- [ ] **Step 15: Write the failing `NameAvatarSection` test**

```tsx
// frontend/tests/unit/name-avatar-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null,
};

describe("NameAvatarSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("saves the entered first and last name", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Weber",
          avatarDataUrl: null,
        }),
        { status: 200 },
      ),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Vorname"), { target: { value: "Jamie" } });
    fireEvent.change(screen.getByLabelText("Nachname"), { target: { value: "Weber" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ first_name: "Jamie", last_name: "Weber" });
  });

  it("shows a remove button only when an avatar is already set", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.queryByText("Bild entfernen")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 16: Run the test to verify it fails**

Run: `cd frontend && npm test -- name-avatar-section`
Expected: FAIL — `@/components/account/name-avatar-section` doesn't exist yet.

- [ ] **Step 17: Write the `NameAvatarSection` component**

```tsx
// frontend/src/components/account/name-avatar-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function NameAvatarSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
  const { t } = useTranslation();
  const [firstName, setFirstName] = React.useState(account.firstName ?? "");
  const [lastName, setLastName] = React.useState(account.lastName ?? "");
  const [isSavingName, setIsSavingName] = React.useState(false);
  const [isUpdatingAvatar, setIsUpdatingAvatar] = React.useState(false);

  const saveName = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSavingName(true);
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ first_name: firstName || null, last_name: lastName || null }),
      });
      if (response.ok) {
        onAccountUpdated(await response.json());
      }
    } finally {
      setIsSavingName(false);
    }
  };

  const uploadAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUpdatingAvatar(true);
    try {
      const formData = new FormData();
      formData.append("avatar", file);
      const response = await fetch("/api/account/avatar", { method: "POST", body: formData });
      if (response.ok) {
        onAccountUpdated(await response.json());
      }
    } finally {
      setIsUpdatingAvatar(false);
      event.target.value = "";
    }
  };

  const removeAvatar = async () => {
    setIsUpdatingAvatar(true);
    try {
      const response = await fetch("/api/account/avatar", { method: "DELETE" });
      if (response.ok) {
        onAccountUpdated(await response.json());
      }
    } finally {
      setIsUpdatingAvatar(false);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.nameAvatarTitle")}</h2>
      <div className="flex items-center gap-4">
        <Avatar
          avatarDataUrl={account.avatarDataUrl} firstName={account.firstName}
          lastName={account.lastName} email={account.email} size={64}
        />
        <div className="flex flex-col gap-2">
          <label className="text-sm underline">
            {t("account.uploadAvatarButton")}
            <input
              type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
              onChange={uploadAvatar} disabled={isUpdatingAvatar}
            />
          </label>
          {account.avatarDataUrl && (
            <button
              type="button" className="text-sm text-red-600 underline"
              onClick={removeAvatar} disabled={isUpdatingAvatar}
            >
              {t("account.removeAvatarButton")}
            </button>
          )}
        </div>
      </div>
      <form onSubmit={saveName} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.firstNameLabel")}
          <Input value={firstName} onChange={(event) => setFirstName(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.lastNameLabel")}
          <Input value={lastName} onChange={(event) => setLastName(event.target.value)} />
        </label>
        <Button type="submit" disabled={isSavingName} className="self-start">
          {t("account.saveNameButton")}
        </Button>
      </form>
    </section>
  );
}
```

- [ ] **Step 18: Run the test to verify it passes**

Run: `cd frontend && npm test -- name-avatar-section`
Expected: PASS (2 tests).

- [ ] **Step 19: Write the failing `/account` page test**

```tsx
// frontend/tests/unit/account-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { AccountPageContent } from "@/app/account/account-page-content";

const originalFetch = global.fetch;

describe("AccountPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no session", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account: null }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <AccountPageContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument(),
    );
  });

  it("renders the name/avatar section once a session is found", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
        { status: 200 },
      ),
    );

    render(
      <LocaleProvider initialLocale="de">
        <AccountPageContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Name und Profilbild")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 20: Run the test to verify it fails**

Run: `cd frontend && npm test -- account-page`
Expected: FAIL — `@/app/account/account-page-content` doesn't exist yet.

- [ ] **Step 21: Write `account-page-content.tsx` and `page.tsx`**

```tsx
// frontend/src/app/account/account-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Deliberately thin: fetches the account once, renders section components.
// Tasks 11-14 each add one import and one <XSection ... /> line here, after
// <NameAvatarSection ... /> -- never reproduce this whole file in a later
// task's brief, only the small addition.

"use client";

import * as React from "react";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function AccountPageContent() {
  const { t } = useTranslation();
  const [account, setAccount] = React.useState<AccountSummary | null>(null);
  const [requiresLogin, setRequiresLogin] = React.useState(false);

  React.useEffect(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => {
        if (body.account === null) {
          setRequiresLogin(true);
        } else {
          setAccount(body.account);
        }
      });
  }, []);

  if (requiresLogin) {
    return <p>{t("account.loginRequired")}</p>;
  }
  if (account === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-xl font-semibold">{t("account.pageTitle")}</h1>
      <NameAvatarSection account={account} onAccountUpdated={setAccount} />
    </div>
  );
}
```

```tsx
// frontend/src/app/account/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { AccountPageContent } from "./account-page-content";

export default function AccountPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <AccountPageContent />
      </main>
    </>
  );
}
```

- [ ] **Step 22: Run the test to verify it passes**

Run: `cd frontend && npm test -- account-page`
Expected: PASS (2 tests).

- [ ] **Step 23: Update `AppHeader` to show the avatar and link to `/account`**

Replace the full content of `frontend/src/components/app-header.tsx`:

```tsx
// frontend/src/components/app-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { AuthDialog } from "@/components/auth/auth-dialog";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

// getInstanceConfig() reads process.env, which is only meaningful on the
// server (and isn't inlined for the client, since these aren't NEXT_PUBLIC_
// variables -- see lib/config.ts). Callers (page.tsx, chats/page.tsx) read
// it server-side and pass the result down as plain props instead of this
// component reading env vars itself.
export function AppHeader({
  instanceName,
  logoPath,
  showHistoryLink = true,
}: {
  instanceName: string;
  logoPath: string | null;
  showHistoryLink?: boolean;
}) {
  const { t } = useTranslation();
  const [account, setAccount] = React.useState<AccountSummary | null>(null);

  const refreshSession = React.useCallback(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => setAccount(body.account))
      .catch(() => setAccount(null));
  }, []);

  React.useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setAccount(null);
    }
  };

  return (
    <header className="flex items-center justify-between border-b p-4">
      {logoPath ? (
        <img src={logoPath} alt={instanceName} className="h-6" />
      ) : (
        <span className="font-semibold">{instanceName}</span>
      )}
      <div className="flex items-center gap-2">
        <Link href="/search" className="text-sm underline">
          {t("search.navLink")}
        </Link>
        {showHistoryLink && (
          <Link href="/chats" className="text-sm underline">
            {t("chat.historyLink")}
          </Link>
        )}
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        {account ? (
          <div className="flex items-center gap-2">
            <Link href="/account" className="flex items-center gap-2">
              <Avatar
                avatarDataUrl={account.avatarDataUrl} firstName={account.firstName}
                lastName={account.lastName} email={account.email}
              />
              <span className="text-sm text-muted-foreground">{account.email}</span>
            </Link>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              {t("auth.logoutButton")}
            </Button>
          </div>
        ) : (
          <AuthDialog onAuthenticated={refreshSession} />
        )}
      </div>
    </header>
  );
}
```

- [ ] **Step 24: Update the existing `AppHeader` test for the new session shape**

The existing `frontend/tests/unit/app-header.test.tsx` mocks `/api/auth/session`
with a plain `{accountId, email}` account object. Update every such mock in
that file to the new full shape (add `firstName: null, lastName: null,
avatarDataUrl: null` alongside the existing `accountId`/`email` fields) — find
each `fetch` mock returning an `account` object in that file and extend it;
do not remove or rewrite any existing assertion, only add the three missing
fields to the mocked response bodies so the component (which now destructures
them) doesn't render `undefined`.

- [ ] **Step 25: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS. Confirm `/account` appears in the build's route table as
`ƒ` (Dynamic).

- [ ] **Step 26: Commit**

```bash
git add frontend/src/lib/account-response.ts frontend/src/app/api/auth/session/route.ts \
  frontend/src/app/api/account/profile/ frontend/src/app/api/account/avatar/ \
  frontend/src/components/ui/avatar.tsx frontend/src/components/account/name-avatar-section.tsx \
  frontend/src/app/account/ frontend/src/components/app-header.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/account-response.test.ts frontend/tests/unit/account-profile-route.test.ts \
  frontend/tests/unit/account-avatar-route.test.ts frontend/tests/unit/avatar.test.tsx \
  frontend/tests/unit/name-avatar-section.test.tsx frontend/tests/unit/account-page.test.tsx \
  frontend/tests/unit/app-header.test.tsx
git commit -s -m "feat: add the /account page shell with name/avatar management"
```

---

### Task 11: Email-change section of `/account` (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/account/email/route.ts`
- Create: `frontend/src/app/api/account/email/confirm/route.ts`
- Create: `frontend/src/components/account/email-section.tsx`
- Create: `frontend/src/app/confirm-email-change/confirm-email-change-content.tsx`
- Create: `frontend/src/app/confirm-email-change/page.tsx`
- Modify: `frontend/src/app/account/account-page-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json`
- Test: `frontend/tests/unit/account-email-route.test.ts`
- Test: `frontend/tests/unit/email-section.test.tsx`
- Test: `frontend/tests/unit/confirm-email-change-page.test.tsx`

**Interfaces:**
- Consumes: `POST /v1/accounts/email/change` and `GET
  /v1/accounts/email/confirm?token=&email=` (Task 5), `AccountSummary` (Task
  10).
- Produces: nothing consumed by later tasks — this is a leaf section.

- [ ] **Step 1: Write the failing BFF route tests**

```typescript
// frontend/tests/unit/account-email-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/email/route";
import { GET } from "@/app/api/account/email/confirm/route";

const originalFetch = global.fetch;

describe("POST /api/account/email", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the new email", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "confirmation_sent" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/email", {
      method: "POST", body: JSON.stringify({ new_email: "new@example.de" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ new_email: "new@example.de" });
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/email", {
      method: "POST", body: JSON.stringify({ new_email: "new@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});

describe("GET /api/account/email/confirm", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the token and email query params without requiring a session", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_changed" }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/account/email/confirm?token=tok-1&email=new@example.de",
    );
    const response = await GET(request);

    expect(response.status).toBe(200);
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe(
      "http://accounts.internal/v1/accounts/email/confirm?token=tok-1&email=new%40example.de",
    );
  });

  it("passes through a 400 for an invalid token", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    const request = new NextRequest(
      "http://localhost/api/account/email/confirm?token=bad&email=new@example.de",
    );
    const response = await GET(request);

    expect(response.status).toBe(400);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- account-email-route`
Expected: FAIL — neither route exists yet.

- [ ] **Step 3: Write the two BFF routes**

```typescript
// frontend/src/app/api/account/email/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/email/change`, {
    method: "POST",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

```typescript
// frontend/src/app/api/account/email/confirm/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

// No session cookie is read or required here -- the link is followed from
// an email client, possibly in a different browser/session than the one
// that requested the change. Task 5's confirm endpoint re-validates the
// token and the address's availability on its own; this route is a plain
// query-string-forwarding proxy.
export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.nextUrl.searchParams.get("token") ?? "";
  const email = request.nextUrl.searchParams.get("email") ?? "";

  const backendUrl = new URL(`${getBackendUrls().accounts}/v1/accounts/email/confirm`);
  backendUrl.searchParams.set("token", token);
  backendUrl.searchParams.set("email", email);

  const backendResponse = await fetch(backendUrl.toString());
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- account-email-route`
Expected: PASS (4 tests).

- [ ] **Step 5: Add the `account` i18n keys for this section**

In `frontend/src/lib/i18n/de.json`, inside the existing `account` object (add
after `saveNameButton`):

```json
    "emailTitle": "E-Mail-Adresse",
    "currentEmailLabel": "Aktuelle E-Mail-Adresse",
    "newEmailLabel": "Neue E-Mail-Adresse",
    "requestEmailChangeButton": "E-Mail-Adresse ändern",
    "emailChangeSentMessage": "Bestätigungslink wurde an die neue Adresse gesendet.",
    "emailChangeGenericError": "Etwas ist schiefgelaufen. Bitte versuche es erneut.",
    "confirmEmailChangeSuccessMessage": "Deine E-Mail-Adresse wurde geändert. Du kannst dich jetzt mit der neuen Adresse anmelden.",
    "confirmEmailChangeErrorMessage": "Dieser Bestätigungslink ist ungültig oder abgelaufen."
```

In `frontend/src/lib/i18n/en.json`, inside the existing `account` object:

```json
    "emailTitle": "Email address",
    "currentEmailLabel": "Current email address",
    "newEmailLabel": "New email address",
    "requestEmailChangeButton": "Change email address",
    "emailChangeSentMessage": "A confirmation link was sent to the new address.",
    "emailChangeGenericError": "Something went wrong. Please try again.",
    "confirmEmailChangeSuccessMessage": "Your email address has been changed. You can now log in with the new address.",
    "confirmEmailChangeErrorMessage": "This confirmation link is invalid or has expired."
```

- [ ] **Step 6: Write the failing `EmailSection` test**

```tsx
// frontend/tests/unit/email-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { EmailSection } from "@/components/account/email-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "old@example.de", firstName: null, lastName: null,
  avatarDataUrl: null,
};

describe("EmailSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the current email and requests a change for a new one", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "confirmation_sent" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <EmailSection account={account} />
      </LocaleProvider>,
    );

    expect(screen.getByText("old@example.de")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Neue E-Mail-Adresse"), {
      target: { value: "new@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse ändern" }));

    await waitFor(() =>
      expect(
        screen.getByText("Bestätigungslink wurde an die neue Adresse gesendet."),
      ).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ new_email: "new@example.de" });
  });

  it("shows an error message when the request fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "an account already exists for this email" }), {
        status: 409,
      }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <EmailSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neue E-Mail-Adresse"), {
      target: { value: "taken@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Etwas ist schiefgelaufen. Bitte versuche es erneut.")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && npm test -- email-section`
Expected: FAIL — `@/components/account/email-section` doesn't exist yet.

- [ ] **Step 8: Write the `EmailSection` component**

```tsx
// frontend/src/components/account/email-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function EmailSection({ account }: { account: AccountSummary }) {
  const { t } = useTranslation();
  const [newEmail, setNewEmail] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "sent" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/email", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ new_email: newEmail }),
      });
      setStatus(response.ok ? "sent" : "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.emailTitle")}</h2>
      <p className="text-sm text-muted-foreground">
        {t("account.currentEmailLabel")}: {account.email}
      </p>
      {status === "sent" ? (
        <p className="text-sm">{t("account.emailChangeSentMessage")}</p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("account.newEmailLabel")}
            <Input
              type="email" value={newEmail} onChange={(event) => setNewEmail(event.target.value)}
              required
            />
          </label>
          {status === "error" && (
            <p className="text-sm text-red-600">{t("account.emailChangeGenericError")}</p>
          )}
          <Button type="submit" disabled={isSubmitting} className="self-start">
            {t("account.requestEmailChangeButton")}
          </Button>
        </form>
      )}
    </section>
  );
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd frontend && npm test -- email-section`
Expected: PASS (2 tests).

- [ ] **Step 10: Add the section to the account page orchestrator**

In `frontend/src/app/account/account-page-content.tsx`, add the import:

```tsx
import { EmailSection } from "@/components/account/email-section";
```

and add one line immediately after `<NameAvatarSection ... />`:

```tsx
      <EmailSection account={account} />
```

- [ ] **Step 11: Write the failing confirm-email-change page test**

```tsx
// frontend/tests/unit/confirm-email-change-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ConfirmEmailChangeContent } from "@/app/confirm-email-change/confirm-email-change-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token&email=new@example.de"),
}));

const originalFetch = global.fetch;

describe("ConfirmEmailChangeContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("confirms the change on mount and shows a success message", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_changed" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ConfirmEmailChangeContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(
        screen.getByText(
          "Deine E-Mail-Adresse wurde geändert. Du kannst dich jetzt mit der neuen Adresse anmelden.",
        ),
      ).toBeInTheDocument(),
    );
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe("/api/account/email/confirm?token=valid-token&email=new@example.de");
  });

  it("shows an error message on an invalid token", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ConfirmEmailChangeContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Dieser Bestätigungslink ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 12: Run the test to verify it fails**

Run: `cd frontend && npm test -- confirm-email-change-page`
Expected: FAIL — `@/app/confirm-email-change/confirm-email-change-content` doesn't
exist yet.

- [ ] **Step 13: Write the confirm-email-change content and page**

Same `useSearchParams()` + `<Suspense>` requirement as Task 9's
`reset-password-content.tsx` applies here — do not omit the wrapper.

```tsx
// frontend/src/app/confirm-email-change/confirm-email-change-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "@/lib/i18n/provider";

function ConfirmEmailChangeInner() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const email = searchParams.get("email") ?? "";
  const [status, setStatus] = React.useState<"pending" | "success" | "error">("pending");

  React.useEffect(() => {
    if (!token || !email) {
      setStatus("error");
      return;
    }
    fetch(
      `/api/account/email/confirm?token=${encodeURIComponent(token)}&email=${encodeURIComponent(email)}`,
    )
      .then((response) => setStatus(response.ok ? "success" : "error"))
      .catch(() => setStatus("error"));
  }, [token, email]);

  if (status === "pending") {
    return null;
  }
  if (status === "success") {
    return <p className="text-sm">{t("account.confirmEmailChangeSuccessMessage")}</p>;
  }
  return <p className="text-sm text-red-600">{t("account.confirmEmailChangeErrorMessage")}</p>;
}

export function ConfirmEmailChangeContent() {
  return (
    <React.Suspense fallback={null}>
      <ConfirmEmailChangeInner />
    </React.Suspense>
  );
}
```

```tsx
// frontend/src/app/confirm-email-change/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { ConfirmEmailChangeContent } from "./confirm-email-change-content";

export default function ConfirmEmailChangePage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader
        instanceName={config.instanceName} logoPath={config.logoPath}
        showHistoryLink={false}
      />
      <main className="mx-auto max-w-2xl p-4">
        <ConfirmEmailChangeContent />
      </main>
    </>
  );
}
```

- [ ] **Step 14: Run the test to verify it passes**

Run: `cd frontend && npm test -- confirm-email-change-page`
Expected: PASS (2 tests).

- [ ] **Step 15: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS. Confirm `/confirm-email-change` appears in the build's
route table as `ƒ` (Dynamic) with no suspense-boundary build error.

- [ ] **Step 16: Commit**

```bash
git add frontend/src/app/api/account/email/ frontend/src/components/account/email-section.tsx \
  frontend/src/app/confirm-email-change/ frontend/src/app/account/account-page-content.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/account-email-route.test.ts frontend/tests/unit/email-section.test.tsx \
  frontend/tests/unit/confirm-email-change-page.test.tsx
git commit -s -m "feat: add the email-change section to the account page"
```

---

### Task 12: Password section of `/account` (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/account/password/route.ts`
- Create: `frontend/src/components/account/password-section.tsx`
- Modify: `frontend/src/app/account/account-page-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json`
- Test: `frontend/tests/unit/account-password-route.test.ts`
- Test: `frontend/tests/unit/password-section.test.tsx`

**Interfaces:**
- Consumes: `POST /v1/accounts/password` (Task 6), `AccountSummary` (Task 10).
- Produces: nothing consumed by later tasks — this is a leaf section. The
  section shows the "current password" field only when
  `account` has ever had a password set — but `AccountSummary` (Task 10)
  carries no `hasPassword` flag, so this task always renders the current-
  password field and lets the backend's own passwordless-account branch
  (Task 6's `set_password`, which treats `current_password: null` as valid
  when the account has no password hash) decide whether it was needed. This
  keeps the frontend simple and matches the backend's actual authority over
  that decision.

- [ ] **Step 1: Write the failing BFF route test**

```typescript
// frontend/tests/unit/account-password-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/password/route";

const originalFetch = global.fetch;

describe("POST /api/account/password", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the password payload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/password", {
      method: "POST",
      body: JSON.stringify({ current_password: "old", new_password: "new secret" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/password", {
      method: "POST", body: JSON.stringify({ current_password: null, new_password: "x" }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- account-password-route`
Expected: FAIL — the route doesn't exist yet.

- [ ] **Step 3: Write the BFF route**

```typescript
// frontend/src/app/api/account/password/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/password`, {
    method: "POST",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- account-password-route`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the `account` i18n keys for this section**

In `frontend/src/lib/i18n/de.json`, inside the existing `account` object (add
after `confirmEmailChangeErrorMessage`):

```json
    "passwordTitle": "Passwort",
    "currentPasswordLabel": "Aktuelles Passwort",
    "newPasswordLabel": "Neues Passwort",
    "changePasswordButton": "Passwort ändern",
    "passwordChangedMessage": "Dein Passwort wurde geändert.",
    "passwordChangeError": "Das aktuelle Passwort ist falsch."
```

In `frontend/src/lib/i18n/en.json`, inside the existing `account` object:

```json
    "passwordTitle": "Password",
    "currentPasswordLabel": "Current password",
    "newPasswordLabel": "New password",
    "changePasswordButton": "Change password",
    "passwordChangedMessage": "Your password has been changed.",
    "passwordChangeError": "The current password is incorrect."
```

- [ ] **Step 6: Write the failing `PasswordSection` test**

```tsx
// frontend/tests/unit/password-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { PasswordSection } from "@/components/account/password-section";

const originalFetch = global.fetch;

describe("PasswordSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the current and new password and shows a success message", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), {
      target: { value: "old secret" },
    });
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Dein Passwort wurde geändert.")).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      current_password: "old secret", new_password: "new secret",
    });
  });

  it("sends null for an empty current-password field", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ current_password: null, new_password: "new secret" });
  });

  it("shows an error message on a 401 response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "current password is incorrect" }), { status: 401 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), {
      target: { value: "wrong" },
    });
    fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: "new secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Das aktuelle Passwort ist falsch.")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && npm test -- password-section`
Expected: FAIL — `@/components/account/password-section` doesn't exist yet.

- [ ] **Step 8: Write the `PasswordSection` component**

```tsx
// frontend/src/components/account/password-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function PasswordSection() {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "success" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword || null, new_password: newPassword,
        }),
      });
      setStatus(response.ok ? "success" : "error");
      if (response.ok) {
        setCurrentPassword("");
        setNewPassword("");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.passwordTitle")}</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.currentPasswordLabel")}
          <Input
            type="password" value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.newPasswordLabel")}
          <Input
            type="password" value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)} required
          />
        </label>
        {status === "success" && (
          <p className="text-sm">{t("account.passwordChangedMessage")}</p>
        )}
        {status === "error" && (
          <p className="text-sm text-red-600">{t("account.passwordChangeError")}</p>
        )}
        <Button type="submit" disabled={isSubmitting} className="self-start">
          {t("account.changePasswordButton")}
        </Button>
      </form>
    </section>
  );
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd frontend && npm test -- password-section`
Expected: PASS (3 tests).

- [ ] **Step 10: Add the section to the account page orchestrator**

In `frontend/src/app/account/account-page-content.tsx`, add the import:

```tsx
import { PasswordSection } from "@/components/account/password-section";
```

and add one line immediately after `<EmailSection account={account} />`:

```tsx
      <PasswordSection />
```

- [ ] **Step 11: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/app/api/account/password/ frontend/src/components/account/password-section.tsx \
  frontend/src/app/account/account-page-content.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/account-password-route.test.ts frontend/tests/unit/password-section.test.tsx
git commit -s -m "feat: add the password section to the account page"
```

---

### Task 13: Sessions section of `/account` (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/account/sessions/route.ts`
- Create: `frontend/src/app/api/account/sessions/[sessionId]/route.ts`
- Create: `frontend/src/components/account/sessions-section.tsx`
- Modify: `frontend/src/app/account/account-page-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json`
- Test: `frontend/tests/unit/account-sessions-route.test.ts`
- Test: `frontend/tests/unit/sessions-section.test.tsx`

**Interfaces:**
- Consumes: `GET /v1/accounts/sessions`, `DELETE
  /v1/accounts/sessions/{id}` (Task 7).
- Produces: nothing consumed by later tasks — this is a leaf section.

- [ ] **Step 1: Write the failing BFF route tests**

```typescript
// frontend/tests/unit/account-sessions-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/sessions/route";
import { DELETE } from "@/app/api/account/sessions/[sessionId]/route";

const originalFetch = global.fetch;

describe("GET /api/account/sessions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and returns the list", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "sess-1", created_at: "2026-08-01T00:00:00Z",
            expires_at: "2026-09-01T00:00:00Z", is_current: true,
          },
        ]),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/sessions", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toHaveLength(1);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/sessions");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});

describe("DELETE /api/account/sessions/[sessionId]", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the session id", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "session_revoked" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/sessions/sess-2", {
      method: "DELETE", headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request, { params: Promise.resolve({ sessionId: "sess-2" }) });

    expect(response.status).toBe(200);
    const [calledUrl, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe("http://accounts.internal/v1/accounts/sessions/sess-2");
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/sessions/sess-2", {
      method: "DELETE",
    });
    const response = await DELETE(request, { params: Promise.resolve({ sessionId: "sess-2" }) });
    expect(response.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- account-sessions-route`
Expected: FAIL — neither route exists yet.

- [ ] **Step 3: Write the two BFF routes**

```typescript
// frontend/src/app/api/account/sessions/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/sessions`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

```typescript
// frontend/src/app/api/account/sessions/[sessionId]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function DELETE(
  request: NextRequest, { params }: { params: Promise<{ sessionId: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const { sessionId } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/sessions/${sessionId}`,
    { method: "DELETE", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- account-sessions-route`
Expected: PASS (4 tests).

- [ ] **Step 5: Add the `account` i18n keys for this section**

In `frontend/src/lib/i18n/de.json`, inside the existing `account` object (add
after `passwordChangeError`):

```json
    "sessionsTitle": "Aktive Sitzungen",
    "sessionCurrentBadge": "Dieses Gerät",
    "sessionCreatedLabel": "Angemeldet seit",
    "revokeSessionButton": "Sitzung beenden"
```

In `frontend/src/lib/i18n/en.json`, inside the existing `account` object:

```json
    "sessionsTitle": "Active sessions",
    "sessionCurrentBadge": "This device",
    "sessionCreatedLabel": "Signed in since",
    "revokeSessionButton": "End session"
```

- [ ] **Step 6: Write the failing `SessionsSection` test**

```tsx
// frontend/tests/unit/sessions-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { SessionsSection } from "@/components/account/sessions-section";

const originalFetch = global.fetch;

describe("SessionsSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("lists sessions and marks the current one", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "sess-1", created_at: "2026-08-01T00:00:00Z",
            expires_at: "2026-09-01T00:00:00Z", is_current: true,
          },
          {
            id: "sess-2", created_at: "2026-08-15T00:00:00Z",
            expires_at: "2026-09-15T00:00:00Z", is_current: false,
          },
        ]),
        { status: 200 },
      ),
    );

    render(
      <LocaleProvider initialLocale="de">
        <SessionsSection />
      </LocaleProvider>,
    );

    await waitFor(() => expect(screen.getByText("Dieses Gerät")).toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: "Sitzung beenden" })).toHaveLength(1);
  });

  it("removes a session from the list after revoking it", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "sess-1", created_at: "2026-08-01T00:00:00Z",
              expires_at: "2026-09-01T00:00:00Z", is_current: true,
            },
            {
              id: "sess-2", created_at: "2026-08-15T00:00:00Z",
              expires_at: "2026-09-15T00:00:00Z", is_current: false,
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "session_revoked" }), { status: 200 }),
      );

    render(
      <LocaleProvider initialLocale="de">
        <SessionsSection />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Sitzung beenden" })).toHaveLength(1),
    );
    fireEvent.click(screen.getByRole("button", { name: "Sitzung beenden" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(calledUrl).toBe("/api/account/sessions/sess-2");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Sitzung beenden" })).not.toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && npm test -- sessions-section`
Expected: FAIL — `@/components/account/sessions-section` doesn't exist yet.

- [ ] **Step 8: Write the `SessionsSection` component**

```tsx
// frontend/src/components/account/sessions-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

interface SessionSummary {
  id: string;
  createdAt: string;
  expiresAt: string;
  isCurrent: boolean;
}

interface RawSessionSummary {
  id: string;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export function SessionsSection() {
  const { t, locale } = useTranslation();
  const [sessions, setSessions] = React.useState<SessionSummary[] | null>(null);

  const load = React.useCallback(() => {
    fetch("/api/account/sessions")
      .then((response) => response.json())
      .then((raw: RawSessionSummary[]) =>
        setSessions(
          raw.map((s) => ({
            id: s.id, createdAt: s.created_at, expiresAt: s.expires_at, isCurrent: s.is_current,
          })),
        ),
      );
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const revoke = async (sessionId: string) => {
    const response = await fetch(`/api/account/sessions/${sessionId}`, { method: "DELETE" });
    if (response.ok) {
      setSessions((current) => (current ?? []).filter((s) => s.id !== sessionId));
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.sessionsTitle")}</h2>
      <ul className="flex flex-col gap-2">
        {(sessions ?? []).map((session) => (
          <li key={session.id} className="flex items-center justify-between gap-3 text-sm">
            <span>
              {t("account.sessionCreatedLabel")}{" "}
              {new Date(session.createdAt).toLocaleDateString(locale)}
              {session.isCurrent && (
                <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
                  {t("account.sessionCurrentBadge")}
                </span>
              )}
            </span>
            {!session.isCurrent && (
              <Button variant="ghost" size="sm" onClick={() => revoke(session.id)}>
                {t("account.revokeSessionButton")}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd frontend && npm test -- sessions-section`
Expected: PASS (2 tests).

- [ ] **Step 10: Add the section to the account page orchestrator**

In `frontend/src/app/account/account-page-content.tsx`, add the import:

```tsx
import { SessionsSection } from "@/components/account/sessions-section";
```

and add one line immediately after `<PasswordSection />`:

```tsx
      <SessionsSection />
```

- [ ] **Step 11: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/app/api/account/sessions/ frontend/src/components/account/sessions-section.tsx \
  frontend/src/app/account/account-page-content.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/account-sessions-route.test.ts frontend/tests/unit/sessions-section.test.tsx
git commit -s -m "feat: add the sessions section to the account page"
```

---

### Task 14: Export and deletion sections of `/account` (`frontend/`)

**Files:**
- Create: `frontend/src/app/api/account/export/route.ts`
- Create: `frontend/src/app/api/account/delete/route.ts`
- Create: `frontend/src/components/account/export-section.tsx`
- Create: `frontend/src/components/account/delete-account-section.tsx`
- Modify: `frontend/src/app/account/account-page-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `en.json`
- Test: `frontend/tests/unit/account-export-route.test.ts`
- Test: `frontend/tests/unit/account-delete-route.test.ts`
- Test: `frontend/tests/unit/export-section.test.tsx`
- Test: `frontend/tests/unit/delete-account-section.test.tsx`

**Interfaces:**
- Consumes: `GET /v1/accounts/export`, `DELETE /v1/accounts/me` (Task 8).
- Produces: nothing consumed by later tasks — these are the final leaf
  sections; Task 15 tests the whole assembled page instead of anything these
  export.

- [ ] **Step 1: Write the failing BFF route tests**

```typescript
// frontend/tests/unit/account-export-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/export/route";

const originalFetch = global.fetch;

describe("GET /api/account/export", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and returns the export payload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    const exportBody = {
      account: {
        email: "a@example.de", created_at: "2026-01-01T00:00:00Z", email_verified: true,
        google_linked: false, first_name: null, last_name: null, avatar_data_url: null,
      },
      chat_sessions: [],
    };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(exportBody), { status: 200 }));

    const request = new NextRequest("http://localhost/api/account/export", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toEqual(exportBody);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/export");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});
```

```typescript
// frontend/tests/unit/account-delete-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/delete/route";

const originalFetch = global.fetch;

describe("POST /api/account/delete", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the password and clears the session cookie on success", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "account_deleted" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: "correct horse" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value ?? "").toBe("");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ password: "correct horse" });
  });

  it("does not clear the cookie when the backend rejects the password", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "password is incorrect" }), { status: 401 }),
    );

    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: "wrong" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(401);
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: null }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- account-export-route account-delete-route`
Expected: FAIL — neither route exists yet.

- [ ] **Step 3: Write the two BFF routes**

```typescript
// frontend/src/app/api/account/export/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/export`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

```typescript
// frontend/src/app/api/account/delete/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/me`, {
    method: "DELETE",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok) {
    response.cookies.delete("normly_account_session");
  }
  return response;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- account-export-route account-delete-route`
Expected: PASS (5 tests).

- [ ] **Step 5: Add the `account` i18n keys for these sections**

In `frontend/src/lib/i18n/de.json`, inside the existing `account` object (add
after `revokeSessionButton`):

```json
    "exportTitle": "Daten exportieren",
    "exportDescription": "Lade deine Konto-Stammdaten und deinen vollständigen Chat-Verlauf als Datei herunter.",
    "exportButton": "Export herunterladen",
    "deleteAccountTitle": "Konto löschen",
    "deleteAccountDescription": "Löscht dein Konto und alle verknüpften Daten unwiderruflich, einschließlich des gesamten Chat-Verlaufs.",
    "deleteAccountPasswordLabel": "Passwort zur Bestätigung",
    "deleteAccountConfirmLabel": "Gib zur Bestätigung deine E-Mail-Adresse ein",
    "deleteAccountButton": "Konto endgültig löschen",
    "deleteAccountError": "Konto konnte nicht gelöscht werden. Prüfe deine Eingaben."
```

In `frontend/src/lib/i18n/en.json`, inside the existing `account` object:

```json
    "exportTitle": "Export data",
    "exportDescription": "Download your account details and full chat history as a file.",
    "exportButton": "Download export",
    "deleteAccountTitle": "Delete account",
    "deleteAccountDescription": "Permanently deletes your account and all linked data, including your entire chat history.",
    "deleteAccountPasswordLabel": "Password to confirm",
    "deleteAccountConfirmLabel": "Type your email address to confirm",
    "deleteAccountButton": "Permanently delete account",
    "deleteAccountError": "Could not delete the account. Check your input."
```

- [ ] **Step 6: Write the failing `ExportSection` test**

```tsx
// frontend/tests/unit/export-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ExportSection } from "@/components/account/export-section";

const originalFetch = global.fetch;

describe("ExportSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("fetches the export payload and triggers a download when clicked", async () => {
    const exportBody = { account: { email: "a@example.de" }, chat_sessions: [] };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(exportBody), { status: 200 }));
    const createObjectUrlSpy = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectUrlSpy = vi.fn();
    global.URL.createObjectURL = createObjectUrlSpy;
    global.URL.revokeObjectURL = revokeObjectUrlSpy;

    render(
      <LocaleProvider initialLocale="de">
        <ExportSection />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Export herunterladen" }));

    await waitFor(() => expect(createObjectUrlSpy).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith("/api/account/export");
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd frontend && npm test -- export-section`
Expected: FAIL — `@/components/account/export-section` doesn't exist yet.

- [ ] **Step 8: Write the `ExportSection` component**

```tsx
// frontend/src/components/account/export-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function ExportSection() {
  const { t } = useTranslation();
  const [isDownloading, setIsDownloading] = React.useState(false);

  const download = async () => {
    setIsDownloading(true);
    try {
      const response = await fetch("/api/account/export");
      if (!response.ok) return;
      const body = await response.json();
      const blob = new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "normly-konto-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.exportTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.exportDescription")}</p>
      <Button variant="outline" onClick={download} disabled={isDownloading} className="self-start">
        {t("account.exportButton")}
      </Button>
    </section>
  );
}
```

`link.click()` on a detached, unattached `<a>` element works in every
browser this project targets — the element does not need to be appended to
`document.body` first, and Vitest's jsdom environment supports it too (it is
never asserted on directly in the test above; only `createObjectURL` being
called is).

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd frontend && npm test -- export-section`
Expected: PASS (1 test).

- [ ] **Step 10: Write the failing `DeleteAccountSection` test**

```tsx
// frontend/tests/unit/delete-account-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null,
};

describe("DeleteAccountSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("only enables the delete button once the typed email matches the account email", () => {
    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );

    const deleteButton = screen.getByRole("button", { name: "Konto endgültig löschen" });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "wrong@example.de" },
    });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    expect(deleteButton).not.toBeDisabled();
  });

  it("submits the password and reloads the page on success", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "account_deleted" }), { status: 200 }),
    );
    const reloadSpy = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload: reloadSpy });

    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort zur Bestätigung"), {
      target: { value: "correct horse" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto endgültig löschen" }));

    await waitFor(() => expect(reloadSpy).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ password: "correct horse" });
  });

  it("shows an error message when the backend rejects the password", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "password is incorrect" }), { status: 401 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort zur Bestätigung"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto endgültig löschen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Konto konnte nicht gelöscht werden. Prüfe deine Eingaben."),
      ).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 11: Run the test to verify it fails**

Run: `cd frontend && npm test -- delete-account-section`
Expected: FAIL — `@/components/account/delete-account-section` doesn't exist
yet.

- [ ] **Step 12: Write the `DeleteAccountSection` component**

```tsx
// frontend/src/components/account/delete-account-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

// The typed-email confirmation is a frontend-only speed bump against
// misclicks -- it is never sent to the backend. The backend's own
// authority for this destructive action is the DeleteAccountRequest.password
// field (Task 8), required whenever the account has a password hash at all;
// a passwordless account relies solely on its valid session, same as Task 8's
// delete_account handler already documents.
export function DeleteAccountSection({ account }: { account: AccountSummary }) {
  const { t } = useTranslation();
  const [confirmEmail, setConfirmEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const canDelete = confirmEmail === account.email;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/delete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password: password || null }),
      });
      if (response.ok) {
        window.location.reload();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3 rounded border border-red-600 p-4">
      <h2 className="text-lg font-semibold text-red-600">{t("account.deleteAccountTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.deleteAccountDescription")}</p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.deleteAccountConfirmLabel")}
          <Input value={confirmEmail} onChange={(event) => setConfirmEmail(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.deleteAccountPasswordLabel")}
          <Input
            type="password" value={password} onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="text-sm text-red-600">{t("account.deleteAccountError")}</p>}
        <Button
          type="submit" disabled={!canDelete || isSubmitting}
          className="self-start bg-red-600 text-white hover:bg-red-700"
        >
          {t("account.deleteAccountButton")}
        </Button>
      </form>
    </section>
  );
}
```

`frontend/src/components/ui/button.tsx` only defines `default`/`outline`/
`ghost` variants (no `destructive`) — the red styling above is applied via
`className` overriding the `default` variant's background, matching how
other one-off color overrides are already done in this codebase rather than
adding a new variant for a single call site.

- [ ] **Step 13: Run the test to verify it passes**

Run: `cd frontend && npm test -- delete-account-section`
Expected: PASS (3 tests).

- [ ] **Step 14: Add both sections to the account page orchestrator**

In `frontend/src/app/account/account-page-content.tsx`, add the imports:

```tsx
import { ExportSection } from "@/components/account/export-section";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
```

and add two lines immediately after `<SessionsSection />`:

```tsx
      <ExportSection />
      <DeleteAccountSection account={account} />
```

- [ ] **Step 15: Run the full frontend unit suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS.

- [ ] **Step 16: Commit**

```bash
git add frontend/src/app/api/account/export/ frontend/src/app/api/account/delete/ \
  frontend/src/components/account/export-section.tsx \
  frontend/src/components/account/delete-account-section.tsx \
  frontend/src/app/account/account-page-content.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/tests/unit/account-export-route.test.ts frontend/tests/unit/account-delete-route.test.ts \
  frontend/tests/unit/export-section.test.tsx frontend/tests/unit/delete-account-section.test.tsx
git commit -s -m "feat: add data export and account deletion sections to the account page"
```

---

### Task 15: Capstone — full account-lifecycle integration test and regression (`core/`, `accounts/`, `frontend/`)

**Files:**
- Create: `accounts/tests/test_account_lifecycle_e2e.py`
- Test: (this task's own deliverable is the test above)

**Interfaces:**
- Consumes: every endpoint from Tasks 3-8 together. Nothing new is produced —
  this is the plan's final task.

Tasks 3-8 each tested their own endpoint in isolation. None of them proved
the endpoints work correctly **together**, in the order a real user would
actually hit them, against the **same** account — e.g. does an avatar
survive a name update; does the exported data reflect a changed email; does
a revoked session actually lose access; does a deleted account's session
token stop working on every one of the ten new endpoints, not just the ones
that were directly tested against deletion. This task closes that gap and
runs the full three-package regression one final time.

Unlike Tasks 1-14, this test is not expected to fail before being written —
every endpoint it calls already exists and is already individually tested.
Its purpose is integration coverage and regression protection, not driving
new implementation, so there is no red/green step split for it.

- [ ] **Step 1: Write the full-lifecycle integration test**

```python
# accounts/tests/test_account_lifecycle_e2e.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import io
import re


def test_full_account_profile_lifecycle(client, email_sender):
    # 1. Register.
    register = client.post(
        "/v1/accounts/register",
        json={"email": "lifecycle@example.de", "password": "correct horse battery staple"},
    )
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['session_token']}"}

    # 2. Set first/last name.
    profile_update = client.patch(
        "/v1/accounts/profile", json={"first_name": "Jamie", "last_name": "Weber"},
        headers=headers,
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["first_name"] == "Jamie"

    # 3. Upload an avatar -- a minimal valid 1x1 PNG.
    png_1x1 = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082"
    )
    avatar_upload = client.post(
        "/v1/accounts/avatar", files={"avatar": ("avatar.png", io.BytesIO(png_1x1), "image/png")},
        headers=headers,
    )
    assert avatar_upload.status_code == 200
    assert avatar_upload.json()["avatar_data_url"] is not None
    # The avatar upload must not have clobbered the name set in step 2 --
    # profile.py and Task 4's set_avatar both write to the same account row.
    assert avatar_upload.json()["first_name"] == "Jamie"

    # 4. Request and confirm an email change.
    email_change = client.post(
        "/v1/accounts/email/change", json={"new_email": "lifecycle-new@example.de"},
        headers=headers,
    )
    assert email_change.status_code == 200
    # The confirmation link's token isn't observable from this test's HTTP
    # surface (it's only ever emailed) -- extract it from the captured
    # outgoing email, the same way test_email_change.py already does for the
    # equivalent single-endpoint case.
    token = re.search(r"token=([^&\s]+)", email_sender.sent[-1]["body"]).group(1)
    confirm = client.get(
        "/v1/accounts/email/confirm",
        params={"token": token, "email": "lifecycle-new@example.de"},
    )
    assert confirm.status_code == 200

    # 5. Change the password.
    password_change = client.post(
        "/v1/accounts/password",
        json={"current_password": "correct horse battery staple", "new_password": "new secret"},
        headers=headers,
    )
    assert password_change.status_code == 200
    relogin = client.post(
        "/v1/accounts/login", json={"email": "lifecycle-new@example.de", "password": "new secret"}
    )
    assert relogin.status_code == 200

    # 6. List sessions (now two: the original registration session plus the
    # relogin from step 5) and revoke the older one.
    sessions = client.get("/v1/accounts/sessions", headers=headers).json()
    assert len(sessions) == 2
    other_session_id = [s["id"] for s in sessions if not s["is_current"]][0]
    revoke = client.delete(f"/v1/accounts/sessions/{other_session_id}", headers=headers)
    assert revoke.status_code == 200

    # 7. Export -- reflects the changed email, name, and avatar.
    export = client.get("/v1/accounts/export", headers=headers)
    assert export.status_code == 200
    exported_account = export.json()["account"]
    assert exported_account["email"] == "lifecycle-new@example.de"
    assert exported_account["first_name"] == "Jamie"
    assert exported_account["avatar_data_url"] is not None

    # 8. Delete the account (needs the *new* password from step 5).
    delete = client.request(
        "DELETE", "/v1/accounts/me", json={"password": "new secret"}, headers=headers,
    )
    assert delete.status_code == 200

    # 9. Every new endpoint this plan added must now reject the dead session.
    assert client.get("/v1/accounts/session", headers=headers).status_code == 401
    assert client.patch(
        "/v1/accounts/profile", json={"first_name": "x", "last_name": "y"}, headers=headers,
    ).status_code == 401
    assert client.get("/v1/accounts/sessions", headers=headers).status_code == 401
    assert client.get("/v1/accounts/export", headers=headers).status_code == 401
    assert client.post(
        "/v1/accounts/email/change", json={"new_email": "irrelevant@example.de"}, headers=headers,
    ).status_code == 401
    assert client.post(
        "/v1/accounts/password", json={"current_password": None, "new_password": "x"},
        headers=headers,
    ).status_code == 401
```

- [ ] **Step 2: Run the new test**

Run: `cd accounts && .venv/bin/python -m pytest tests/test_account_lifecycle_e2e.py -v`
Expected: PASS (1 test). If it fails, the failure points at a real
integration gap between two of Tasks 3-8 (not a missing feature) — read the
assertion that failed and the two tasks' routers together before changing
anything.

- [ ] **Step 3: Run the full `core/` suite**

Run: `cd core && .venv/bin/python -m pytest -v -W error`
Expected: all pass.

- [ ] **Step 4: Run the full `accounts/` suite**

Run: `cd accounts && .venv/bin/python -m pytest -v`
Expected: all pass, including every test from Tasks 1-8 and the new
lifecycle test.

- [ ] **Step 5: Verify migrations 0018/0019 apply cleanly from a fresh database**

Run: `cd core && .venv/bin/python -m pytest tests/ -k migration -v` if such a
test module exists in this codebase (check `core/tests/` for an existing
migration-head test first — sub-project 1/2 established a testcontainers-based
pattern for this). If no dedicated migration test exists, run instead:

```bash
cd core && .venv/bin/alembic upgrade head
```

against a scratch Postgres (the same testcontainers setup `accounts/tests/conftest.py`
already uses for its own fixtures) and confirm it exits 0 with no errors.

- [ ] **Step 6: Run the full frontend unit suite and production build**

Run: `cd frontend && npm test && npm run build`
Expected: both PASS. Confirm the build's route table lists `/account`,
`/confirm-email-change`, and `/reset-password` all as `ƒ` (Dynamic), and that
no route emits a "should be wrapped in a suspense boundary" error.

- [ ] **Step 7: Write a Playwright end-to-end spec for the account page**

`frontend/playwright.config.ts` already runs its suite against a real
production build (`npm run build && npm run start`) — the same kind of
run that caught both of sub-project 2's production-only bugs (an Edge
Runtime import and a Server/Client Component boundary violation), neither
of which Vitest's jsdom environment could have caught. `frontend/tests/e2e/`
already has three specs following this pattern (`chat-and-history.spec.ts`
registers a real account through the UI and asserts against a real, live
`accounts/` backend) — add a fourth for the account page, in the same style,
rather than relying on manual verification alone.

```typescript
// frontend/tests/e2e/account-management.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

async function registerAndOpenAccountPage(page: import("@playwright/test").Page) {
  const email = `e2e-account-${Date.now()}@example.de`;
  await page.goto("/");
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.getByRole("tab", { name: "Registrieren" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(email);
  await page.getByLabel("Passwort").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();

  await page.goto("/account");
  return email;
}

test.describe("account management", () => {
  test("a user can set their name and it persists across a reload", async ({ page }) => {
    // AppHeader only ever displays the account's email next to the avatar
    // (Task 10) -- first/last name are surfaced nowhere but this form
    // itself, so persistence-after-reload is the correct thing to assert
    // here, not visible text elsewhere on the page.
    await registerAndOpenAccountPage(page);

    await page.getByLabel("Vorname").fill("Jamie");
    await page.getByLabel("Nachname").fill("Weber");
    await page.getByRole("button", { name: "Speichern" }).click();

    await page.reload();
    await expect(page.getByLabel("Vorname")).toHaveValue("Jamie");
  });

  test("a user can upload and then remove an avatar", async ({ page }) => {
    await registerAndOpenAccountPage(page);
    const png1x1 = Buffer.from(
      "89504e470d0a1a0a0000000d49484452000000010000000108020000009077" +
        "53de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082",
      "hex",
    );

    // The file input is a descendant of a <label>Bild hochladen<input .../></label>
    // -- Playwright's getByLabel() resolves this to the <input> itself
    // (wrapping counts as association, same as a for=/id= pair), which is
    // the element setInputFiles() requires; getByText() would instead
    // return the label and fail with "not an HTMLInputElement".
    await page.getByLabel("Bild hochladen").setInputFiles({
      name: "avatar.png", mimeType: "image/png", buffer: png1x1,
    });
    await expect(page.getByRole("img", { name: "Profilbild" }).first()).toBeVisible();

    await page.getByRole("button", { name: "Bild entfernen" }).click();
    await expect(page.getByRole("button", { name: "Bild entfernen" })).not.toBeVisible();
  });

  test("a user can change their password and log in with the new one", async ({ page }) => {
    const email = await registerAndOpenAccountPage(page);

    await page.getByLabel("Neues Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Passwort ändern" }).click();
    await expect(page.getByText("Dein Passwort wurde geändert.")).toBeVisible();

    await page.request.post("/api/auth/logout");
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("the current session is listed and cannot be revoked from itself", async ({ page }) => {
    await registerAndOpenAccountPage(page);

    await expect(page.getByText("Dieses Gerät")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sitzung beenden" })).not.toBeVisible();
  });

  test("a user can download their data export", async ({ page }) => {
    await registerAndOpenAccountPage(page);

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export herunterladen" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("normly-konto-export.json");
  });

  test("deleting the account requires the confirmation email and ends the session", async ({
    page,
  }) => {
    const email = await registerAndOpenAccountPage(page);

    const deleteButton = page.getByRole("button", { name: "Konto endgültig löschen" });
    await expect(deleteButton).toBeDisabled();

    await page.getByLabel("Gib zur Bestätigung deine E-Mail-Adresse ein").fill(email);
    await page.getByLabel("Passwort zur Bestätigung").fill("correct horse battery staple");
    await deleteButton.click();

    // DeleteAccountSection reloads the page on success (Task 14) -- the URL
    // stays "/account", but the reload re-fetches /api/auth/session, which
    // now finds the cookie cleared and renders the logged-out message.
    await expect(page.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeVisible();
  });
});
```

- [ ] **Step 8: Run the new Playwright spec**

Run: `cd frontend && npm run test:e2e -- account-management`
Expected: all 6 tests PASS against a real production build and a real,
running `accounts/` backend (the same stack `playwright.config.ts`'s
`webServer` already brings up for the existing three specs). If a test
fails on something Steps 1-14's own unit tests already covered in isolation,
the failure is pointing at an integration gap between the real browser, the
real production build, and the real backend — not a missing feature; read
the failure before changing any task's code.

- [ ] **Step 9: Commit**

```bash
git add accounts/tests/test_account_lifecycle_e2e.py frontend/tests/e2e/account-management.spec.ts
git commit -s -m "test: add full account-profile-lifecycle integration and e2e coverage"
```

---
