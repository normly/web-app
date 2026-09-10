# Notification Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound the `notification` table's unbounded growth with an opportunistic, CLI-triggered cleanup that deletes read notifications older than 60 days, never touching unread ones.

**Architecture:** A new repository method (`PostgresNotificationRepository.delete_read_before`) issues one `DELETE` filtered by `read_at IS NOT NULL AND created_at < cutoff`. A new `cleanup-notifications` CLI subcommand computes the cutoff and calls it, following the exact shape of the existing `backfill-document-embeddings` subcommand.

**Tech Stack:** Python, SQLAlchemy Core (`sa.delete`), argparse, pytest (real Postgres via the existing `db_session`/`committed_db`/`migrated_engine` fixtures).

## Global Constraints

- Retention period is a fixed code constant: `_NOTIFICATION_RETENTION_DAYS = 60`.
- Only notifications with `read_at IS NOT NULL` are ever eligible for deletion — unread notifications are exempt regardless of age.
- The cutoff applies to `created_at`, not `read_at` — a single predicate, not two clocks.
- Repository access only through the repository layer — the `sa.delete(...)` statement lives inside `PostgresNotificationRepository`, never in `cli.py`.
- Every commit needs `git commit -s` (DCO `Signed-off-by`, added automatically by `-s` — never type a literal `Signed-off-by:` line), Conventional Commits format, and a `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.

---

## File Structure

- Modify `core/src/normly_core/graph/postgres/repositories.py`: add `PostgresNotificationRepository.delete_read_before`, right after the existing `mark_read` method (ends at line 1004 as of this plan's writing).
- Modify `core/tests/graph/test_notification_repository.py`: add two new test functions for `delete_read_before`, after the existing `test_mark_read_only_succeeds_for_the_owning_account`.
- Modify `core/src/normly_core/pipeline/cli.py`: add the `_NOTIFICATION_RETENTION_DAYS` constant, a `cleanup-notifications` subparser, and its handling branch.
- Modify `core/tests/pipeline/test_cli.py`: add one new CLI integration test, plus three new imports it needs (`NotificationORM`, `NotificationTriggerType`, `WorkCreatedVia`, `PostgresWorkRepository` — see Task 2 for exact import-line changes).

No new files. Both production files already exist and already host the closest analogous feature (`mark_read` for the repository; `backfill-document-embeddings` for the CLI).

---

### Task 1: `PostgresNotificationRepository.delete_read_before`

**Files:**
- Modify: `core/src/normly_core/graph/postgres/repositories.py:996-1004` (add new method after `mark_read`)
- Test: `core/tests/graph/test_notification_repository.py`

**Interfaces:**
- Produces: `PostgresNotificationRepository.delete_read_before(self, cutoff: datetime) -> int` — deletes every notification with `read_at IS NOT NULL AND created_at < cutoff`, returns the number of rows deleted. Consumed by Task 2's CLI command.

No imports need to change in `repositories.py` — `NotificationORM`, `sa`, and `datetime` are already imported (verified: `NotificationORM` is imported at line 74, `sa` at line 7, `from datetime import date, datetime, timezone` at line 5).

- [ ] **Step 1: Write the failing tests**

Open `core/tests/graph/test_notification_repository.py` and add these two test functions at the end of the file (after `test_mark_read_only_succeeds_for_the_owning_account`):

```python
def test_delete_read_before_only_removes_read_notifications_older_than_cutoff(db_session):
    account = _make_account(db_session, "notif-cleanup@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    old_read = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    new_read = repo.create(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    old_unread = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.RIGHTS_CHANGE,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )

    # created_at is server_default=func.now(), frozen for the whole
    # transaction -- backdate explicitly, same technique as
    # test_list_for_account_orders_newest_first above.
    db_session.execute(
        sa.update(NotificationORM)
        .where(NotificationORM.id.in_([old_read.id, old_unread.id]))
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()

    now = datetime.now(timezone.utc)
    repo.mark_read(old_read.id, account_id=account.id, read_at=now)
    repo.mark_read(new_read.id, account_id=account.id, read_at=now)
    # old_unread stays unread.

    deleted_count = repo.delete_read_before(datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert deleted_count == 1
    remaining_ids = {n.id for n in repo.list_for_account(account.id)}
    assert remaining_ids == {new_read.id, old_unread.id}


def test_delete_read_before_returns_the_number_of_rows_deleted(db_session):
    account = _make_account(db_session, "notif-cleanup-count@example.de")
    work = _make_work(db_session)
    repo = PostgresNotificationRepository(db_session)

    first = repo.create(
        account_id=account.id, work_id=work.id, trigger_type=NotificationTriggerType.NEW_EDITION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    second = repo.create(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION,
        trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
        may_process=None, may_index_fulltext=None, may_cite_passages=None, may_export_free=None,
        emailed_at=None,
    )
    db_session.execute(
        sa.update(NotificationORM)
        .where(NotificationORM.id.in_([first.id, second.id]))
        .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    )
    db_session.flush()
    now = datetime.now(timezone.utc)
    repo.mark_read(first.id, account_id=account.id, read_at=now)
    repo.mark_read(second.id, account_id=account.id, read_at=now)

    deleted_count = repo.delete_read_before(datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert deleted_count == 2
    assert repo.list_for_account(account.id) == []
```

Both tests use only fixtures/helpers already present in the file (`_make_account`, `_make_work`, `PostgresNotificationRepository`, `NotificationORM`, `NotificationTriggerType` — all already imported at the top of this file). No new imports needed for this test file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_notification_repository.py -v -k delete_read_before`

Expected: both tests FAIL with `AttributeError: 'PostgresNotificationRepository' object has no attribute 'delete_read_before'`.

- [ ] **Step 3: Implement `delete_read_before`**

In `core/src/normly_core/graph/postgres/repositories.py`, add this method to `PostgresNotificationRepository`, immediately after the existing `mark_read` method (which currently ends with `return result.rowcount > 0`):

```python
    def delete_read_before(self, cutoff: datetime) -> int:
        # Only read notifications are ever eligible -- an account that hasn't
        # logged in for months must not lose notifications it hasn't seen yet,
        # regardless of age. Mirrors PostgresRateLimitRepository's
        # delete_buckets_before opportunistic-cleanup idiom.
        result = self._session.execute(
            sa.delete(NotificationORM).where(
                NotificationORM.read_at.is_not(None),
                NotificationORM.created_at < cutoff,
            )
        )
        return result.rowcount
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_notification_repository.py -v`

Expected: PASS, all tests in the file (including the two new ones and every pre-existing test in it).

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_notification_repository.py
git commit -s -m "$(cat <<'EOF'
feat(core): add PostgresNotificationRepository.delete_read_before

Deletes read notifications older than a given cutoff, keeping unread
ones regardless of age -- the repository-layer half of the
notification-cleanup design (docs/superpowers/specs/2026-09-10-notification-cleanup-design.md).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `cleanup-notifications` CLI subcommand

**Files:**
- Modify: `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/pipeline/test_cli.py`

**Interfaces:**
- Consumes: `PostgresNotificationRepository.delete_read_before(cutoff: datetime) -> int` from Task 1.
- Produces: `main(["cleanup-notifications"])` — deletes eligible notifications, commits, prints `f"notifications_deleted={deleted}"` to stdout, returns exit code `0`.

- [ ] **Step 1: Write the failing test**

Open `core/tests/pipeline/test_cli.py`. First, update its imports:

Change this import block (currently around line 11-16):

```python
from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationPreference,
)
```

to:

```python
from normly_core.graph.domain import (
    EdgeType,
    Layer,
    LegalBasisCategory,
    NotificationPreference,
    NotificationTriggerType,
    WorkCreatedVia,
)
```

Change this import (currently around line 17):

```python
from normly_core.graph.postgres.orm import DocumentDesignationORM, SourceORM, WatchlistORM
```

to:

```python
from normly_core.graph.postgres.orm import (
    DocumentDesignationORM,
    NotificationORM,
    SourceORM,
    WatchlistORM,
)
```

Change this import block (currently around line 18-26):

```python
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresSourceRepository,
    PostgresWatchlistRepository,
)
```

to:

```python
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDeliveryRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresSourceRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)
```

`PostgresAccountRepository`, `PostgresNotificationRepository`, `sa`, `Session` (imported locally inside other test functions via `from sqlalchemy.orm import Session`) are already available. `"notification"` is already in `_WRITTEN_TABLES` (line ~39), so the `committed_db` fixture's teardown truncation needs no change.

Now add this test at the end of the file:

```python
def test_cleanup_notifications_command_deletes_old_read_notifications(committed_db, capsys):
    from sqlalchemy.orm import Session

    with Session(committed_db) as session:
        account = PostgresAccountRepository(session).create_account(
            email="cli-notif-cleanup@example.de", password_hash=None,
        )
        work = PostgresWorkRepository(session).create_work(created_via=WorkCreatedVia.MANUAL)
        repo = PostgresNotificationRepository(session)
        old_read = repo.create(
            account_id=account.id, work_id=work.id,
            trigger_type=NotificationTriggerType.NEW_EDITION,
            trigger_edge_id=None, trigger_document_id=None, trigger_jurisdiction=None,
            may_process=None, may_index_fulltext=None, may_cite_passages=None,
            may_export_free=None, emailed_at=None,
        )
        session.execute(
            sa.update(NotificationORM)
            .where(NotificationORM.id == old_read.id)
            .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        )
        repo.mark_read(old_read.id, account_id=account.id, read_at=datetime.now(timezone.utc))
        session.commit()

    exit_code = main(["cleanup-notifications"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "notifications_deleted=1" in output
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_cli.py -v -k test_cleanup_notifications_command_deletes_old_read_notifications`

Expected: FAIL with `SystemExit` from argparse (`error: argument command: invalid choice: 'cleanup-notifications'`), since the subcommand doesn't exist yet.

- [ ] **Step 3: Implement the CLI subcommand**

In `core/src/normly_core/pipeline/cli.py`:

First, add `PostgresNotificationRepository` to the existing repositories import and add a `datetime` import. Change:

```python
from normly_core.graph.postgres.repositories import PostgresSourceRepository
```

to:

```python
from normly_core.graph.postgres.repositories import (
    PostgresNotificationRepository,
    PostgresSourceRepository,
)
```

Add this import near the top of the file, after the `from pathlib import Path` line:

```python
from datetime import datetime, timedelta, timezone
```

Add the retention constant near the existing `_NOTIFY_WATCHERS_LOCK_KEY` constant (after its definition, which currently ends the module-level constants section):

```python
# Starting point, not a carefully-derived number -- revisit once real usage
# data exists. Only read notifications are ever eligible for cleanup; unread
# ones are kept regardless of age (see delete_read_before).
_NOTIFICATION_RETENTION_DAYS = 60
```

Add the subparser registration right after the existing `subparsers.add_parser("backfill-document-embeddings")` line and before `subparsers.add_parser("notify-watchers")`:

```python
    subparsers.add_parser("cleanup-notifications")
```

Add the handling branch right after the existing `elif args.command == "backfill-document-embeddings":` block (which currently ends with `print(f"document_embeddings_created={created}")`) and before `elif args.command == "notify-watchers":`:

```python
            elif args.command == "cleanup-notifications":
                cutoff = datetime.now(timezone.utc) - timedelta(days=_NOTIFICATION_RETENTION_DAYS)
                deleted = PostgresNotificationRepository(session).delete_read_before(cutoff)
                session.commit()
                print(f"notifications_deleted={deleted}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd core && .venv/bin/pytest tests/pipeline/test_cli.py -v -k test_cleanup_notifications_command_deletes_old_read_notifications`

Expected: PASS.

- [ ] **Step 5: Run the full core/ test suite**

Run: `cd core && .venv/bin/pytest tests/`

Expected: PASS, no regressions (confirms the new imports in `test_cli.py` and the new CLI branch didn't break any existing test, e.g. `notify-watchers`'s own tests still pass given the new `elif` branch sits between two existing ones).

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/pipeline/cli.py core/tests/pipeline/test_cli.py
git commit -s -m "$(cat <<'EOF'
feat(core): add cleanup-notifications CLI subcommand

Deletes read notifications older than 60 days via the new
delete_read_before repository method, following the same shape as
the existing backfill-document-embeddings subcommand. No scheduler
is wired up here (same as notify-watchers, externally invoked).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Addendum: Tasks 3-4 (added after the final whole-branch review)

The final whole-branch review of Tasks 1-2 found a Critical defect that is a
gap in the *design spec*, not a coding error: `notify-watchers`
(`core/src/normly_core/notifications/detection.py`) uses the `Notification`
table itself as its dedup marker for the `NEW_EDITION`/`NATIONAL_ADOPTION`
trigger types (`find_by_trigger_edge`). Once `cleanup-notifications` can
delete read notifications, deleting one of these rows makes the *next*
`notify-watchers` run treat the same old edge as new again — re-creating the
notification and re-sending the email, forever, every 60 days, for as long
as the watch exists. The `RIGHTS_CHANGE` trigger type is unaffected: it
already has its own dedicated bookkeeping table
(`rights_notification_baseline`) for exactly this reason — "Deliberately
NOT the Notification table" per that table's own comment. The same
reasoning was simply never applied to the edge-triggered types.

Tasks 3-4 close this gap by giving `NEW_EDITION`/`NATIONAL_ADOPTION` the
same treatment: a new, permanent, non-cleaned-up bookkeeping table
(`notified_edge`), decoupling notify-watchers' dedup from the user-facing
`Notification` table entirely. After Tasks 3-4, `delete_read_before` is
safe to run against every trigger type — no carve-out needed.

Two smaller findings from the same review are folded into Task 4: the CLI
integration test only checked the printed summary line, not that the row
was actually gone from the database (so it would still pass with
`session.commit()` deleted); and `delete_read_before`'s comment overstates
how closely it mirrors `delete_buckets_before` (that method returns `None`
and runs opportunistically per-request; this one returns `int` and runs via
a dedicated command).

### Task 3: `notified_edge` bookkeeping table

**Files:**
- Modify: `core/src/normly_core/graph/postgres/orm.py` (add `NotifiedEdgeORM`, right after `RightsNotificationBaselineORM`, which currently ends at line 639, before `ChatSessionORM` at line 642)
- Modify: `core/src/normly_core/graph/domain.py` (add a `NotifiedEdgeRepository` Protocol, right after `RightsNotificationBaselineRepository`'s Protocol block)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (add `NotifiedEdgeORM` to the existing ORM import block at line 58-83; add `PostgresNotifiedEdgeRepository`, right after `PostgresRightsNotificationBaselineRepository`, which currently ends at line 1152, before `_edge_to_domain` at line 1155)
- Create: `core/migrations/versions/0030_create_notified_edge.py`
- Test: `core/tests/graph/test_notified_edge_repository.py` (new file)

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `PostgresNotifiedEdgeRepository.has_been_notified(self, *, account_id: uuid.UUID, work_id: uuid.UUID, trigger_type: NotificationTriggerType, trigger_edge_id: uuid.UUID) -> bool` and `PostgresNotifiedEdgeRepository.mark_notified(self, *, account_id: uuid.UUID, work_id: uuid.UUID, trigger_type: NotificationTriggerType, trigger_edge_id: uuid.UUID) -> None`. Task 4 imports and calls both.

- [ ] **Step 1: Add the ORM model**

In `core/src/normly_core/graph/postgres/orm.py`, add this class immediately after `RightsNotificationBaselineORM` (which ends with the `updated_at` column definition, right before `class ChatSessionORM(Base):`):

```python
class NotifiedEdgeORM(Base):
    __tablename__ = "notified_edge"

    # Pure internal bookkeeping for the notify-watchers NEW_EDITION/
    # NATIONAL_ADOPTION dedup check: has this edge already produced a
    # notification for this account/work? Deliberately NOT the Notification
    # table -- a row here is never shown to a user, never emailed, and
    # never joined into anything user-facing, so cleanup-notifications'
    # deletion of read Notification rows can never cause notify-watchers to
    # treat an already-seen edge as new again. Same shape as
    # RightsNotificationBaselineORM, but keyed by edge instead of by
    # document/jurisdiction, and covering the two edge-triggered types
    # instead of RIGHTS_CHANGE.
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True
    )
    trigger_type: Mapped[NotificationTriggerType] = mapped_column(
        sa.Enum(
            NotificationTriggerType,
            name="notification_trigger_type",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        primary_key=True,
    )
    trigger_edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("edge.id"), primary_key=True
    )
    notified_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
```

`NotificationTriggerType` and `_enum_values` are already imported/defined in this file (used by `NotificationORM.trigger_type` a few lines above).

- [ ] **Step 2: Write the migration**

Create `core/migrations/versions/0030_create_notified_edge.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""create notified_edge table, index notification.created_at

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notified_edge",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("work_id", UUID(as_uuid=True), sa.ForeignKey("work.id"), primary_key=True),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "new_edition", "national_adoption", "rights_change",
                name="notification_trigger_type",
                native_enum=False,
                create_constraint=True,
            ),
            primary_key=True,
        ),
        sa.Column(
            "trigger_edge_id", UUID(as_uuid=True), sa.ForeignKey("edge.id"), primary_key=True,
        ),
        sa.Column(
            "notified_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # cleanup-notifications (Task 2) filters on both columns; without this,
    # every run is a full table scan of a table the design spec expects to
    # grow without bound between cleanups.
    op.create_index("ix_notification_created_at", "notification", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_created_at", table_name="notification")
    op.drop_table("notified_edge")
```

- [ ] **Step 3: Run the migration**

Run: `cd core && .venv/bin/python -m alembic upgrade head`
Expected: succeeds, no errors. (If your test database is managed by the test suite's own migration fixture rather than a persistent one, this step may be a no-op locally — in that case skip straight to Step 4 and let the test suite's own migration runner apply it.)

- [ ] **Step 4: Add the domain Protocol**

In `core/src/normly_core/graph/domain.py`, add this class immediately after `RightsNotificationBaselineRepository`'s Protocol block (after its `upsert_baseline` method's `...` and closing, before whatever class currently follows it):

```python
class NotifiedEdgeRepository(Protocol):
    """
    Pure internal bookkeeping for the notify-watchers NEW_EDITION/
    NATIONAL_ADOPTION dedup check. Deliberately separate from
    NotificationRepository so cleanup-notifications' deletion of read
    Notification rows never causes a re-notification -- a row here must
    never be exposed via any HTTP-reachable method or joined into a
    user-facing feed.
    """

    def has_been_notified(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> bool: ...

    def mark_notified(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> None: ...
```

- [ ] **Step 5: Write the failing repository tests**

Create `core/tests/graph/test_notified_edge_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import NotificationTriggerType, WorkCreatedVia
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresNotifiedEdgeRepository,
    PostgresWorkRepository,
)


def _make_account(db_session, email):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _make_work(db_session):
    return PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)


def test_has_been_notified_is_false_before_mark_notified_and_true_after(db_session):
    account = _make_account(db_session, "notified-edge@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    import uuid
    edge_id = uuid.uuid4()

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is False

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is True


def test_mark_notified_is_idempotent(db_session):
    account = _make_account(db_session, "notified-edge-idempotent@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    import uuid
    edge_id = uuid.uuid4()

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )
    # Calling it again for the same key must not raise (e.g. a duplicate-key
    # error) -- notify-watchers always checks has_been_notified first, but
    # the method itself should be safe to call twice.
    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is True


def test_has_been_notified_is_scoped_to_the_exact_key(db_session):
    account = _make_account(db_session, "notified-edge-scoped@example.de")
    other_account = _make_account(db_session, "notified-edge-other@example.de")
    work = _make_work(db_session)
    repo = PostgresNotifiedEdgeRepository(db_session)
    import uuid
    edge_id = uuid.uuid4()

    repo.mark_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    )

    # Different account, same edge/work/trigger_type -- not notified.
    assert repo.has_been_notified(
        account_id=other_account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NEW_EDITION, trigger_edge_id=edge_id,
    ) is False
    # Same account/work/edge, different trigger_type -- not notified.
    assert repo.has_been_notified(
        account_id=account.id, work_id=work.id,
        trigger_type=NotificationTriggerType.NATIONAL_ADOPTION, trigger_edge_id=edge_id,
    ) is False
```

(The `import uuid` inside each test function, rather than at module level, is a minor style choice — move it to a single top-of-file `import uuid` instead when implementing; the plan writes it this way only to keep each test snippet self-contained for reading.)

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd core && .venv/bin/pytest tests/graph/test_notified_edge_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PostgresNotifiedEdgeRepository'`.

- [ ] **Step 7: Implement `PostgresNotifiedEdgeRepository`**

In `core/src/normly_core/graph/postgres/repositories.py`, add `NotifiedEdgeORM` to the existing `from normly_core.graph.postgres.orm import (...)` block (currently lines 58-83), inserted alphabetically after `IdentityResolutionCaseORM` and before `NotificationORM`:

```python
    IdentityResolutionCaseORM,
    NotifiedEdgeORM,
    NotificationORM,
```

Then add this class immediately after `PostgresRightsNotificationBaselineRepository` (which currently ends at line 1152 with `return _rights_notification_baseline_to_domain(merged)`), before `def _edge_to_domain(orm: EdgeORM) -> Edge:`:

```python
class PostgresNotifiedEdgeRepository:
    def __init__(self, session: Session):
        self._session = session

    def has_been_notified(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> bool:
        return self._session.get(
            NotifiedEdgeORM, (account_id, work_id, trigger_type, trigger_edge_id)
        ) is not None

    def mark_notified(
        self,
        *,
        account_id: uuid.UUID,
        work_id: uuid.UUID,
        trigger_type: NotificationTriggerType,
        trigger_edge_id: uuid.UUID,
    ) -> None:
        self._session.merge(
            NotifiedEdgeORM(
                account_id=account_id, work_id=work_id,
                trigger_type=trigger_type, trigger_edge_id=trigger_edge_id,
            )
        )
        self._session.flush()
```

`NotificationTriggerType` is already imported in this file (line 42, used by `PostgresNotificationRepository.create`'s signature).

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd core && .venv/bin/pytest tests/graph/test_notified_edge_repository.py -v`
Expected: PASS, 3 passed.

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/graph/postgres/orm.py core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/migrations/versions/0030_create_notified_edge.py core/tests/graph/test_notified_edge_repository.py
git commit -s -m "$(cat <<'EOF'
feat(core): add notified_edge bookkeeping table

Pure internal dedup bookkeeping for notify-watchers' NEW_EDITION and
NATIONAL_ADOPTION detectors, mirroring rights_notification_baseline's
existing "deliberately not the Notification table" pattern. Not yet
wired into detection.py (Task 4) -- this task only adds the table,
repository, and its own tests. Also indexes notification.created_at,
used by cleanup-notifications' delete_read_before.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Wire up the new dedup table, remove the old one, prove the bug is fixed

**Files:**
- Modify: `core/src/normly_core/notifications/detection.py`
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (remove `find_by_trigger_edge` from `PostgresNotificationRepository`, currently lines 969-985; fix `delete_read_before`'s comment, currently lines 1005-1016)
- Modify: `core/src/normly_core/graph/domain.py` (remove `find_by_trigger_edge` from the `NotificationRepository` Protocol)
- Modify: `core/tests/graph/test_notification_repository.py` (remove the 2 tests that only exercised `find_by_trigger_edge`)
- Modify: `core/tests/notifications/test_detection.py` (add 1 new regression test)
- Modify: `core/tests/pipeline/test_cli.py` (add the missing row-count assertion to Task 2's CLI test)

**Interfaces:**
- Consumes: `PostgresNotifiedEdgeRepository.has_been_notified`/`.mark_notified` from Task 3.

- [ ] **Step 1: Write the failing regression test first**

Open `core/tests/notifications/test_detection.py`. Add `PostgresNotifiedEdgeRepository` to the existing `from normly_core.graph.postgres.repositories import (...)` block (currently lines 18-29), inserted alphabetically after `PostgresNotificationRepository` and before `PostgresRightsNotificationBaselineRepository`:

```python
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresRightsNotificationBaselineRepository,
```

Then add this test at the end of the file, right after `test_new_edition_edge_produces_one_notification_and_no_duplicate_on_a_second_run` (which ends with `assert len(PostgresNotificationRepository(db_session).list_for_account(account.id)) == 1` — the same setup this new test builds on):

```python
def test_deleting_a_read_notification_does_not_cause_a_duplicate_on_the_next_run(db_session):
    # Regression test for the bug the final review of the notification-
    # cleanup branch found: before notified_edge existed, the Notification
    # row itself was the only dedup marker for NEW_EDITION/NATIONAL_ADOPTION.
    # Once cleanup-notifications could delete a read Notification row, the
    # next notify-watchers run had no memory that the edge was already
    # handled -- it recreated the notification and, under EMAIL/BOTH,
    # re-sent the email. This proves that no longer happens.
    source = _make_source(db_session)
    delivery = _make_delivery(db_session, source.id, "no-duplicate-after-cleanup")
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
        email="watcher-no-dup@example.de", password_hash=None
    )
    PostgresAccountRepository(db_session).update_notification_preference(
        account.id, preference=NotificationPreference.IN_APP
    )
    watch = PostgresWatchlistRepository(db_session).add_watch(
        account_id=account.id, work_id=old.work_id
    )
    _set_created_at(db_session, WatchlistORM, watch.id, _BEFORE)

    sender = RecordingEmailSender()
    first_run = run_notify_watchers(db_session, sender)
    assert first_run.notifications_created == 1

    notification_repo = PostgresNotificationRepository(db_session)
    created = notification_repo.list_for_account(account.id)[0]
    notification_repo.mark_read(created.id, account_id=account.id, read_at=_AFTER)
    deleted_count = notification_repo.delete_read_before(_AFTER)
    assert deleted_count == 1
    assert notification_repo.list_for_account(account.id) == []

    second_run = run_notify_watchers(db_session, sender)

    assert second_run.notifications_created == 0
    assert notification_repo.list_for_account(account.id) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && .venv/bin/pytest tests/notifications/test_detection.py -v -k test_deleting_a_read_notification_does_not_cause_a_duplicate_on_the_next_run`
Expected: FAIL — `second_run.notifications_created == 1`, not `0` (the bug, reproduced).

- [ ] **Step 3: Wire `notified_edge` into `detection.py`**

In `core/src/normly_core/notifications/detection.py`, add `PostgresNotifiedEdgeRepository` to the existing `from normly_core.graph.postgres.repositories import (...)` block, inserted alphabetically after `PostgresNotificationRepository` and before `PostgresRightsNotificationBaselineRepository`:

```python
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresDocumentRepository,
    PostgresEdgeRepository,
    PostgresNotificationRepository,
    PostgresNotifiedEdgeRepository,
    PostgresRightsNotificationBaselineRepository,
    PostgresRightsRepository,
    PostgresWatchlistRepository,
)
```

In `run_notify_watchers`, add a `notified_edge_repo` alongside the other repository instantiations at the top of the function:

```python
    watchlist_repo = PostgresWatchlistRepository(session)
    notification_repo = PostgresNotificationRepository(session)
    notified_edge_repo = PostgresNotifiedEdgeRepository(session)
    account_repo = PostgresAccountRepository(session)
```

Replace the dedup check:

```python
                if notification_repo.find_by_trigger_edge(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                ) is not None:
                    continue
```

with:

```python
                if notified_edge_repo.has_been_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                ):
                    continue
```

Immediately after the `notifications_created += 1` / `if notification.emailed_at is not None: emails_sent += 1` block that follows the `_create_and_maybe_email(...)` call for the edge-triggered loop (NOT the RIGHTS_CHANGE loop further down, which has its own separate `notifications_created += 1` block and must NOT get this call — RIGHTS_CHANGE already has its own dedicated dedup via `rights_notification_baseline`), add:

```python
                notified_edge_repo.mark_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                )
```

So that whole block reads:

```python
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
                notified_edge_repo.mark_notified(
                    account_id=account.id, work_id=watch.work_id,
                    trigger_type=trigger_type, trigger_edge_id=edge.id,
                )
```

- [ ] **Step 4: Run the regression test to verify it passes**

Run: `cd core && .venv/bin/pytest tests/notifications/test_detection.py -v`
Expected: PASS, every test in the file (including the new one and all pre-existing ones — `find_by_trigger_edge` is not yet removed at this point, so nothing else in this file should have broken).

- [ ] **Step 5: Remove the now-dead `find_by_trigger_edge`**

In `core/src/normly_core/graph/domain.py`, delete the `find_by_trigger_edge` method from the `NotificationRepository` Protocol (currently the block from `def find_by_trigger_edge(` through its closing `...` and blank line, right before `def list_for_account`).

In `core/src/normly_core/graph/postgres/repositories.py`, delete the `find_by_trigger_edge` method from `PostgresNotificationRepository` (currently lines 969-985, the block from `def find_by_trigger_edge(` through `return _notification_to_domain(orm) if orm else None`, right before `def list_for_account`).

In `core/tests/graph/test_notification_repository.py`, delete these two now-obsolete tests: `test_create_and_find_by_trigger_edge` and `test_find_by_trigger_edge_returns_none_when_absent` (the first two test functions in the file, right after the helper functions). `PostgresNotificationRepository.create` is still exercised by every other test in this file (`test_list_for_account_orders_newest_first`, `test_mark_read_only_succeeds_for_the_owning_account`, and both `delete_read_before` tests from Task 1), so removing these two loses no coverage of `create` itself.

- [ ] **Step 6: Fix `delete_read_before`'s comment**

In `core/src/normly_core/graph/postgres/repositories.py`, replace the `delete_read_before` method's comment (currently lines 1006-1009):

```python
        # Only read notifications are ever eligible -- an account that hasn't
        # logged in for months must not lose notifications it hasn't seen yet,
        # regardless of age. Mirrors PostgresRateLimitRepository's
        # delete_buckets_before opportunistic-cleanup idiom.
```

with:

```python
        # Only read notifications are ever eligible -- an account that hasn't
        # logged in for months must not lose notifications it hasn't seen yet,
        # regardless of age. Same shape as PostgresRateLimitRepository's
        # delete_buckets_before, though that one returns None and runs
        # opportunistically per-request; this one returns a count and runs
        # via the dedicated cleanup-notifications command instead. Safe to
        # delete any trigger type: notify-watchers' own dedup no longer
        # depends on Notification rows surviving (see notified_edge).
```

- [ ] **Step 7: Fix the CLI test's missing row-count assertion**

In `core/tests/pipeline/test_cli.py`, find `test_cleanup_notifications_command_deletes_old_read_notifications` (added in Task 2). After its existing final assertion (`assert "notifications_deleted=1" in output`), add:

```python
    with Session(committed_db) as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(NotificationORM)
        ).scalar_one() == 0
```

(`Session`, `sa`, and `NotificationORM` are all already imported/used in this test function and file.)

- [ ] **Step 8: Run the full core/ test suite**

Run: `cd core && .venv/bin/pytest tests/`
Expected: PASS, no regressions. Confirm the count is 3 more than the Task-2 baseline of 382 (the 3 new Task-3 tests) plus whatever net change Task 4's own additions/removals produce (+1 regression test, -2 obsolete `find_by_trigger_edge` tests) — do not treat a mismatch as automatically wrong, read the actual pass/fail list if the count surprises you.

- [ ] **Step 9: Commit**

```bash
git add core/src/normly_core/notifications/detection.py core/src/normly_core/graph/domain.py core/src/normly_core/graph/postgres/repositories.py core/tests/graph/test_notification_repository.py core/tests/notifications/test_detection.py core/tests/pipeline/test_cli.py
git commit -s -m "$(cat <<'EOF'
fix(core): stop cleanup-notifications from causing duplicate re-notifications

notify-watchers used the Notification table itself as its dedup marker
for NEW_EDITION/NATIONAL_ADOPTION -- once cleanup-notifications could
delete a read notification, the next run had no memory that the
triggering edge was already handled, and recreated it (re-sending the
email under EMAIL/BOTH). Wire in the notified_edge bookkeeping table
from the previous commit instead, remove the now-dead
find_by_trigger_edge dedup path, and add a regression test proving the
delete-then-rerun sequence no longer duplicates. Also closes two
smaller final-review findings: the CLI test now asserts the row is
actually gone, not just the printed count, and delete_read_before's
comment no longer overstates its similarity to delete_buckets_before.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** Policy (read-only, 60-day, `created_at`-based cutoff) → Task 1's `delete_read_before` implementation and both its tests. Repository method shape and docstring/comment → Task 1 Step 3, copied verbatim from the spec's own code block. CLI subcommand shape, constant placement, commit-then-print pattern → Task 2 Steps 1-3, copied verbatim from the spec. Testing section's four scenarios (old-read deleted, new-read kept, old-unread kept, correct count) → covered by Task 1's two tests. CLI integration test → Task 2's test, following the `backfill-document-embeddings` test's exact pattern (`committed_db`, `capsys`, a fresh `Session`, real commit, then `main([...])`). Out-of-scope items (no scheduler, no per-account override, no soft-delete) — no task introduces any of them, consistent with the spec.

**Placeholder scan:** No TBD/TODO; every step has literal code, not a description of code.

**Type consistency:** `delete_read_before(self, cutoff: datetime) -> int` is defined once in Task 1 and consumed identically in Task 2 (`PostgresNotificationRepository(session).delete_read_before(cutoff)`), matching signature and return type used directly as `deleted` in the f-string. `NotificationORM.read_at`/`created_at` field names match the live ORM (verified against the current file, not assumed).
