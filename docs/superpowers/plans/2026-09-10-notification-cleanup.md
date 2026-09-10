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

## Self-Review Notes

**Spec coverage:** Policy (read-only, 60-day, `created_at`-based cutoff) → Task 1's `delete_read_before` implementation and both its tests. Repository method shape and docstring/comment → Task 1 Step 3, copied verbatim from the spec's own code block. CLI subcommand shape, constant placement, commit-then-print pattern → Task 2 Steps 1-3, copied verbatim from the spec. Testing section's four scenarios (old-read deleted, new-read kept, old-unread kept, correct count) → covered by Task 1's two tests. CLI integration test → Task 2's test, following the `backfill-document-embeddings` test's exact pattern (`committed_db`, `capsys`, a fresh `Session`, real commit, then `main([...])`). Out-of-scope items (no scheduler, no per-account override, no soft-delete) — no task introduces any of them, consistent with the spec.

**Placeholder scan:** No TBD/TODO; every step has literal code, not a description of code.

**Type consistency:** `delete_read_before(self, cutoff: datetime) -> int` is defined once in Task 1 and consumed identically in Task 2 (`PostgresNotificationRepository(session).delete_read_before(cutoff)`), matching signature and return type used directly as `deleted` in the f-string. `NotificationORM.read_at`/`created_at` field names match the live ORM (verified against the current file, not assumed).
