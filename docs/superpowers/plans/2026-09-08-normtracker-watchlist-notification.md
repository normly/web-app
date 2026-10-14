# Watchlist/Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a logged-in account mark a Work as a favorite (heart icon), choose whether to be notified about changes to it (in-app, email, both, or none), and have a new `notify-watchers` CLI job detect new editions, national adoptions, and rights-classification changes and turn them into real notifications the bell icon and inbox actually show.

**Architecture:** All new tables (`watchlist`, `notification`, `account.notification_preference`) live in `core/`'s shared Postgres ORM, exactly like the existing `account`/`account_session` tables. A new `notify-watchers` CLI subcommand (externally triggered — cron/systemd timer — no scheduler in-process) scans every watchlist entry once per run and relies on the `notification` table itself for dedup, so missed or repeated runs are safe. `accounts/` gains new authenticated endpoints on top of the new repositories and already-existing session/email infrastructure. `EmailSender` moves from `accounts/` to `core/` so the CLI job (which lives in `core/` and cannot depend on `accounts/`) can send real mail; `accounts/`'s own routers switch their import path only, with no behavior change. `frontend/` adds a heart toggle, a profile-settings section, and wires the previously-decorative bell popover to real data.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 + Alembic (`core/`), FastAPI + Pydantic (`accounts/`), Next.js App Router + React + vitest (`frontend/`), Postgres 16 (testcontainers in `core/` tests).

## Global Constraints

- No changes to `eur_lex.py`/`baua.py`/`dguv.py` adapters or to `identity.py`/`references.py`/`runner.py` — this plan only adds new tables/endpoints/UI on top of the existing, already-correct ingestion pipeline.
- `accounts/`'s existing email-sending tests (registration, magic-link, password-reset, email-change, email-verification) must stay green after the `EmailSender` import-path change — pure relocation, no behavior change.
- The bell icon's popover structure (`Popover`/`PopoverTrigger`/`PopoverContent` from `@/components/ui/popover`) stays exactly as-is — only its content becomes real data instead of the static `t("nav.noNotifications")` line.
- No retry/queue for failed email sends — fail-soft (`try/except Exception`, `logger.exception(...)`, no re-attempt), matching the existing convention in `magic_link.py`/`password_reset.py` exactly.
- No push notifications (browser or mobile) — in-app popover and email only.
- No digest summarization — every change is its own `Notification` row and its own email.
- No automatic cleanup of old `Notification` rows — left for a later sub-project.
- `Notification` rows are created **only** when `account.notification_preference != NONE`; a `NONE` account produces zero rows for that account (no data clutter for users who opted out).
- If no prior `Notification` row exists for a given `(account_id, work_id, trigger_document_id, trigger_jurisdiction)` rights tuple, that is a **first-time observation, not a change** — do not create a `RIGHTS_CHANGE` notification for it. Only a genuine difference from a previously recorded state produces one.
- Database access only through the repository layer (ADR-006) — no raw SQL or graph queries in CLI/router/pipeline code.
- License headers: `# SPDX-License-Identifier: AGPL-3.0-or-later` / `# Copyright (C) 2026 normly contributors` on every new `core/`/`accounts/` source file (2-line form, matching every existing file read during planning) and `// SPDX-License-Identifier: AGPL-3.0-or-later` / `// Copyright (C) 2026 normly contributors` on every new `frontend/` `.ts`/`.tsx` file (same convention, confirmed present on every existing frontend file touched this sub-project).
- DCO (`Signed-off-by`) + Conventional Commits on every commit; add `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` as a separate trailer, never as the DCO signoff.
- New i18n keys go into **both** `frontend/src/lib/i18n/de.json` and `en.json` — `tests/unit/i18n.test.tsx` fails the whole suite if the two files' key sets ever diverge.
- TDD throughout: write the failing test, run it, confirm the failure reason, then implement.

---

### Task 1: Data model — migration, ORM, and `notification_preference`

**Files:**
- Create: `core/migrations/versions/0027_create_watchlist_and_notification.py`
- Modify: `core/src/normly_core/graph/postgres/orm.py` (add `notification_preference` to `AccountORM`; add `WatchlistORM`, `NotificationORM`)
- Modify: `core/src/normly_core/graph/domain.py` (add `NotificationPreference`, `NotificationTriggerType` enums; add `notification_preference` field to `Account`; add `update_notification_preference` to `AccountRepository` Protocol)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_account_to_domain` maps the new field; `PostgresAccountRepository.update_notification_preference`)
- Test: `core/tests/graph/test_watchlist_and_notification_orm.py` (new file)
- Test: `core/tests/graph/test_account_repository.py` (extend)

**Interfaces:**
- Produces: `normly_core.graph.domain.NotificationPreference` (`str, Enum`: `NONE`, `IN_APP`, `EMAIL`, `BOTH`); `normly_core.graph.domain.NotificationTriggerType` (`str, Enum`: `NEW_EDITION`, `NATIONAL_ADOPTION`, `RIGHTS_CHANGE`); `Account.notification_preference: NotificationPreference`; `AccountRepository.update_notification_preference(account_id: uuid.UUID, *, preference: NotificationPreference) -> None`; ORM tables `watchlist` (`id`, `account_id`, `work_id`, `created_at`, unique on `(account_id, work_id)`) and `notification` (`id`, `account_id`, `work_id`, `trigger_type`, `trigger_edge_id`, `trigger_document_id`, `trigger_jurisdiction`, `may_process`, `may_index_fulltext`, `may_cite_passages`, `may_export_free`, `created_at`, `read_at`, `emailed_at`, unique on `(account_id, work_id, trigger_type, trigger_edge_id)`); `account.notification_preference` column, `NOT NULL DEFAULT 'none'`.
- Consumes: nothing new — only the existing `account`, `work`, `document`, `edge` tables (FK targets) and the existing `_enum_values` helper / enum-column pattern in `orm.py`.

- [ ] **Step 1: Write the failing ORM/migration tests**

```python
# core/tests/graph/test_watchlist_and_notification_orm.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from normly_core.graph.domain import (
    NotificationPreference,
    NotificationTriggerType,
    WorkCreatedVia,
)
from normly_core.graph.postgres.orm import AccountORM, NotificationORM, WatchlistORM
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresWorkRepository,
)


def test_new_account_defaults_to_notification_preference_none(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-default@example.de", password_hash=None
    )
    assert account.notification_preference == NotificationPreference.NONE

    db_session.flush()
    orm = db_session.get(AccountORM, account.id)
    assert orm.notification_preference == NotificationPreference.NONE


def test_watchlist_rejects_a_duplicate_account_work_pair(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-dup@example.de", password_hash=None
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)

    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    db_session.flush()
    db_session.add(WatchlistORM(id=uuid.uuid4(), account_id=account.id, work_id=work.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_notification_orm_round_trip_and_nullable_trigger_columns(db_session):
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-notif@example.de", password_hash=None
    )
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)

    notification = NotificationORM(
        id=uuid.uuid4(),
        account_id=account.id,
        work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None,
        trigger_document_id=None,
        trigger_jurisdiction=None,
        may_process=None,
        may_index_fulltext=None,
        may_cite_passages=None,
        may_export_free=None,
        read_at=None,
        emailed_at=None,
    )
    db_session.add(notification)
    db_session.flush()

    fetched = db_session.get(NotificationORM, notification.id)
    assert fetched is not None
    assert fetched.trigger_type == NotificationTriggerType.NEW_EDITION
    assert fetched.read_at is None
    assert fetched.emailed_at is None
```

```python
# append to core/tests/graph/test_account_repository.py

def test_update_notification_preference(db_session):
    from normly_core.graph.domain import NotificationPreference

    account = PostgresAccountRepository(db_session).create_account(
        email="watcher-pref@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.BOTH
    )
    updated = PostgresAccountRepository(db_session).get_account_by_id(account.id)
    assert updated.notification_preference == NotificationPreference.BOTH
```

(`PostgresAccountRepository` is already imported at the top of `test_account_repository.py` — reuse that import, do not add a second one.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_watchlist_and_notification_orm.py tests/graph/test_account_repository.py::test_update_notification_preference -v`
Expected: FAIL — `ImportError`/`AttributeError` (`NotificationPreference`, `NotificationTriggerType`, `WatchlistORM`, `NotificationORM`, `update_notification_preference` don't exist yet).

- [ ] **Step 3: Add the enums and the `Account.notification_preference` field**

In `core/src/normly_core/graph/domain.py`, add near the other simple `str, Enum` definitions (e.g. right before the `Account` dataclass):

```python
class NotificationPreference(str, Enum):
    NONE = "none"
    IN_APP = "in_app"
    EMAIL = "email"
    BOTH = "both"


class NotificationTriggerType(str, Enum):
    NEW_EDITION = "new_edition"
    NATIONAL_ADOPTION = "national_adoption"
    RIGHTS_CHANGE = "rights_change"
```

Add the field to the existing `Account` dataclass (at the end, after `avatar_content_type`):

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
    notification_preference: NotificationPreference
```

Add the Protocol method to `AccountRepository` (right after `update_profile_names`):

```python
    def update_notification_preference(
        self, account_id: uuid.UUID, *, preference: NotificationPreference
    ) -> None: ...
```

- [ ] **Step 4: Add the ORM column and the two new ORM tables**

In `core/src/normly_core/graph/postgres/orm.py`, add `NotificationPreference` and `NotificationTriggerType` to the existing `from normly_core.graph.domain import (...)` block (alphabetical, matching the existing style).

Add the column to `AccountORM`, right after `avatar_content_type`:

```python
    notification_preference: Mapped[NotificationPreference] = mapped_column(
        sa.Enum(
            NotificationPreference,
            name="notification_preference",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=NotificationPreference.NONE,
        server_default=NotificationPreference.NONE.value,
    )
```

(`server_default` is required here, unlike `WorkStatus`'s plain `default=` on `WorkORM.status`: this column is being added to an *existing*, non-empty `account` table via `ALTER TABLE ... ADD COLUMN`, not created alongside a brand-new table — every already-existing account row needs a value at add-column time, which only a server-side default provides.)

Add the two new ORM classes anywhere after `AccountORM` (e.g. right after `AccountTokenORM`, before the delivery/document classes, keeping the account-family tables grouped):

```python
class WatchlistORM(Base):
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("account_id", "work_id", name="uq_watchlist_account_work"),
    )


class NotificationORM(Base):
    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False
    )
    trigger_type: Mapped[NotificationTriggerType] = mapped_column(
        sa.Enum(
            NotificationTriggerType,
            name="notification_trigger_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        )
    )
    trigger_edge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("edge.id")
    )
    trigger_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("document.id")
    )
    trigger_jurisdiction: Mapped[str | None]
    may_process: Mapped[bool | None]
    may_index_fulltext: Mapped[bool | None]
    may_cite_passages: Mapped[bool | None]
    may_export_free: Mapped[bool | None]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "account_id", "work_id", "trigger_type", "trigger_edge_id",
            name="uq_notification_account_work_trigger_edge",
        ),
    )
```

`trigger_edge_id` is always non-NULL for `NEW_EDITION`/`NATIONAL_ADOPTION` rows, so this plain unique constraint gives real DB-level dedup for those two trigger types (Postgres's default "every NULL is distinct" behavior is irrelevant there). `RIGHTS_CHANGE` rows always have `trigger_edge_id IS NULL`, so this same constraint never blocks them — by design: `RIGHTS_CHANGE` dedup is a value comparison against the latest prior row (Task 6), not an existence check, exactly per the spec's "nutzt eine separate Eindeutigkeits-Prüfung."

- [ ] **Step 5: Write the migration**

```python
# core/migrations/versions/0027_create_watchlist_and_notification.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create watchlist and notification tables, add account.notification_preference

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column(
            "notification_preference",
            sa.Enum(
                "none", "in_app", "email", "both",
                name="notification_preference",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="none",
        ),
    )

    op.create_table(
        "watchlist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "work_id", name="uq_watchlist_account_work"),
    )

    op.create_table(
        "notification",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), nullable=False),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "new_edition", "national_adoption", "rights_change",
                name="notification_trigger_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("trigger_edge_id", UUID(as_uuid=True), sa.ForeignKey("edge.id"), nullable=True),
        sa.Column(
            "trigger_document_id", UUID(as_uuid=True), sa.ForeignKey("document.id"),
            nullable=True,
        ),
        sa.Column("trigger_jurisdiction", sa.String, nullable=True),
        sa.Column("may_process", sa.Boolean, nullable=True),
        sa.Column("may_index_fulltext", sa.Boolean, nullable=True),
        sa.Column("may_cite_passages", sa.Boolean, nullable=True),
        sa.Column("may_export_free", sa.Boolean, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "account_id", "work_id", "trigger_type", "trigger_edge_id",
            name="uq_notification_account_work_trigger_edge",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification")
    op.drop_table("watchlist")
    op.drop_column("account", "notification_preference")
```

- [ ] **Step 6: Add `update_notification_preference` and update `_account_to_domain`**

In `core/src/normly_core/graph/postgres/repositories.py`, update `_account_to_domain` (add the new field to the existing `return Account(...)` call) and add the new method to `PostgresAccountRepository` right after `update_profile_names`:

```python
def _account_to_domain(orm: AccountORM) -> Account:
    return Account(
        id=orm.id, email=orm.email, password_hash=orm.password_hash,
        email_verified_at=orm.email_verified_at, created_at=orm.created_at,
        first_name=orm.first_name, last_name=orm.last_name,
        avatar_image=orm.avatar_image, avatar_content_type=orm.avatar_content_type,
        notification_preference=orm.notification_preference,
    )
```

```python
    def update_notification_preference(
        self, account_id: uuid.UUID, *, preference: NotificationPreference
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(notification_preference=preference)
        )
```

(Add `NotificationPreference` to the existing `from normly_core.graph.domain import (...)` block at the top of `repositories.py`.)

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_watchlist_and_notification_orm.py tests/graph/test_account_repository.py -v`
Expected: PASS.

Also run the pre-existing cross-cutting consistency tests, which must stay green without any further changes (they compare the ORM's declared constraints against the actual migrated schema):

Run: `cd core && .venv/bin/pytest tests/graph/test_orm_migration_consistency.py tests/graph/test_enum_columns.py tests/graph/test_migration_determinism.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/migrations/versions/0027_create_watchlist_and_notification.py \
  core/src/normly_core/graph/domain.py \
  core/src/normly_core/graph/postgres/orm.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_watchlist_and_notification_orm.py \
  core/tests/graph/test_account_repository.py
git commit -s -m "feat(core): add watchlist/notification tables and account.notification_preference"
```

---

### Task 2: Watchlist repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `Watchlist` dataclass, `WatchlistRepository` Protocol)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add `_watchlist_to_domain`, `PostgresWatchlistRepository`)
- Test: `core/tests/graph/test_watchlist_repository.py` (new file)

**Interfaces:**
- Consumes: `WatchlistORM` (Task 1).
- Produces: `normly_core.graph.domain.Watchlist(id, account_id, work_id, created_at)`; `PostgresWatchlistRepository` with `add_watch(*, account_id, work_id) -> Watchlist` (idempotent — a second call with the same pair returns the existing row, never raises), `remove_watch(*, account_id, work_id) -> None` (idempotent — no error if the pair isn't watched), `list_watches_for_account(account_id) -> list[Watchlist]`, `list_all_watches() -> list[Watchlist]` (unscoped — used only by the Task 6 CLI job, which must see every account's watches in one run).

- [ ] **Step 1: Write the failing repository tests**

```python
# core/tests/graph/test_watchlist_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def test_add_watch_creates_a_row(db_session):
    account = _make_account(db_session, "watch-add@example.de")
    work = _make_work(db_session)

    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=work.id
    )
    assert watch.account_id == account.id
    assert watch.work_id == work.id


def test_add_watch_is_idempotent(db_session):
    account = _make_account(db_session, "watch-idempotent@example.de")
    work = _make_work(db_session)
    repo = PostgresWatchlistRepository(db_session)

    first = repo.add_watch(account_id=account.id, work_id=work.id)
    second = repo.add_watch(account_id=account.id, work_id=work.id)
    assert first.id == second.id
    assert len(repo.list_watches_for_account(account.id)) == 1


def test_remove_watch_is_idempotent(db_session):
    account = _make_account(db_session, "watch-remove@example.de")
    work = _make_work(db_session)
    repo = PostgresWatchlistRepository(db_session)

    repo.add_watch(account_id=account.id, work_id=work.id)
    repo.remove_watch(account_id=account.id, work_id=work.id)
    repo.remove_watch(account_id=account.id, work_id=work.id)  # no error on the second call
    assert repo.list_watches_for_account(account.id) == []


def test_list_watches_for_account_only_returns_that_accounts_watches(db_session):
    repo = PostgresWatchlistRepository(db_session)
    account_a = _make_account(db_session, "watch-a@example.de")
    account_b = _make_account(db_session, "watch-b@example.de")
    work = _make_work(db_session)

    repo.add_watch(account_id=account_a.id, work_id=work.id)
    repo.add_watch(account_id=account_b.id, work_id=work.id)

    assert [w.account_id for w in repo.list_watches_for_account(account_a.id)] == [account_a.id]


def test_list_all_watches_returns_every_accounts_watches(db_session):
    repo = PostgresWatchlistRepository(db_session)
    account_a = _make_account(db_session, "watch-all-a@example.de")
    account_b = _make_account(db_session, "watch-all-b@example.de")
    work_1 = _make_work(db_session)
    work_2 = _make_work(db_session)

    repo.add_watch(account_id=account_a.id, work_id=work_1.id)
    repo.add_watch(account_id=account_b.id, work_id=work_2.id)

    pairs = {(w.account_id, w.work_id) for w in repo.list_all_watches()}
    assert pairs == {(account_a.id, work_1.id), (account_b.id, work_2.id)}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_watchlist_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PostgresWatchlistRepository'`.

- [ ] **Step 3: Add the `Watchlist` dataclass and `WatchlistRepository` Protocol**

In `core/src/normly_core/graph/domain.py`, add right after the `Work`/`WorkRepository` block (or any other sensible spot near `Work`, since a Watchlist entry always references one):

```python
@dataclass(frozen=True)
class Watchlist:
    id: uuid.UUID
    account_id: uuid.UUID
    work_id: uuid.UUID
    created_at: datetime


class WatchlistRepository(Protocol):
    def add_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> Watchlist:
        """Idempotent: a second call for the same pair returns the existing row."""
        ...

    def remove_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> None:
        """Idempotent: no error if the pair is not currently watched."""
        ...

    def list_watches_for_account(self, account_id: uuid.UUID) -> list[Watchlist]: ...

    def list_all_watches(self) -> list[Watchlist]:
        """
        Every watch, across every account -- unscoped. The only caller is the
        notify-watchers CLI job (normly_core.notifications.detection), which
        must see every account's watches in a single run. No HTTP endpoint
        may call this.
        """
        ...
```

- [ ] **Step 4: Implement `PostgresWatchlistRepository`**

In `core/src/normly_core/graph/postgres/repositories.py`, add `Watchlist` to the domain import block and `WatchlistORM` to the orm import block, then add (e.g. right after `PostgresWorkRepository`):

```python
def _watchlist_to_domain(orm: WatchlistORM) -> Watchlist:
    return Watchlist(
        id=orm.id, account_id=orm.account_id, work_id=orm.work_id, created_at=orm.created_at,
    )


class PostgresWatchlistRepository:
    def __init__(self, session: Session):
        self._session = session

    def add_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> Watchlist:
        existing = self._existing(account_id, work_id)
        if existing is not None:
            return _watchlist_to_domain(existing)

        orm = WatchlistORM(id=uuid.uuid4(), account_id=account_id, work_id=work_id)
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError:
            existing = self._existing(account_id, work_id)
            if existing is None:
                raise
            return _watchlist_to_domain(existing)
        self._session.refresh(orm)
        return _watchlist_to_domain(orm)

    def remove_watch(self, *, account_id: uuid.UUID, work_id: uuid.UUID) -> None:
        self._session.execute(
            sa.delete(WatchlistORM).where(
                WatchlistORM.account_id == account_id, WatchlistORM.work_id == work_id
            )
        )

    def list_watches_for_account(self, account_id: uuid.UUID) -> list[Watchlist]:
        rows = self._session.execute(
            select(WatchlistORM)
            .where(WatchlistORM.account_id == account_id)
            .order_by(WatchlistORM.created_at, WatchlistORM.id)
        ).scalars()
        return [_watchlist_to_domain(row) for row in rows]

    def list_all_watches(self) -> list[Watchlist]:
        rows = self._session.execute(
            select(WatchlistORM).order_by(WatchlistORM.id)
        ).scalars()
        return [_watchlist_to_domain(row) for row in rows]

    def _existing(self, account_id: uuid.UUID, work_id: uuid.UUID) -> WatchlistORM | None:
        return self._session.execute(
            select(WatchlistORM).where(
                WatchlistORM.account_id == account_id, WatchlistORM.work_id == work_id
            )
        ).scalar_one_or_none()
```

This mirrors `PostgresEdgeRepository.create_edge`'s exact idempotent-insert pattern (check-then-insert, catch `IntegrityError` for the concurrent-race case, re-check once, re-raise only if that second check also comes up empty).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_watchlist_repository.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/domain.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_watchlist_repository.py
git commit -s -m "feat(core): add WatchlistRepository"
```

---

### Task 3: Notification repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `Notification` dataclass, `NotificationRepository` Protocol)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add `_notification_to_domain`, `PostgresNotificationRepository`)
- Test: `core/tests/graph/test_notification_repository.py` (new file)

**Interfaces:**
- Consumes: `NotificationORM` (Task 1); `NotificationTriggerType` (Task 1).
- Produces: `normly_core.graph.domain.Notification(id, account_id, work_id, trigger_type, trigger_edge_id, trigger_document_id, trigger_jurisdiction, may_process, may_index_fulltext, may_cite_passages, may_export_free, created_at, read_at, emailed_at)`; `PostgresNotificationRepository` with:
  - `create(*, account_id, work_id, trigger_type, trigger_edge_id, trigger_document_id, trigger_jurisdiction, may_process, may_index_fulltext, may_cite_passages, may_export_free, emailed_at) -> Notification`
  - `find_by_trigger_edge(*, account_id, work_id, trigger_type, trigger_edge_id) -> Notification | None`
  - `find_latest_rights_notification(*, account_id, work_id, trigger_document_id, trigger_jurisdiction) -> Notification | None`
  - `list_for_account(account_id) -> list[Notification]` (newest first)
  - `mark_read(notification_id, *, account_id, read_at) -> bool` (ownership-scoped: only updates and returns `True` when the row belongs to `account_id`; returns `False` for a missing id or an id owned by a different account — this is the only thing stopping one account from marking another account's notification as read)

- [ ] **Step 1: Write the failing repository tests**

```python
# core/tests/graph/test_notification_repository.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.domain import NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresNotificationRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def test_create_and_find_by_trigger_edge(db_session):
    account = _make_account(db_session, "notif-edge@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)
    edge_id = _make_work(db_session).id  # any uuid; FK not enforced against edge in this test

    created = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge_id, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    found = repo.find_by_trigger_edge(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=edge_id,
    )
    assert found is not None
    assert found.id == created.id
    assert found.read_at is None


def test_find_by_trigger_edge_returns_none_when_absent(db_session):
    account = _make_account(db_session, "notif-absent@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    assert repo.find_by_trigger_edge(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=work.id,
    ) is None


def test_find_latest_rights_notification_picks_the_most_recent(db_session):
    account = _make_account(db_session, "notif-rights@example.de")
    work = _make_work(db_session)
    document_id = _make_work(db_session).id
    repo = PostgresNotificationRepository(db_session)

    older = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=document_id, trigger_jurisdiction="DE",
        may_process=True, may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        emailed_at=None,
    )
    newer = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=document_id, trigger_jurisdiction="DE",
        may_process=False, may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        emailed_at=None,
    )
    assert older.id != newer.id

    latest = repo.find_latest_rights_notification(
        account_id=account.id, work_id=work.id, trigger_document_id=document_id,
        trigger_jurisdiction="DE",
    )
    assert latest.id == newer.id
    assert latest.may_process is False


def test_list_for_account_orders_newest_first(db_session):
    account = _make_account(db_session, "notif-list@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    first = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=_make_work(db_session).id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    second = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=_make_work(db_session).id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    listed = repo.list_for_account(account.id)
    assert [n.id for n in listed] == [second.id, first.id]


def test_mark_read_only_succeeds_for_the_owning_account(db_session):
    owner = _make_account(db_session, "notif-owner@example.de")
    other = _make_account(db_session, "notif-other@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    notification = repo.create(
        account_id=owner.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=_make_work(db_session).id, trigger_document_id=None,
        trigger_jurisdiction=None, may_process=None, may_index_fulltext=None,
        may_cite_passages=None, may_export_free=None, emailed_at=None,
    )
    now = datetime.now(timezone.utc)

    assert repo.mark_read(notification.id, account_id=other.id, read_at=now) is False
    assert repo.mark_read(notification.id, account_id=owner.id, read_at=now) is True
    assert repo.list_for_account(owner.id)[0].read_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_notification_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PostgresNotificationRepository'`.

- [ ] **Step 3: Add the `Notification` dataclass and `NotificationRepository` Protocol**

In `core/src/normly_core/graph/domain.py`, add right after the `Watchlist`/`WatchlistRepository` block from Task 2:

```python
@dataclass(frozen=True)
class Notification:
    id: uuid.UUID
    account_id: uuid.UUID
    work_id: uuid.UUID
    trigger_type: NotificationTriggerType
    trigger_edge_id: uuid.UUID | None
    trigger_document_id: uuid.UUID | None
    trigger_jurisdiction: str | None
    may_process: bool | None
    may_index_fulltext: bool | None
    may_cite_passages: bool | None
    may_export_free: bool | None
    created_at: datetime
    read_at: datetime | None
    emailed_at: datetime | None


class NotificationRepository(Protocol):
    def create(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID | None,
        trigger_document_id: uuid.UUID | None,
        trigger_jurisdiction: str | None,
        may_process: bool | None,
        may_index_fulltext: bool | None,
        may_cite_passages: bool | None,
        may_export_free: bool | None,
        emailed_at: datetime | None,
    ) -> Notification: ...

    def find_by_trigger_edge(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> Notification | None:
        """
        The NEW_EDITION/NATIONAL_ADOPTION dedup check: has this exact edge
        already produced a notification for this account/work? The
        notify-watchers job (Task 6) calls this before creating one.
        """
        ...

    def find_latest_rights_notification(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_document_id: uuid.UUID,
        trigger_jurisdiction: str,
    ) -> Notification | None:
        """
        The most recent RIGHTS_CHANGE notification for this exact tuple, or
        None if there has never been one. The notify-watchers job (Task 6)
        diffs the document's current rights booleans against this row's
        stored booleans -- None means "no prior observation," not "no
        change," and must not itself produce a notification.
        """
        ...

    def list_for_account(self, account_id: uuid.UUID) -> list[Notification]:
        """Newest first -- the shape the in-app feed renders directly."""
        ...

    def mark_read(
        self, notification_id: uuid.UUID, *, account_id: uuid.UUID, read_at: datetime
    ) -> bool:
        """
        Sets read_at only when the row belongs to account_id. Returns True if
        a row was updated, False for a missing id or one owned by a
        different account -- the only thing stopping one account from
        marking another account's notification as read.
        """
        ...
```

- [ ] **Step 4: Implement `PostgresNotificationRepository`**

In `core/src/normly_core/graph/postgres/repositories.py`, add `Notification`, `NotificationTriggerType` to the domain import block and `NotificationORM` to the orm import block, then add (e.g. right after `PostgresWatchlistRepository`):

```python
def _notification_to_domain(orm: NotificationORM) -> Notification:
    return Notification(
        id=orm.id, account_id=orm.account_id, work_id=orm.work_id,
        trigger_type=orm.trigger_type, trigger_edge_id=orm.trigger_edge_id,
        trigger_document_id=orm.trigger_document_id,
        trigger_jurisdiction=orm.trigger_jurisdiction,
        may_process=orm.may_process, may_index_fulltext=orm.may_index_fulltext,
        may_cite_passages=orm.may_cite_passages, may_export_free=orm.may_export_free,
        created_at=orm.created_at, read_at=orm.read_at, emailed_at=orm.emailed_at,
    )


class PostgresNotificationRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID | None,
        trigger_document_id: uuid.UUID | None,
        trigger_jurisdiction: str | None,
        may_process: bool | None,
        may_index_fulltext: bool | None,
        may_cite_passages: bool | None,
        may_export_free: bool | None,
        emailed_at: datetime | None,
    ) -> Notification:
        orm = NotificationORM(
            id=uuid.uuid4(), account_id=account_id, work_id=work_id, trigger_type=trigger_type,
            trigger_edge_id=trigger_edge_id, trigger_document_id=trigger_document_id,
            trigger_jurisdiction=trigger_jurisdiction, may_process=may_process,
            may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
            may_export_free=may_export_free, read_at=None, emailed_at=emailed_at,
        )
        self._session.add(orm)
        self._session.flush()
        self._session.refresh(orm)
        return _notification_to_domain(orm)

    def find_by_trigger_edge(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> Notification | None:
        orm = self._session.execute(
            select(NotificationORM).where(
                NotificationORM.account_id == account_id,
                NotificationORM.work_id == work_id,
                NotificationORM.trigger_type == trigger_type,
                NotificationORM.trigger_edge_id == trigger_edge_id,
            )
        ).scalar_one_or_none()
        return _notification_to_domain(orm) if orm else None

    def find_latest_rights_notification(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_document_id: uuid.UUID,
        trigger_jurisdiction: str,
    ) -> Notification | None:
        orm = self._session.execute(
            select(NotificationORM)
            .where(
                NotificationORM.account_id == account_id,
                NotificationORM.work_id == work_id,
                NotificationORM.trigger_type == NotificationTriggerType.RIGHTS_CHANGE,
                NotificationORM.trigger_document_id == trigger_document_id,
                NotificationORM.trigger_jurisdiction == trigger_jurisdiction,
            )
            .order_by(NotificationORM.created_at.desc(), NotificationORM.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _notification_to_domain(orm) if orm else None

    def list_for_account(self, account_id: uuid.UUID) -> list[Notification]:
        rows = self._session.execute(
            select(NotificationORM)
            .where(NotificationORM.account_id == account_id)
            .order_by(NotificationORM.created_at.desc(), NotificationORM.id.desc())
        ).scalars()
        return [_notification_to_domain(row) for row in rows]

    def mark_read(
        self, notification_id: uuid.UUID, *, account_id: uuid.UUID, read_at: datetime
    ) -> bool:
        result = self._session.execute(
            sa.update(NotificationORM)
            .where(NotificationORM.id == notification_id, NotificationORM.account_id == account_id)
            .values(read_at=read_at)
        )
        return result.rowcount > 0
```

(The `created_at.desc(), id.desc()` tiebreak on both ordered queries mirrors the deterministic-ordering fix already applied to `find_by_designation` in the edition-aware-identity sub-project — a same-transaction tie on `created_at` must not produce a nondeterministic pick.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_notification_repository.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/domain.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_notification_repository.py
git commit -s -m "feat(core): add NotificationRepository"
```

---

### Task 4: Ungated internal listings for notification detection

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (add `created_at` to `Edge`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_edge_to_domain` maps `created_at`; add `list_documents_for_work_unchecked` to `PostgresDocumentRepository`; add `list_incoming_edges_for_work_unchecked` to `PostgresEdgeRepository`; add `list_classifications_for_document_unchecked` to `PostgresRightsRepository`)
- Test: `core/tests/graph/test_document_repository.py` (extend)
- Test: `core/tests/graph/test_edge_repository.py` (extend)
- Test: `core/tests/graph/test_rights_gate.py` (extend)

**Interfaces:**
- Consumes: nothing new — `EdgeORM.created_at` already exists in the database (migration `0007`), it is only missing from the domain dataclass.
- Produces: `Edge.created_at: datetime`; `PostgresDocumentRepository.list_documents_for_work_unchecked(work_id: uuid.UUID) -> list[Document]`; `PostgresEdgeRepository.list_incoming_edges_for_work_unchecked(document_ids: list[uuid.UUID], edge_types: tuple[EdgeType, ...]) -> list[Edge]`; `PostgresRightsRepository.list_classifications_for_document_unchecked(document_id: uuid.UUID) -> list[RightsClassification]`. All three are deliberately **not** part of their repository's Protocol (same convention as `get_document_unchecked`) — internal/administrative reads, never callable from an HTTP endpoint. Task 6's `notify-watchers` CLI job is the only consumer.

- [ ] **Step 1: Write the failing tests**

```python
# append to core/tests/graph/test_document_repository.py

def test_list_documents_for_work_unchecked_returns_every_document_regardless_of_jurisdiction(
    db_session,
):
    source = _make_source(db_session)
    delivery = PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source.id, content_hash="sha256:work-unchecked",
        ingested_at=datetime.now(timezone.utc),
    )
    doc_repo = PostgresDocumentRepository(db_session)
    first = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    second = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id, work_id=first.work_id,
    )
    # No rights_classification row exists for either document -- a gated
    # method would return nothing; the unchecked method must still see both.
    documents = doc_repo.list_documents_for_work_unchecked(first.work_id)
    assert {d.id for d in documents} == {first.id, second.id}
```

(Check the top of `test_document_repository.py` for its existing `_make_source`/import style and match it exactly — every other test in that file already builds a `Source`/`Delivery` this way.)

```python
# append to core/tests/graph/test_edge_repository.py
# (this file already defines _make_two_documents(db_session) -> (old, new,
# delivery) and imports PostgresDeliveryRepository -- reuse both exactly)

def test_edge_created_at_is_exposed_on_the_domain_dataclass(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge = PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    assert edge.created_at is not None


def test_list_incoming_edges_for_work_unchecked_is_bounded_to_the_given_documents(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    replaces_edge = edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    unrelated_old, unrelated_new, unrelated_delivery = _make_two_documents(db_session)
    edge_repo.create_edge(
        from_document_id=unrelated_new.id, to_document_id=unrelated_old.id,
        edge_type=EdgeType.REPLACES, jurisdiction=None, layer=Layer.FREE,
        delivery_id=unrelated_delivery.id,
    )

    found = edge_repo.list_incoming_edges_for_work_unchecked([old.id, new.id], (EdgeType.REPLACES,))
    assert [edge.id for edge in found] == [replaces_edge.id]


def test_list_incoming_edges_for_work_unchecked_filters_by_edge_type(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.WITHDRAWN_BY,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    found = edge_repo.list_incoming_edges_for_work_unchecked([old.id, new.id], (EdgeType.REPLACES,))
    assert found == []


def test_list_incoming_edges_for_work_unchecked_excludes_revoked_edges(db_session):
    old, new, delivery = _make_two_documents(db_session)
    edge_repo = PostgresEdgeRepository(db_session)
    edge_repo.create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )

    PostgresDeliveryRepository(db_session).revoke_delivery(delivery.id)

    found = edge_repo.list_incoming_edges_for_work_unchecked([old.id, new.id], (EdgeType.REPLACES,))
    assert found == []
```

- [ ] **Step 1b: Write the failing rights test**

```python
# append to core/tests/graph/test_rights_gate.py
# (this file already defines _make_document(db_session, content_hash=...) ->
# (document, delivery) -- reuse it exactly)

def test_list_classifications_for_document_unchecked_returns_every_jurisdiction(db_session):
    document, delivery = _make_document(db_session)
    rights_repo = PostgresRightsRepository(db_session)
    rights_repo.classify(
        document_id=document.id, jurisdiction="DE", may_process=True, may_index_fulltext=True,
        may_cite_passages=True, may_export_free=True, legal_basis_reference="§ 5 UrhG",
        classified_at=datetime.now(timezone.utc), classified_by="pipeline",
        delivery_id=delivery.id,
    )
    rights_repo.classify(
        document_id=document.id, jurisdiction="AT", may_process=False, may_index_fulltext=False,
        may_cite_passages=False, may_export_free=False, legal_basis_reference="n/a",
        classified_at=datetime.now(timezone.utc), classified_by="pipeline",
        delivery_id=delivery.id,
    )

    classifications = rights_repo.list_classifications_for_document_unchecked(document.id)
    assert {c.jurisdiction for c in classifications} == {"DE", "AT"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_repository.py tests/graph/test_edge_repository.py tests/graph/test_rights_gate.py -v -k "unchecked or created_at"`
Expected: FAIL — `AttributeError` (methods/field don't exist yet).

- [ ] **Step 3: Add `Edge.created_at`**

In `core/src/normly_core/graph/domain.py`, add the field to the existing `Edge` dataclass (at the end, after `revoked_at`):

```python
@dataclass(frozen=True)
class Edge:
    id: uuid.UUID
    from_document_id: uuid.UUID
    to_document_id: uuid.UUID
    edge_type: EdgeType
    jurisdiction: str | None
    layer: Layer
    delivery_id: uuid.UUID
    revoked_at: datetime | None
    created_at: datetime
```

- [ ] **Step 4: Update `_edge_to_domain` and add the three ungated methods**

In `core/src/normly_core/graph/postgres/repositories.py`:

```python
def _edge_to_domain(orm: EdgeORM) -> Edge:
    return Edge(
        id=orm.id,
        from_document_id=orm.from_document_id,
        to_document_id=orm.to_document_id,
        edge_type=orm.edge_type,
        jurisdiction=orm.jurisdiction,
        layer=orm.layer,
        delivery_id=orm.delivery_id,
        revoked_at=orm.revoked_at,
        created_at=orm.created_at,
    )
```

Add to `PostgresDocumentRepository` (e.g. right after `get_document_unchecked`), and update that method's class-level docstring list of ungated methods to also name this one:

```python
    def list_documents_for_work_unchecked(self, work_id: uuid.UUID) -> list[Document]:
        """
        Every Document belonging to `work_id`, regardless of rights
        classification or jurisdiction. Internal/administrative use only
        (notify-watchers, Task 6) -- never callable from an HTTP endpoint.
        """
        rows = self._session.execute(
            select(DocumentORM).where(DocumentORM.work_id == work_id)
        ).scalars()
        return [_document_to_domain(row) for row in rows]
```

Add to `PostgresEdgeRepository` (e.g. right after `list_incoming_edges_for_jurisdiction`):

```python
    def list_incoming_edges_for_work_unchecked(
        self, document_ids: list[uuid.UUID], edge_types: tuple[EdgeType, ...]
    ) -> list[Edge]:
        """
        Incoming, unrevoked edges of the given types whose to_document_id is
        one of `document_ids` -- bounded to one Work's own documents, no
        rights-gating and no layer filter. Internal/administrative use only
        (notify-watchers, Task 6) -- never callable from an HTTP endpoint;
        every public read path keeps using the *_for_jurisdiction methods
        above.
        """
        if not document_ids:
            return []
        rows = self._session.execute(
            select(EdgeORM)
            .where(
                EdgeORM.to_document_id.in_(document_ids),
                EdgeORM.edge_type.in_(edge_types),
                EdgeORM.revoked_at.is_(None),
            )
            .order_by(EdgeORM.id)
        ).scalars()
        return [_edge_to_domain(row) for row in rows]
```

Add to `PostgresRightsRepository` (e.g. right after `get_classification`):

```python
    def list_classifications_for_document_unchecked(
        self, document_id: uuid.UUID
    ) -> list[RightsClassification]:
        """
        Every classification row for `document_id`, one per jurisdiction ever
        classified, regardless of revoked_at. Internal/administrative use
        only (notify-watchers, Task 6) -- never callable from an HTTP
        endpoint.
        """
        rows = self._session.execute(
            select(RightsClassificationORM).where(
                RightsClassificationORM.document_id == document_id
            )
        ).scalars()
        return [_rights_to_domain(row) for row in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_document_repository.py tests/graph/test_edge_repository.py tests/graph/test_rights_gate.py -v`
Expected: PASS — including every pre-existing test in these three files (the `Edge.created_at` field addition is additive, but run the whole files, not just the new tests, to catch any place still constructing an `Edge(...)` positionally without it).

Run the full core suite once here too, since `Edge.created_at` is a dataclass shape change that could break a construction site this plan's grounding didn't find:

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS (340+ tests).

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/graph/domain.py \
  core/src/normly_core/graph/postgres/repositories.py \
  core/tests/graph/test_document_repository.py \
  core/tests/graph/test_edge_repository.py \
  core/tests/graph/test_rights_gate.py
git commit -s -m "feat(core): expose Edge.created_at and add ungated work-scoped listings"
```

---

### Task 5: Move `EmailSender` from `accounts/` to `core/`

**Files:**
- Create: `core/src/normly_core/notifications/__init__.py`
- Create: `core/src/normly_core/notifications/email.py`
- Delete: `accounts/src/normly_accounts/email.py`
- Modify: `accounts/src/normly_accounts/main.py`
- Modify: `accounts/src/normly_accounts/routers/registration.py`
- Modify: `accounts/src/normly_accounts/routers/magic_link.py`
- Modify: `accounts/src/normly_accounts/routers/password_reset.py`
- Modify: `accounts/src/normly_accounts/routers/email_change.py`
- Modify: `accounts/src/normly_accounts/routers/email_verification.py`
- Modify: `accounts/tests/conftest.py`
- Test: `core/tests/pipeline/test_email.py` (new file — the `SmtpEmailSender`/`RecordingEmailSender` tests, moved verbatim in spirit from wherever `accounts/` tested them before, since this is pure relocation)

**Interfaces:**
- Produces: `normly_core.notifications.email.EmailSender` (Protocol), `SmtpEmailSender`, `RecordingEmailSender` — byte-for-byte the same classes, new import path only. Task 6's CLI job imports from here.
- Consumes: nothing new.

- [ ] **Step 1: Check for pre-existing email tests to move**

Run: `grep -rl "SmtpEmailSender\|RecordingEmailSender" accounts/tests/`

If any test file asserts behavior of `SmtpEmailSender`/`RecordingEmailSender` themselves (not just using `RecordingEmailSender` as a test double for an unrelated endpoint test), write the equivalent test(s) in the new `core/tests/pipeline/test_email.py` first, then delete them from wherever they lived in `accounts/tests/`. If no such dedicated test exists (i.e. `RecordingEmailSender` is only ever used as a fixture, never tested on its own), write a minimal one from scratch:

```python
# core/tests/pipeline/test_email.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.notifications.email import RecordingEmailSender


def test_recording_email_sender_records_every_call():
    sender = RecordingEmailSender()
    sender.send(to="a@example.de", subject="Test", body="Body")
    assert sender.sent == [{"to": "a@example.de", "subject": "Test", "body": "Body"}]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_email.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_core.notifications'`.

- [ ] **Step 3: Move the file**

```bash
mkdir -p core/src/normly_core/notifications
git mv accounts/src/normly_accounts/email.py core/src/normly_core/notifications/email.py
```

Update the header comment inside the moved file from `# accounts/src/normly_accounts/email.py` to `# core/src/normly_core/notifications/email.py` (first line); the rest of the file's content (the `EmailSender` Protocol, `SmtpEmailSender`, `RecordingEmailSender` classes, `_SMTP_TIMEOUT_SECONDS`) is unchanged.

Create `core/src/normly_core/notifications/__init__.py`:

```python
# core/src/normly_core/notifications/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

- [ ] **Step 4: Update every `accounts/` import site**

In each of these five router files, change:
```python
from normly_accounts.email import EmailSender
```
to:
```python
from normly_core.notifications.email import EmailSender
```
— `registration.py`, `magic_link.py`, `password_reset.py`, `email_change.py`, `email_verification.py`. (Confirm each file's exact current import line with `grep -n "from normly_accounts.email import" accounts/src/normly_accounts/routers/*.py` before editing — this plan's grounding found exactly these five importing `EmailSender` only, but re-verify before touching each file.)

In `accounts/src/normly_accounts/main.py`, change:
```python
from normly_accounts.email import RecordingEmailSender, SmtpEmailSender
```
to:
```python
from normly_core.notifications.email import RecordingEmailSender, SmtpEmailSender
```

In `accounts/tests/conftest.py`, change:
```python
from normly_accounts.email import RecordingEmailSender
```
to:
```python
from normly_core.notifications.email import RecordingEmailSender
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_email.py -v`
Expected: PASS.

Run the entire `accounts/` suite — this is the "prove no behavior change" check the Global Constraints require:

Run: `cd accounts && .venv/bin/pytest -v`
Expected: PASS (98+ tests, same count as the pre-task baseline — if the count differs, something beyond an import path changed and must be investigated before continuing).

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/notifications/ \
  core/tests/pipeline/test_email.py \
  accounts/src/normly_accounts/email.py \
  accounts/src/normly_accounts/main.py \
  accounts/src/normly_accounts/routers/registration.py \
  accounts/src/normly_accounts/routers/magic_link.py \
  accounts/src/normly_accounts/routers/password_reset.py \
  accounts/src/normly_accounts/routers/email_change.py \
  accounts/src/normly_accounts/routers/email_verification.py \
  accounts/tests/conftest.py
git commit -s -m "refactor(core,accounts): move EmailSender to core/ so notify-watchers can send mail"
```

---

### Task 6: `notify-watchers` CLI job

**Files:**
- Create: `core/src/normly_core/notifications/detection.py`
- Modify: `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/notifications/__init__.py` (new)
- Test: `core/tests/notifications/test_detection.py` (new)
- Test: `core/tests/pipeline/test_cli.py` (extend)

**Interfaces:**
- Consumes: `PostgresWatchlistRepository` (Task 2), `PostgresNotificationRepository` (Task 3), `PostgresDocumentRepository.list_documents_for_work_unchecked` / `PostgresEdgeRepository.list_incoming_edges_for_work_unchecked` / `PostgresRightsRepository.list_classifications_for_document_unchecked` (Task 4), `normly_core.notifications.email.EmailSender` (Task 5), `Account.notification_preference` (Task 1).
- Produces: `normly_core.notifications.detection.run_notify_watchers(session: Session, email_sender: EmailSender) -> NotifyWatchersSummary` (`NotifyWatchersSummary(watches_scanned: int, notifications_created: int, emails_sent: int)`); a new `notify-watchers` subcommand on the existing CLI (`python -m normly_core.pipeline notify-watchers`).

- [ ] **Step 1: Write the failing detection tests**

```python
# core/tests/notifications/__init__.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
```

```python
# core/tests/notifications/test_detection.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationPreference,
    NotificationTriggerType,
    TdmOptOutResult,
    WorkCreatedVia,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresRightsRepository,
    PostgresSourceRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import RecordingEmailSender


def _make_source(db_session):
    return PostgresSourceRepository(db_session).create_source(
        publisher="DGUV", retrieval_path="https://publikationen.dguv.de",
        legal_basis_category=LegalBasisCategory.A, jurisdiction="DE",
        reviewed_at=datetime(2026, 1, 1).date(), responsible_person="Test Reviewer",
    )


def _make_delivery(db_session, source_id, tag):
    return PostgresDeliveryRepository(db_session).record_delivery(
        source_id=source_id, content_hash=f"sha256:{tag}", ingested_at=datetime.now(timezone.utc),
    )


def _classify(db_session, document_id, delivery_id, *, jurisdiction="DE", may_process=True):
    return PostgresRightsRepository(db_session).classify(
        document_id=document_id, jurisdiction=jurisdiction, may_process=may_process,
        may_index_fulltext=True, may_cite_passages=True, may_export_free=False,
        legal_basis_reference="§5 UrhG", classified_at=datetime.now(timezone.utc),
        classified_by="pipeline", delivery_id=delivery_id,
    )


def test_new_edition_edge_produces_one_notification_and_no_duplicate_on_a_second_run(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "new-edition")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="1", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=old.work_id)
    db_session.flush()

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1
    assert first_run.emails_sent == 0  # preference is IN_APP, not EMAIL/BOTH
    assert sender.sent == []

    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert len(notifications) == 1
    assert notifications[0].trigger_type == NotificationTriggerType.NEW_EDITION

    second_run = run_notify_watchers(db_session, sender)
    assert second_run.notifications_created == 0
    assert len(PostgresNotificationRepository(db_session).list_for_account(account.id)) == 1


def test_national_adoption_edge_produces_one_notification_and_no_duplicate_on_a_second_run(
    db_session,
):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "national-adoption")
    doc_repo = PostgresDocumentRepository(db_session)
    original = doc_repo.create_document(
        origin_issuer="DIN", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id,
    )
    adoption = doc_repo.create_document(
        origin_issuer="BS", origin_number="EN ISO 9001", edition="2015", part=None,
        delivery_id=delivery.id, work_id=original.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=adoption.id, to_document_id=original.id,
        edge_type=EdgeType.ADOPTED_FROM, jurisdiction=None, layer=Layer.FREE,
        delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="adoption-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=original.work_id
    )
    db_session.flush()

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1

    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert notifications[0].trigger_type == NotificationTriggerType.NATIONAL_ADOPTION

    second_run = run_notify_watchers(db_session, sender)
    assert second_run.notifications_created == 0


def test_email_preference_sends_mail_and_sets_emailed_at(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "email-pref")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="2", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="email-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.BOTH
    )
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=old.work_id)
    db_session.flush()

    sender = RecordingEmailSender()
    run_notify_watchers(db_session, sender)

    assert len(sender.sent) == 1
    assert sender.sent[0]["to"] == "email-watcher@example.de"
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert notifications[0].emailed_at is not None


def test_notification_preference_none_creates_no_notification(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "pref-none")
    doc_repo = PostgresDocumentRepository(db_session)
    old = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="3", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    new = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="3", edition="2026", part=None,
        delivery_id=delivery.id, work_id=old.work_id,
    )
    PostgresEdgeRepository(db_session).create_edge(
        from_document_id=new.id, to_document_id=old.id, edge_type=EdgeType.REPLACES,
        jurisdiction=None, layer=Layer.FREE, delivery_id=delivery.id,
    )
    account = PostgresAccountRepository(db_session).create_account(
        email="pref-none@example.de", password_hash=None
    )
    # Default preference is NONE -- no update_notification_preference call.
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=old.work_id)
    db_session.flush()

    run_notify_watchers(db_session, RecordingEmailSender())
    assert PostgresNotificationRepository(db_session).list_for_account(account.id) == []


def test_rights_change_is_not_flagged_on_first_observation_but_is_on_a_real_change(db_session):
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "rights-change")
    doc_repo = PostgresDocumentRepository(db_session)
    document = doc_repo.create_document(
        origin_issuer="DGUV", origin_number="4", edition="2020", part=None,
        delivery_id=delivery.id,
    )
    _classify(db_session, document.id, delivery.id, may_process=True)
    account = PostgresAccountRepository(db_session).create_account(
        email="rights-watcher@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=document.work_id)
    db_session.flush()

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 0  # first observation, nothing to compare against

    # Re-classify with unchanged values -- a re-ingestion with the same
    # rights must NOT produce a notification (classified_at always moves,
    # the boolean fields don't).
    _classify(db_session, document.id, delivery.id, may_process=True)
    unchanged_run = run_notify_watchers(db_session, sender)
    assert unchanged_run.notifications_created == 0

    # A genuine change must produce exactly one notification.
    _classify(db_session, document.id, delivery.id, may_process=False)
    changed_run = run_notify_watchers(db_session, sender)
    assert changed_run.notifications_created == 1
    notifications = PostgresNotificationRepository(db_session).list_for_account(account.id)
    assert notifications[0].trigger_type == NotificationTriggerType.RIGHTS_CHANGE
    assert notifications[0].may_process is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/notifications/test_detection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normly_core.notifications.detection'`.

- [ ] **Step 3: Implement `detection.py`**

```python
# core/src/normly_core/notifications/detection.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from normly_core.graph.domain import (
    Account,
    EdgeType,
    NotificationPreference,
    NotificationTriggerType,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresRightsRepository,
    PostgresWatchlistRepository,
)
from normly_core.notifications.email import EmailSender

logger = logging.getLogger(__name__)

_NEW_EDITION_EDGE_TYPES = (EdgeType.REPLACES, EdgeType.WITHDRAWN_BY)
_NATIONAL_ADOPTION_EDGE_TYPES = (EdgeType.ADOPTED_FROM,)

_EMAIL_SUBJECTS = {
    NotificationTriggerType.NEW_EDITION: "Neue Ausgabe eines beobachteten Regelwerks",
    NotificationTriggerType.NATIONAL_ADOPTION: "Neue nationale Fassung eines beobachteten Regelwerks",
    NotificationTriggerType.RIGHTS_CHANGE: "Rechteänderung an einem beobachteten Regelwerk",
}


@dataclass(frozen=True)
class NotifyWatchersSummary:
    watches_scanned: int
    notifications_created: int
    emails_sent: int


def run_notify_watchers(session: Session, email_sender: EmailSender) -> NotifyWatchersSummary:
    watchlist_repo = PostgresWatchlistRepository(session)
    notification_repo = PostgresNotificationRepository(session)
    account_repo = PostgresAccountRepository(session)
    document_repo = PostgresDocumentRepository(session)
    edge_repo = PostgresEdgeRepository(session)
    rights_repo = PostgresRightsRepository(session)

    watches = watchlist_repo.list_all_watches()
    notifications_created = 0
    emails_sent = 0

    for watch in watches:
        account = account_repo.get_account_by_id(watch.account_id)
        if account is None or account.notification_preference == NotificationPreference.NONE:
            continue

        documents = document_repo.list_documents_for_work_unchecked(watch.work_id)
        document_ids = [document.id for document in documents]

        for edge_types, trigger_type in (
            (_NEW_EDITION_EDGE_TYPES, NotificationTriggerType.NEW_EDITION),
            (_NATIONAL_ADOPTION_EDGE_TYPES, NotificationTriggerType.NATIONAL_ADOPTION),
        ):
            for edge in edge_repo.list_incoming_edges_for_work_unchecked(document_ids, edge_types):
                if notification_repo.find_by_trigger_edge(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                ) is not None:
                    continue
                notification = _create_and_maybe_email(
                    notification_repo, email_sender, account=account, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                    trigger_document_id=None, trigger_jurisdiction=None,
                    may_process=None, may_index_fulltext=None,
                    may_cite_passages=None, may_export_free=None,
                )
                notifications_created += 1
                if notification.emailed_at is not None:
                    emails_sent += 1

        for document_id in document_ids:
            for classification in rights_repo.list_classifications_for_document_unchecked(
                document_id
            ):
                previous = notification_repo.find_latest_rights_notification(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_document_id=document_id,
                    trigger_jurisdiction=classification.jurisdiction,
                )
                if previous is None:
                    # First-time observation, not a change -- nothing to
                    # compare against yet (see Global Constraints).
                    continue
                if (
                    previous.may_process == classification.may_process
                    and previous.may_index_fulltext == classification.may_index_fulltext
                    and previous.may_cite_passages == classification.may_cite_passages
                    and previous.may_export_free == classification.may_export_free
                ):
                    continue
                notification = _create_and_maybe_email(
                    notification_repo, email_sender, account=account, work_id=watch.work_id,
                    trigger_type=NotificationTriggerType.RIGHTS_CHANGE, trigger_edge_id=None,
                    trigger_document_id=document_id,
                    trigger_jurisdiction=classification.jurisdiction,
                    may_process=classification.may_process,
                    may_index_fulltext=classification.may_index_fulltext,
                    may_cite_passages=classification.may_cite_passages,
                    may_export_free=classification.may_export_free,
                )
                notifications_created += 1
                if notification.emailed_at is not None:
                    emails_sent += 1

    return NotifyWatchersSummary(
        watches_scanned=len(watches), notifications_created=notifications_created,
        emails_sent=emails_sent,
    )


def _create_and_maybe_email(
    notification_repo: PostgresNotificationRepository,
    email_sender: EmailSender,
    *,
    account: Account,
    work_id,
    trigger_type: NotificationTriggerType,
    trigger_edge_id,
    trigger_document_id,
    trigger_jurisdiction: str | None,
    may_process: bool | None,
    may_index_fulltext: bool | None,
    may_cite_passages: bool | None,
    may_export_free: bool | None,
):
    emailed_at = None
    if account.notification_preference in (
        NotificationPreference.EMAIL, NotificationPreference.BOTH,
    ):
        try:
            email_sender.send(
                to=account.email, subject=_EMAIL_SUBJECTS[trigger_type],
                body=(
                    f"Ein von dir beobachtetes Regelwerk hat eine Änderung erfahren "
                    f"({trigger_type.value}). Melde dich bei normly an, um die Details zu sehen."
                ),
            )
            emailed_at = datetime.now(timezone.utc)
        except Exception:
            # Fail-soft, best-effort, no retry -- see Global Constraints.
            logger.exception("notify-watchers email delivery failed for %s", account.email)

    return notification_repo.create(
        account_id=account.id, work_id=work_id, trigger_type=trigger_type,
        trigger_edge_id=trigger_edge_id, trigger_document_id=trigger_document_id,
        trigger_jurisdiction=trigger_jurisdiction, may_process=may_process,
        may_index_fulltext=may_index_fulltext, may_cite_passages=may_cite_passages,
        may_export_free=may_export_free, emailed_at=emailed_at,
    )
```

`_create_and_maybe_email` returns the created `Notification` (rather than `None`) specifically so `run_notify_watchers` can check `.emailed_at` right after each call and increment `emails_sent` inline, without a second pass over the data.

- [ ] **Step 4: Wire the CLI subcommand**

In `core/src/normly_core/pipeline/cli.py`, add the import and subcommand registration:

```python
from normly_core.notifications.detection import run_notify_watchers
from normly_core.notifications.email import RecordingEmailSender, SmtpEmailSender
```

```python
    subparsers.add_parser("notify-watchers")
```

(right after the existing `subparsers.add_parser("backfill-document-embeddings")` line)

```python
            elif args.command == "notify-watchers":
                smtp_host = os.environ.get("NORMLY_SMTP_HOST")
                if smtp_host:
                    email_sender = SmtpEmailSender(
                        host=smtp_host,
                        port=int(os.environ.get("NORMLY_SMTP_PORT", "587")),
                        from_address=os.environ.get(
                            "NORMLY_SMTP_FROM", "no-reply@normly.example"
                        ),
                        username=os.environ.get("NORMLY_SMTP_USERNAME"),
                        password=os.environ.get("NORMLY_SMTP_PASSWORD"),
                    )
                else:
                    email_sender = RecordingEmailSender()
                summary = run_notify_watchers(session, email_sender)
                session.commit()
                print(
                    f"watches_scanned={summary.watches_scanned} "
                    f"notifications_created={summary.notifications_created} "
                    f"emails_sent={summary.emails_sent}"
                )
```

(as a new `elif` branch, in the same `if/elif` chain as `ingest`/`backfill-document-embeddings`, inside the existing `with Session(engine) as session:` block)

- [ ] **Step 5: Extend `test_cli.py`**

```python
# append to core/tests/pipeline/test_cli.py

def test_main_notify_watchers_subcommand_runs_without_smtp_configured(committed_db, capsys):
    exit_code = main(["notify-watchers"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "watches_scanned=" in captured.out
```

(`committed_db` is this file's existing fixture that points `NORMLY_DATABASE_URL` at the real test database and truncates afterwards — reuse it exactly as the other `main([...])` tests in this file do; if `_WRITTEN_TABLES` in this file doesn't already include `watchlist`/`notification`/`account`, add them so the truncate cleans up after this test too.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/notifications/test_detection.py tests/pipeline/test_cli.py -v`
Expected: PASS.

Run the full core suite:

Run: `cd core && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/notifications/detection.py \
  core/src/normly_core/pipeline/cli.py \
  core/tests/notifications/ \
  core/tests/pipeline/test_cli.py
git commit -s -m "feat(core): add the notify-watchers CLI job"
```

---

### Task 7: `accounts/` watchlist endpoints

**Files:**
- Create: `accounts/src/normly_accounts/routers/watchlist.py`
- Modify: `accounts/src/normly_accounts/schemas.py`
- Modify: `accounts/src/normly_accounts/main.py`
- Test: `accounts/tests/test_watchlist.py` (new file)

**Interfaces:**
- Consumes: `PostgresWatchlistRepository` (Task 2); `get_current_account`, `get_session` (existing `accounts/src/normly_accounts/dependencies.py`, unchanged).
- Produces: `POST /v1/accounts/watchlist` (body `{work_id}`, returns `WatchlistEntryResponse`), `DELETE /v1/accounts/watchlist/{work_id}` (returns `{"status": "removed"}`, always 200 whether or not it was watched — idempotent, matching `remove_watch`), `GET /v1/accounts/watchlist` (returns `list[WatchlistEntryResponse]`).

- [ ] **Step 1: Write the failing endpoint tests**

```python
# accounts/tests/test_watchlist.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import WorkCreatedVia
from normly_core.graph.postgres.repositories import PostgresWorkRepository


def _register_and_authorize(client, email="watchlist@example.de"):
    response = client.post("/v1/accounts/register", json={"email": email, "password": "correct horse"})
    body = response.json()
    return body["session_token"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_work(db_session):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    db_session.commit()
    return work


def test_add_to_watchlist(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)

    response = client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    assert response.status_code == 200
    assert response.json()["work_id"] == str(work.id)


def test_add_to_watchlist_is_idempotent(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)

    client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    response = client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)
    assert response.status_code == 200

    listing = client.get("/v1/accounts/watchlist", headers=headers)
    assert len(listing.json()) == 1


def test_remove_from_watchlist(client, db_session):
    _, headers = _register_and_authorize(client)
    work = _make_work(db_session)
    client.post("/v1/accounts/watchlist", json={"work_id": str(work.id)}, headers=headers)

    response = client.delete(f"/v1/accounts/watchlist/{work.id}", headers=headers)
    assert response.status_code == 200

    listing = client.get("/v1/accounts/watchlist", headers=headers)
    assert listing.json() == []


def test_remove_from_watchlist_when_not_watched_does_not_error(client):
    _, headers = _register_and_authorize(client)
    response = client.delete(f"/v1/accounts/watchlist/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 200


def test_watchlist_endpoints_require_authentication(client):
    response = client.get("/v1/accounts/watchlist")
    assert response.status_code == 401
```

(This mirrors `test_profile.py`'s exact `_register_and_authorize(client)` local-helper pattern — this codebase has no shared `auth_headers` fixture; every test file that needs an authenticated client defines this same small helper for itself.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd accounts && .venv/bin/pytest tests/test_watchlist.py -v`
Expected: FAIL — `404 Not Found` (router doesn't exist yet).

- [ ] **Step 3: Add the schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class AddWatchlistEntryRequest(BaseModel):
    work_id: uuid.UUID


class WatchlistEntryResponse(BaseModel):
    work_id: uuid.UUID
    created_at: datetime
```

(Add `datetime` to this file's existing imports if not already imported.)

- [ ] **Step 4: Implement the router**

```python
# accounts/src/normly_accounts/routers/watchlist.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresWatchlistRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import AddWatchlistEntryRequest, WatchlistEntryResponse

watchlist_router = APIRouter(prefix="/v1/accounts", tags=["watchlist"])


@watchlist_router.post("/watchlist", response_model=WatchlistEntryResponse)
def add_watch(
    payload: AddWatchlistEntryRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> WatchlistEntryResponse:
    watch = PostgresWatchlistRepository(session).add_watch(
        account_id=account.id, work_id=payload.work_id
    )
    return WatchlistEntryResponse(work_id=watch.work_id, created_at=watch.created_at)


@watchlist_router.delete("/watchlist/{work_id}")
def remove_watch(
    work_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> dict:
    PostgresWatchlistRepository(session).remove_watch(account_id=account.id, work_id=work_id)
    return {"status": "removed"}


@watchlist_router.get("/watchlist", response_model=list[WatchlistEntryResponse])
def list_watches(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[WatchlistEntryResponse]:
    watches = PostgresWatchlistRepository(session).list_watches_for_account(account.id)
    return [WatchlistEntryResponse(work_id=w.work_id, created_at=w.created_at) for w in watches]
```

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`, add the import (alphabetical, with the other router imports) and registration line:

```python
from normly_accounts.routers.watchlist import watchlist_router
```

```python
    app.include_router(watchlist_router, responses=COMMON_ERROR_RESPONSES)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd accounts && .venv/bin/pytest tests/test_watchlist.py -v`
Expected: PASS.

Run: `cd accounts && .venv/bin/pytest -v`
Expected: PASS (existing count + new tests).

- [ ] **Step 7: Commit**

```bash
git add accounts/src/normly_accounts/routers/watchlist.py \
  accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py \
  accounts/tests/test_watchlist.py
git commit -s -m "feat(accounts): add watchlist endpoints"
```

---

### Task 8: `accounts/` notification endpoints

**Files:**
- Create: `accounts/src/normly_accounts/routers/notifications.py`
- Modify: `accounts/src/normly_accounts/schemas.py`
- Modify: `accounts/src/normly_accounts/main.py`
- Test: `accounts/tests/test_notifications.py` (new file)

**Interfaces:**
- Consumes: `PostgresNotificationRepository` (Task 3); `get_current_account`, `get_session` (existing).
- Produces: `GET /v1/accounts/notifications` (returns `list[NotificationResponse]`, newest first), `PATCH /v1/accounts/notifications/{id}` (marks read, returns `NotificationResponse`; 404 if the id doesn't exist or belongs to a different account).

- [ ] **Step 1: Write the failing endpoint tests**

```python
# accounts/tests/test_notifications.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

from normly_core.graph.domain import NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresNotificationRepository,
    PostgresWorkRepository,
)


def _register_and_authorize(client, email="notifications@example.de"):
    response = client.post("/v1/accounts/register", json={"email": email, "password": "correct horse"})
    body = response.json()
    return body["account"]["id"], {"Authorization": f"Bearer {body['session_token']}"}


def _make_notification(db_session, account_id):
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    notification = PostgresNotificationRepository(db_session).create(
        account_id=account_id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=uuid.uuid4(), trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.commit()
    return notification


def test_list_notifications(client, db_session):
    account_id, headers = _register_and_authorize(client)
    _make_notification(db_session, account_id)

    response = client.get("/v1/accounts/notifications", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["read_at"] is None


def test_mark_notification_read(client, db_session):
    account_id, headers = _register_and_authorize(client)
    notification = _make_notification(db_session, account_id)

    response = client.patch(f"/v1/accounts/notifications/{notification.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_mark_notification_read_for_a_missing_id_returns_404(client):
    _, headers = _register_and_authorize(client)
    response = client.patch(f"/v1/accounts/notifications/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_notification_endpoints_require_authentication(client):
    response = client.get("/v1/accounts/notifications")
    assert response.status_code == 401
```

(Same local `_register_and_authorize` helper pattern as `test_profile.py`/Task 7, extended to also return the new account's own `id` from the registration response body — `SessionResponse.account.id` — since this file needs it to create a notification that belongs to the authenticated test account.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd accounts && .venv/bin/pytest tests/test_notifications.py -v`
Expected: FAIL — `404 Not Found` (router doesn't exist yet).

- [ ] **Step 3: Add the schema**

In `accounts/src/normly_accounts/schemas.py`, add:

```python
class NotificationResponse(BaseModel):
    id: uuid.UUID
    work_id: uuid.UUID
    trigger_type: str
    trigger_document_id: uuid.UUID | None
    trigger_jurisdiction: str | None
    created_at: datetime
    read_at: datetime | None
```

- [ ] **Step 4: Implement the router**

```python
# accounts/src/normly_accounts/routers/notifications.py
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account
from normly_core.graph.postgres.repositories import PostgresNotificationRepository

from normly_accounts.dependencies import get_current_account, get_session
from normly_accounts.schemas import NotificationResponse

notifications_router = APIRouter(prefix="/v1/accounts", tags=["notifications"])


def _notification_response(notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id, work_id=notification.work_id,
        trigger_type=notification.trigger_type.value,
        trigger_document_id=notification.trigger_document_id,
        trigger_jurisdiction=notification.trigger_jurisdiction,
        created_at=notification.created_at, read_at=notification.read_at,
    )


@notifications_router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    account: Account = Depends(get_current_account), session: Session = Depends(get_session),
) -> list[NotificationResponse]:
    notifications = PostgresNotificationRepository(session).list_for_account(account.id)
    return [_notification_response(n) for n in notifications]


@notifications_router.patch("/notifications/{notification_id}", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> NotificationResponse:
    repo = PostgresNotificationRepository(session)
    updated = repo.mark_read(
        notification_id, account_id=account.id, read_at=datetime.now(timezone.utc)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="notification not found")
    notifications = repo.list_for_account(account.id)
    return _notification_response(next(n for n in notifications if n.id == notification_id))
```

- [ ] **Step 5: Register the router**

In `accounts/src/normly_accounts/main.py`:

```python
from normly_accounts.routers.notifications import notifications_router
```

```python
    app.include_router(notifications_router, responses=COMMON_ERROR_RESPONSES)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd accounts && .venv/bin/pytest tests/test_notifications.py -v`
Expected: PASS.

Run: `cd accounts && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add accounts/src/normly_accounts/routers/notifications.py \
  accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/main.py \
  accounts/tests/test_notifications.py
git commit -s -m "feat(accounts): add notification list/mark-read endpoints"
```

---

### Task 9: Extend the profile endpoint with `notification_preference`

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py`
- Modify: `accounts/src/normly_accounts/routers/profile.py`
- Test: `accounts/tests/test_profile.py` (extend)

**Interfaces:**
- Consumes: `AccountRepository.update_notification_preference` (Task 1); `Account.notification_preference` (Task 1).
- Produces: `AccountResponse.notification_preference: str`; `UpdateProfileRequest.notification_preference: str | None` — `PATCH /v1/accounts/profile` now also accepts and returns this field, following the exact `model_fields_set` partial-update pattern already used for `first_name`/`last_name`.

- [ ] **Step 1: Write the failing test**

```python
# append to accounts/tests/test_profile.py
# (this file already defines _register_and_authorize(client) at the top --
# reuse it exactly, matching every other test in the file)

def test_update_notification_preference(client):
    _, headers = _register_and_authorize(client)
    response = client.patch(
        "/v1/accounts/profile", json={"notification_preference": "email"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["notification_preference"] == "email"


def test_updating_only_the_name_leaves_notification_preference_unchanged(client):
    _, headers = _register_and_authorize(client)
    client.patch("/v1/accounts/profile", json={"notification_preference": "both"}, headers=headers)
    response = client.patch("/v1/accounts/profile", json={"first_name": "Jamie"}, headers=headers)
    assert response.json()["notification_preference"] == "both"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd accounts && .venv/bin/pytest tests/test_profile.py -v -k notification_preference`
Expected: FAIL — `KeyError`/`AssertionError` (field doesn't exist in the response yet, request field is silently ignored by Pydantic).

- [ ] **Step 3: Extend the schemas**

In `accounts/src/normly_accounts/schemas.py`:

```python
class UpdateProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    notification_preference: str | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    first_name: str | None
    last_name: str | None
    avatar_data_url: str | None
    has_password: bool
    notification_preference: str
```

- [ ] **Step 4: Extend `profile.py`**

```python
from normly_core.graph.domain import NotificationPreference
```

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


@profile_router.patch("/profile", response_model=AccountResponse)
def update_profile(
    payload: UpdateProfileRequest, account: Account = Depends(get_current_account),
    session: Session = Depends(get_session),
) -> AccountResponse:
    fields_set = payload.model_fields_set
    first_name = payload.first_name if "first_name" in fields_set else account.first_name
    last_name = payload.last_name if "last_name" in fields_set else account.last_name

    account_repo = PostgresAccountRepository(session)
    account_repo.update_profile_names(account.id, first_name=first_name, last_name=last_name)
    if "notification_preference" in fields_set and payload.notification_preference is not None:
        account_repo.update_notification_preference(
            account.id, preference=NotificationPreference(payload.notification_preference)
        )
    updated = account_repo.get_account_by_id(account.id)
    return _account_response(updated)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd accounts && .venv/bin/pytest tests/test_profile.py -v`
Expected: PASS.

Run: `cd accounts && .venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add accounts/src/normly_accounts/schemas.py \
  accounts/src/normly_accounts/routers/profile.py \
  accounts/tests/test_profile.py
git commit -s -m "feat(accounts): let PATCH /v1/accounts/profile set notification_preference"
```

---

### Task 10: Frontend BFF routes and account-response plumbing

**Files:**
- Create: `frontend/src/app/api/account/watchlist/route.ts`
- Create: `frontend/src/app/api/account/watchlist/[workId]/route.ts`
- Create: `frontend/src/app/api/account/notifications/route.ts`
- Create: `frontend/src/app/api/account/notifications/[id]/route.ts`
- Modify: `frontend/src/lib/account-response.ts`
- Test: `frontend/tests/unit/account-watchlist-route.test.ts` (new)
- Test: `frontend/tests/unit/account-notifications-route.test.ts` (new)
- Test: `frontend/tests/unit/account-response.test.ts` (extend)

**Interfaces:**
- Consumes: `POST/DELETE/GET /v1/accounts/watchlist` (Task 7), `GET/PATCH /v1/accounts/notifications` (Task 8), `AccountResponse.notification_preference` (Task 9).
- Produces: `AccountSummary.notificationPreference: string`; `/api/account/watchlist` (`POST` body `{workId}` → `{workId, createdAt}`, `GET` → `{workId, createdAt}[]`); `/api/account/watchlist/[workId]` (`DELETE`); `/api/account/notifications` (`GET` → `{id, workId, triggerType, triggerDocumentId, triggerJurisdiction, createdAt, readAt}[]`); `/api/account/notifications/[id]` (`PATCH`). Task 11-13 call only these BFF routes, never the backend directly.

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/account-watchlist-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/account/watchlist/route";
import { DELETE } from "@/app/api/account/watchlist/[workId]/route";

const originalFetch = global.fetch;

describe("/api/account/watchlist", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns 401 for GET without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/watchlist"));
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards POST with the account cookie as Authorization", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ work_id: "11111111-1111-1111-1111-111111111111", created_at: "2026-01-01T00:00:00Z" }),
        { status: 200 },
      ),
    );
    const request = new NextRequest("http://localhost/api/account/watchlist", {
      method: "POST",
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
      body: JSON.stringify({ workId: "11111111-1111-1111-1111-111111111111" }),
    });
    const response = await POST(request);
    const body = await response.json();
    expect(body.workId).toBe("11111111-1111-1111-1111-111111111111");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ work_id: "11111111-1111-1111-1111-111111111111" });
  });

  it("forwards DELETE for a given workId", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "removed" }), { status: 200 }));
    const request = new NextRequest("http://localhost/api/account/watchlist/work-1", {
      method: "DELETE",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request, { params: Promise.resolve({ workId: "work-1" }) });
    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/watchlist/work-1");
  });
});
```

```typescript
// frontend/tests/unit/account-notifications-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/notifications/route";
import { PATCH } from "@/app/api/account/notifications/[id]/route";

const originalFetch = global.fetch;

describe("/api/account/notifications", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns 401 for GET without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/notifications"));
    expect(response.status).toBe(401);
  });

  it("forwards PATCH for a given notification id", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "n1", read_at: "2026-01-01T00:00:00Z" }), { status: 200 }),
    );
    const request = new NextRequest("http://localhost/api/account/notifications/n1", {
      method: "PATCH",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await PATCH(request, { params: Promise.resolve({ id: "n1" }) });
    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/notifications/n1");
    expect(init.method).toBe("PATCH");
  });
});
```

```typescript
// append to frontend/tests/unit/account-response.test.ts
// (extend the existing mapAccountSummary test(s) with the new field; read
// that file first and add notification_preference to every RawAccountFields
// fixture object it already builds, plus one assertion that
// mapAccountSummary(...).notificationPreference echoes raw.notification_preference.)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/account-watchlist-route.test.ts tests/unit/account-notifications-route.test.ts tests/unit/account-response.test.ts`
Expected: FAIL — module not found for the two new route test files; type/assertion failure for `account-response.test.ts`.

- [ ] **Step 3: Extend `account-response.ts`**

```typescript
export interface AccountSummary {
  accountId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  avatarDataUrl: string | null;
  hasPassword: boolean;
  notificationPreference: string;
}

interface RawAccountFields {
  first_name: string | null;
  last_name: string | null;
  avatar_data_url: string | null;
  has_password: boolean;
  notification_preference: string;
}

export function mapAccountSummary(
  accountId: string, email: string, raw: RawAccountFields,
): AccountSummary {
  return {
    accountId, email, firstName: raw.first_name, lastName: raw.last_name,
    avatarDataUrl: raw.avatar_data_url, hasPassword: raw.has_password,
    notificationPreference: raw.notification_preference,
  };
}
```

- [ ] **Step 4: Add the watchlist BFF routes**

```typescript
// frontend/src/app/api/account/watchlist/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

interface RawWatchlistEntry {
  work_id: string;
  created_at: string;
}

function mapEntry(raw: RawWatchlistEntry) {
  return { workId: raw.work_id, createdAt: raw.created_at };
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/watchlist`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    return NextResponse.json(await backendResponse.json(), { status: backendResponse.status });
  }
  const body: RawWatchlistEntry[] = await backendResponse.json();
  return NextResponse.json(body.map(mapEntry));
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/watchlist`, {
    method: "POST",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify({ work_id: payload.workId }),
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapEntry(body));
}
```

```typescript
// frontend/src/app/api/account/watchlist/[workId]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function DELETE(
  request: NextRequest, { params }: { params: Promise<{ workId: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const { workId } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/watchlist/${workId}`,
    { method: "DELETE", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 5: Add the notifications BFF routes**

```typescript
// frontend/src/app/api/account/notifications/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

interface RawNotification {
  id: string;
  work_id: string;
  trigger_type: string;
  trigger_document_id: string | null;
  trigger_jurisdiction: string | null;
  created_at: string;
  read_at: string | null;
}

function mapNotification(raw: RawNotification) {
  return {
    id: raw.id, workId: raw.work_id, triggerType: raw.trigger_type,
    triggerDocumentId: raw.trigger_document_id, triggerJurisdiction: raw.trigger_jurisdiction,
    createdAt: raw.created_at, readAt: raw.read_at,
  };
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/notifications`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    return NextResponse.json(await backendResponse.json(), { status: backendResponse.status });
  }
  const body: RawNotification[] = await backendResponse.json();
  return NextResponse.json(body.map(mapNotification));
}
```

```typescript
// frontend/src/app/api/account/notifications/[id]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function PATCH(
  request: NextRequest, { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const { id } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/notifications/${id}`,
    { method: "PATCH", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/account-watchlist-route.test.ts tests/unit/account-notifications-route.test.ts tests/unit/account-response.test.ts`
Expected: PASS.

Run: `cd frontend && npx vitest run`
Expected: PASS (every existing test still green — `mapAccountSummary`'s new required field could break any test file constructing a `RawAccountFields`/`AccountSummary` fixture literal directly instead of through a helper; grep for `avatar_data_url` and `hasPassword` across `tests/` to find every such literal and add `notification_preference`/`notificationPreference` to each).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/api/account/watchlist/ \
  frontend/src/app/api/account/notifications/ \
  frontend/src/lib/account-response.ts \
  frontend/tests/unit/account-watchlist-route.test.ts \
  frontend/tests/unit/account-notifications-route.test.ts \
  frontend/tests/unit/account-response.test.ts
git commit -s -m "feat(frontend): add watchlist/notifications BFF routes"
```

---

### Task 11: Heart-icon favorite toggle on the document detail page

**Files:**
- Modify: `frontend/src/app/documents/[id]/document-detail-content.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/document-detail-page.test.tsx` (extend — this is the file that tests `DocumentDetailContent`, despite the different basename)

**Interfaces:**
- Consumes: `/api/account/watchlist` (Task 10, `GET` for initial state, `POST` to add), `/api/account/watchlist/[workId]` (Task 10, `DELETE` to remove); `useAccountSession` (existing, `frontend/src/lib/use-account-session.ts`, unchanged, itself calls `/api/auth/session`).
- Produces: a heart toggle button (`data-testid="watchlist-toggle"`) rendered whenever both an account is logged in AND `workStructure` is loaded; no new exported symbols, purely a UI addition to the existing component.

- [ ] **Step 1: Extend the mock helper and write the failing tests**

`frontend/tests/unit/document-detail-page.test.tsx`'s `mockFetch(overrides)` function only branches on `/api/documents/...` URLs today. `DocumentDetailContent` is about to call `useAccountSession` (which fetches `/api/auth/session`) and, once logged in, `/api/account/watchlist`. Extend `mockFetch` with two new branches and an `account`/`watchlist` overrides shape, added right after the function's opening line (`global.fetch = vi.fn().mockImplementation((url: string) => {`), before the existing `/api/documents/...` branches:

```typescript
function mockFetch(
  overrides: { work?: object; rights?: object; account?: object | null; watchlist?: object[] } = {},
) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/auth/session")) {
      return Promise.resolve(
        new Response(JSON.stringify({ account: overrides.account ?? null }), { status: 200 }),
      );
    }
    if (url.includes("/api/account/watchlist")) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides.watchlist ?? []), { status: 200 }),
      );
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/edges`)) {
      // ... unchanged, every existing branch below stays exactly as it is
```

(This is additive only — every one of this file's six existing tests calls `mockFetch()` with no arguments, so `overrides.account` defaults to `null`, meaning `useAccountSession` reports "not logged in" exactly like before this task existed, and the new watchlist-fetching code path (gated on `account &&`, see Step 4) never runs for them. None of the six existing tests or their assertions need to change.)

Add three new tests, importing `fireEvent` alongside this file's existing `testing-library` imports (`render, screen, waitFor, within` → add `fireEvent`):

```typescript
  it("shows no watchlist toggle for an anonymous visitor and never calls the watchlist API", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "EN ISO 9001:2018" })).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("watchlist-toggle")).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(expect.stringContaining("/api/account/watchlist"));
  });

  it("shows an empty heart for a logged-in visitor who has not favorited this Work, and adds it on click", async () => {
    mockFetch({
      account: {
        accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
        avatarDataUrl: null, hasPassword: true, notificationPreference: "none",
      },
      watchlist: [],
    });

    renderDetail(DOCUMENT_ID);

    const toggle = await screen.findByTestId("watchlist-toggle");
    expect(toggle).toHaveAttribute("aria-label", "Zur Watchlist hinzufügen");

    fireEvent.click(toggle);

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/account/watchlist",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ workId: WORK_ID }) }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("watchlist-toggle")).toHaveAttribute(
        "aria-label", "Von Watchlist entfernen",
      ),
    );
  });

  it("shows a filled heart for a logged-in visitor who already favorited this Work, and removes it on click", async () => {
    mockFetch({
      account: {
        accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
        avatarDataUrl: null, hasPassword: true, notificationPreference: "none",
      },
      watchlist: [{ workId: WORK_ID, createdAt: "2026-01-01T00:00:00Z" }],
    });

    renderDetail(DOCUMENT_ID);

    const toggle = await screen.findByTestId("watchlist-toggle");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-label", "Von Watchlist entfernen"));

    fireEvent.click(toggle);

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        `/api/account/watchlist/${WORK_ID}`,
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: FAIL — no heart button exists yet (the first new test's `queryByTestId` assertion passes vacuously, but the other two time out in `findByTestId`).

- [ ] **Step 3: Add the i18n keys**

```json
// de.json, inside "documentDetail"
"addToWatchlist": "Zur Watchlist hinzufügen",
"removeFromWatchlist": "Von Watchlist entfernen",
```

```json
// en.json, inside "documentDetail"
"addToWatchlist": "Add to watchlist",
"removeFromWatchlist": "Remove from watchlist",
```

(Find the exact existing `"documentDetail"` block in both files — this plan's grounding confirmed it already holds `editionsHeading`, `mayProcess`, etc. — and add these two keys inside it, in both files, in the same position, so `tests/unit/i18n.test.tsx`'s key-parity check stays green.)

- [ ] **Step 4: Add the heart toggle**

In `document-detail-content.tsx`, add state, a *separate* effect (independent from the existing large data-loading effect — do not touch that effect at all, and in particular do not call `workResponse.json()` a second time inside it, since a `Response` body can only be read once) that loads watchlist membership once both an account and a `workStructure` are known, plus the toggle handler, then render the button next to the validity `Badge`:

```typescript
import { useAccountSession } from "@/lib/use-account-session";
```

```typescript
  const { account } = useAccountSession();
  const [isWatched, setIsWatched] = React.useState(false);
  const [isTogglingWatch, setIsTogglingWatch] = React.useState(false);

  React.useEffect(() => {
    if (!account || !workStructure) {
      setIsWatched(false);
      return;
    }
    let cancelled = false;
    fetch("/api/account/watchlist")
      .then((response) => (response.ok ? response.json() : []))
      .then((entries: { workId: string }[]) => {
        if (!cancelled) {
          setIsWatched(entries.some((entry) => entry.workId === workStructure.work_id));
        }
      })
      .catch(() => {
        if (!cancelled) setIsWatched(false);
      });
    return () => {
      cancelled = true;
    };
  }, [account, workStructure]);
```

(This is a new, independent `React.useEffect` call, placed right after the existing one that loads `documentDetail`/`edges`/`validity`/`workStructure`/`rights` — not merged into it. Anonymous visitors, or visitors on a document whose Work hasn't loaded yet, never call `/api/account/watchlist` at all.)

Add the toggle handler and button, rendered right after the existing `validity && (<Badge ... />)` block:

```typescript
  const toggleWatch = async () => {
    if (!workStructure) return;
    setIsTogglingWatch(true);
    try {
      if (isWatched) {
        await fetch(`/api/account/watchlist/${workStructure.work_id}`, { method: "DELETE" });
        setIsWatched(false);
      } else {
        await fetch("/api/account/watchlist", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ workId: workStructure.work_id }),
        });
        setIsWatched(true);
      }
    } finally {
      setIsTogglingWatch(false);
    }
  };
```

```tsx
      {account && workStructure && (
        <button
          type="button"
          onClick={toggleWatch}
          disabled={isTogglingWatch}
          aria-label={t(isWatched ? "documentDetail.removeFromWatchlist" : "documentDetail.addToWatchlist")}
          data-testid="watchlist-toggle"
        >
          <Heart className={isWatched ? "h-5 w-5 fill-current" : "h-5 w-5"} />
        </button>
      )}
```

```typescript
import { Heart } from "lucide-react";
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: PASS.

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/documents/\[id\]/document-detail-content.tsx \
  frontend/src/lib/i18n/de.json \
  frontend/src/lib/i18n/en.json \
  frontend/tests/unit/document-detail-page.test.tsx
git commit -s -m "feat(frontend): add a favorite/watchlist heart toggle to the document detail page"
```

---

### Task 12: Notification-preference section in the profile overlay

**Files:**
- Create: `frontend/src/components/account/notification-preference-section.tsx`
- Modify: `frontend/src/components/account/profile-overlay.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/notification-preference-section.test.tsx` (new)

**Interfaces:**
- Consumes: `/api/account/profile` (existing `PATCH` route, unchanged — Task 9 only added a field to the body it already passes through verbatim); `AccountSummary.notificationPreference` (Task 10).
- Produces: `NotificationPreferenceSection({ account, onAccountUpdated }: { account: AccountSummary; onAccountUpdated: (account: AccountSummary) => void })` — same prop shape as `NameAvatarSection`, added as a new tab in `ProfileOverlay`'s `SECTIONS`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/notification-preference-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NotificationPreferenceSection } from "@/components/account/notification-preference-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null, hasPassword: true, notificationPreference: "none",
};

describe("NotificationPreferenceSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("saves the selected preference", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...account, notificationPreference: "both" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={account} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Software und E-Mail"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "both" });
  });

  it("shows an error message when saving fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "something went wrong" }), { status: 500 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Software und E-Mail"));

    await waitFor(() =>
      expect(
        screen.getByText("Einstellung konnte nicht gespeichert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/notification-preference-section.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Add the i18n keys**

```json
// de.json, inside "account"
"notificationPreferenceTitle": "Benachrichtigungen",
"notificationPreferenceNone": "Keine Benachrichtigungen",
"notificationPreferenceInApp": "Nur in der Software",
"notificationPreferenceEmail": "Nur per E-Mail",
"notificationPreferenceBoth": "Software und E-Mail",
"notificationPreferenceSaveError": "Einstellung konnte nicht gespeichert werden. Bitte versuche es erneut."
```

```json
// en.json, inside "account"
"notificationPreferenceTitle": "Notifications",
"notificationPreferenceNone": "No notifications",
"notificationPreferenceInApp": "In-app only",
"notificationPreferenceEmail": "Email only",
"notificationPreferenceBoth": "In-app and email",
"notificationPreferenceSaveError": "Could not save this setting. Please try again."
```

- [ ] **Step 4: Implement the component**

```typescript
// frontend/src/components/account/notification-preference-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const OPTIONS: { value: string; labelKey: TranslationKey }[] = [
  { value: "none", labelKey: "account.notificationPreferenceNone" },
  { value: "in_app", labelKey: "account.notificationPreferenceInApp" },
  { value: "email", labelKey: "account.notificationPreferenceEmail" },
  { value: "both", labelKey: "account.notificationPreferenceBoth" },
];

export function NotificationPreferenceSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"idle" | "error">("idle");

  const save = async (value: string) => {
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ notification_preference: value }),
      });
      if (response.ok) {
        setStatus("idle");
        onAccountUpdated(await response.json());
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.notificationPreferenceTitle")}</h2>
      <div className="flex flex-col gap-2">
        {OPTIONS.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input
              type="radio" name="notification_preference" value={option.value}
              checked={account.notificationPreference === option.value}
              onChange={() => save(option.value)}
              aria-label={t(option.labelKey)}
            />
            {t(option.labelKey)}
          </label>
        ))}
      </div>
      {status === "error" && (
        <p className="text-sm text-destructive">{t("account.notificationPreferenceSaveError")}</p>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Wire the new section into `ProfileOverlay`**

In `frontend/src/components/account/profile-overlay.tsx`:

```typescript
import { NotificationPreferenceSection } from "@/components/account/notification-preference-section";
```

```typescript
type SectionId = "profile" | "notifications" | "email" | "password" | "sessions" | "data";

const SECTIONS: { id: SectionId; labelKey: TranslationKey }[] = [
  { id: "profile", labelKey: "account.nameAvatarTitle" },
  { id: "notifications", labelKey: "account.notificationPreferenceTitle" },
  { id: "email", labelKey: "account.emailTitle" },
  { id: "password", labelKey: "account.passwordTitle" },
  { id: "sessions", labelKey: "account.sessionsTitle" },
  { id: "data", labelKey: "account.dataSectionTitle" },
];
```

```tsx
              {activeSection === "notifications" && (
                <NotificationPreferenceSection account={account} onAccountUpdated={setAccount} />
              )}
```

(placed right after the existing `{activeSection === "profile" && (...)}` block)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/notification-preference-section.test.tsx tests/unit/profile-overlay.test.tsx`
Expected: PASS.

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/account/notification-preference-section.tsx \
  frontend/src/components/account/profile-overlay.tsx \
  frontend/src/lib/i18n/de.json \
  frontend/src/lib/i18n/en.json \
  frontend/tests/unit/notification-preference-section.test.tsx
git commit -s -m "feat(frontend): add a notification-preference section to the profile overlay"
```

---

### Task 13: Real data in the bell popover

**Files:**
- Create: `frontend/src/lib/use-notifications.ts`
- Modify: `frontend/src/components/page-header.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`
- Test: `frontend/tests/unit/page-header.test.tsx` (extend/modify)

**Interfaces:**
- Consumes: `/api/account/notifications` (Task 10, `GET`/`PATCH`).
- Produces: `useNotifications()` → `{ notifications, unreadCount, markRead, refresh }`, same shape family as `useAccountSession` (fetch-on-mount, `useState`, manual refresh). `PageHeader`'s public props are unchanged (`titleKey`, `subtitleKey`) — every existing caller (`app/page.tsx`, `app/search/page.tsx`, `app/documents/[id]/page.tsx`) needs no changes.

- [ ] **Step 1: Update the existing `page-header.test.tsx`**

`PageHeader` now fetches on mount (`useNotifications`), so every test in this file needs `global.fetch` mocked, and the existing test at line 54-58 (`"shows the static no-notifications message in the bell popover"`) — which asserted the OLD, always-static behavior — must be replaced with real-data coverage. Rewrite the whole file to this exact content (it is short enough to replace outright rather than patch piecemeal):

```typescript
// frontend/tests/unit/page-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { PageHeader } from "@/components/page-header";
import { SidebarProvider } from "@/components/ui/sidebar";

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

const originalFetch = global.fetch;

// PageHeader renders a SidebarTrigger (Finding 1 of the app-shell final
// review), which needs SidebarContext from SidebarProvider -- in the real
// app that's supplied by AppShell, but PageHeader is tested in isolation
// here, so it must be provided directly.
function renderPageHeader(ui: React.ReactElement) {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <SidebarProvider>{ui}</SidebarProvider>
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

describe("PageHeader", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  beforeEach(() => {
    // jsdom has no matchMedia -- the sidebar primitive's internal
    // useIsMobile() hook calls it on every render.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    // PageHeader now fetches notifications on mount (useNotifications) --
    // default every test to an empty list unless it overrides global.fetch
    // itself, so an unmocked fetch never throws in jsdom.
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
  });

  it("renders the translated title", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("renders no subtitle when subtitleKey is omitted", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.queryByText("Konto")).not.toBeInTheDocument();
  });

  it("renders the sidebar toggle button in its left cluster (Finding 1: the only sidebar toggle must live in PageHeader, not inside the Sidebar itself)", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("button", { name: "Seitenleiste umschalten" })).toBeInTheDocument();
  });

  it("shows the empty-notifications message when there are none", async () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(await screen.findByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });

  it("shows the empty-notifications message for an anonymous visitor (401)", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not authenticated" }), { status: 401 }),
    );
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(await screen.findByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });

  it("lists real notifications and marks one read on click", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
              triggerJurisdiction: null, createdAt: "2026-01-01T00:00:00Z", readAt: null,
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "n1", readAt: "2026-01-02T00:00:00Z" }), { status: 200 }),
      )
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    const item = await screen.findByTestId("notification-n1");
    fireEvent.click(item);

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/account/notifications/n1", expect.objectContaining({ method: "PATCH" }),
      ),
    );
  });
});
```

(The third mock in the last test's chain — `.mockResolvedValue(...)` with no `Once` — is the fallback for `useNotifications`' own `refresh()` re-fetch after `markRead` resolves; without it, the third and any later call would fall through to the second mock's response again via `mockResolvedValueOnce` exhaustion behavior, which is harmless here but worth being explicit about.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx`
Expected: FAIL — `useNotifications` doesn't exist; `PageHeader` still renders the static line.

- [ ] **Step 3: Add the i18n key**

```json
// de.json, inside "nav"
"notificationItemUnreadBadge": "Neu"
```

```json
// en.json, inside "nav"
"notificationItemUnreadBadge": "New"
```

- [ ] **Step 4: Implement `useNotifications`**

```typescript
// frontend/src/lib/use-notifications.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

export interface Notification {
  id: string;
  workId: string;
  triggerType: string;
  triggerDocumentId: string | null;
  triggerJurisdiction: string | null;
  createdAt: string;
  readAt: string | null;
}

export function useNotifications() {
  const [notifications, setNotifications] = React.useState<Notification[]>([]);

  const refresh = React.useCallback(() => {
    fetch("/api/account/notifications")
      .then((response) => (response.ok ? response.json() : []))
      .then((body: Notification[]) => setNotifications(body))
      .catch(() => setNotifications([]));
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const markRead = React.useCallback(async (id: string) => {
    try {
      await fetch(`/api/account/notifications/${id}`, { method: "PATCH" });
    } finally {
      refresh();
    }
  }, [refresh]);

  const unreadCount = notifications.filter((n) => n.readAt === null).length;

  return { notifications, unreadCount, markRead, refresh };
}
```

- [ ] **Step 5: Wire it into `page-header.tsx`**

```typescript
import { useNotifications } from "@/lib/use-notifications";
```

```typescript
  const { notifications, markRead } = useNotifications();
```

Replace the existing static `PopoverContent`:

```tsx
          <PopoverContent align="end">
            {notifications.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("nav.noNotifications")}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {notifications.map((notification) => (
                  <li key={notification.id}>
                    <button
                      type="button"
                      data-testid={`notification-${notification.id}`}
                      onClick={() => markRead(notification.id)}
                      className="flex w-full items-center justify-between gap-2 rounded-md p-2 text-left text-sm hover:bg-muted"
                    >
                      <span>{t(EDGE_TYPE_KEYS[notification.triggerType] ?? "nav.notificationsLabel")}</span>
                      {notification.readAt === null && (
                        <span className="text-xs text-primary">{t("nav.notificationItemUnreadBadge")}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PopoverContent>
```

`EDGE_TYPE_KEYS` does not exist in `page-header.tsx` today (it is local to `document-detail-content.tsx`). Do not import it across files — instead add a small local map in `page-header.tsx` covering the three trigger types this file actually renders:

```typescript
const TRIGGER_TYPE_KEYS: Record<string, TranslationKey> = {
  new_edition: "edgeType.replaces",
  national_adoption: "edgeType.adopted_from",
  rights_change: "documentDetail.rightsHeading",
};
```

and use `TRIGGER_TYPE_KEYS[notification.triggerType] ?? "nav.notificationsLabel"` in place of `EDGE_TYPE_KEYS[...]` above. (These three existing translation keys already read naturally as short labels for their respective trigger types — reuse them rather than inventing three new, near-duplicate strings.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx`
Expected: PASS.

Run: `cd frontend && npx vitest run`
Expected: PASS — every test file that renders `PageHeader` (directly or via `AppShell`) transitively now triggers a `fetch("/api/account/notifications")` call; check `documents-detail` or any other test that renders a full page including `PageHeader` and add a `global.fetch` mock there too if it doesn't already have one from Task 11.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/use-notifications.ts \
  frontend/src/components/page-header.tsx \
  frontend/src/lib/i18n/de.json \
  frontend/src/lib/i18n/en.json \
  frontend/tests/unit/page-header.test.tsx
git commit -s -m "feat(frontend): wire the bell popover to real notification data"
```
