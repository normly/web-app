# User management — backend (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server-side role model (user / publisher / administrator), publishers as contract partners, invitations with consent, blocking, an admin audit log and the admin API — everything the admin panel (PR 2) will call.

**Architecture:** Role, publisher binding and block live on `account` (migration 0041) next to three new tables (`publisher`, `account_invitation`, `admin_audit_log`). Repositories in `normly_core` own all SQL (ADR-006). The accounts service gets `/v1/admin/*` routers guarded by a capability check that reads the role from the database on every request, a public `POST /v1/accounts/invitations/accept`, and a central blocked-account check in session creation and validation. Mails use the existing template system.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 (testcontainers), pytest, Jinja2.

**Spec:** [`docs/superpowers/specs/2026-10-31-user-management-design.md`](../specs/2026-10-31-user-management-design.md)

## Global Constraints

- Every new source file starts with `# SPDX-License-Identifier: AGPL-3.0-or-later` and `# Copyright (C) 2026 normly contributors`.
- All SQL goes through repositories in `core/src/normly_core/graph/postgres/repositories.py`; routers never build queries.
- Every new repository Protocol method whose name starts with `get_` or `list_` must be added, with a reason, to `JURISDICTION_EXEMPT_READS` in `core/tests/graph/test_architecture.py`.
- Exactly one role per account: `user`, `publisher`, `administrator`. `role = publisher` ⇔ `publisher_id IS NOT NULL`.
- Block reasons: `bulk_retrieval`, `abuse`, `terms_violation`, `other`. No free text.
- Invitation validity: 7 days. Expired invitations deleted 30 days after expiry. Audit log retention: 730 days.
- Audit entries never contain an e-mail address; no foreign keys on `admin_audit_log`.
- Error `detail` codes used by the frontend (exact strings): `last_administrator`, `self_action`, `upgrade_requires_invitation`, `not_a_publisher`, `account_blocked`, `already_blocked`, `not_blocked`, `publisher_name_taken`, `invitation_invalid`.
- The accounts service answers every request-validation error with **400** (app-wide handler in `accounts/src/normly_accounts/errors.py`), never 422.
- Explicit `session.commit()` before building a response that reports a write (see the comment in `routers/login.py::_create_session_response`). Mails are sent **after** the commit; a failed send never rolls back the action and is reported as `email_sent: false`.
- Personal invitation message: plain text, max. 500 characters, never stored.
- Commits: Conventional Commits, `git commit -s` (DCO sign-off of the human committer), trailer `Assisted-by: Claude Code`. Never `Co-Authored-By`.
- Test commands (Docker must run; testcontainers starts Postgres):
  - core: `cd core && ../.venv/bin/pytest <path> -v`
  - accounts: `cd accounts && ../.venv/bin/pytest <path> -v`
- Accounts tests import shared helpers as `from tests.admin_support import …` (`accounts/tests/__init__.py` exists, so pytest puts `accounts/` on `sys.path`).
- The `/invitation` frontend page arrives in PR 2. Do not release between PR 1 and PR 2: invitation links would 404.

## File Structure

| File | Responsibility |
|---|---|
| `core/migrations/versions/0041_user_management.py` (create) | Schema: three tables, four `account` columns, constraints |
| `core/src/normly_core/graph/domain.py` (modify) | `Role`, `BlockReason`, `AdminAction`, dataclasses, Protocols, `PublisherNameTakenError` |
| `core/src/normly_core/graph/postgres/orm.py` (modify) | `PublisherORM`, `AccountInvitationORM`, `AdminAuditLogORM`, new `AccountORM` columns |
| `core/src/normly_core/graph/postgres/repositories.py` (modify) | Publisher, invitation, audit, admin-directory repositories; account and session additions |
| `core/src/normly_core/exchange/tables.py` (modify) | New tables in `USER_TABLES` |
| `core/src/normly_core/retention.py` (modify) | `INVITATION_EXPIRED_GRACE`, `ADMIN_AUDIT_RETENTION` |
| `core/src/normly_core/admin.py` (create) | `grant_administrator` used by the CLI |
| `core/src/normly_core/pipeline/cli.py` (modify) | Cleanup steps, `grant-admin` command |
| `core/src/normly_core/notifications/mail/{texts.py,render.py,templates/*}` (modify) | Three mail kinds, quoted personal message, `format_days`, `contact_address` |
| `accounts/src/normly_accounts/permissions.py` (create) | Capability matrix, the single source for guard and dialog |
| `accounts/src/normly_accounts/admin_rules.py` (create) | Shared admin checks: self action, last administrator, snapshots |
| `accounts/src/normly_accounts/admin_mail.py` (create) | Sending invitation / blocked / removed mails |
| `accounts/src/normly_accounts/admin_schemas.py` (create) | Pydantic models of the admin API |
| `accounts/src/normly_accounts/routers/admin_publishers.py` (create) | `GET/POST /v1/admin/publishers` |
| `accounts/src/normly_accounts/routers/admin_invitations.py` (create) | Check, create, resend, withdraw |
| `accounts/src/normly_accounts/routers/admin_accounts.py` (create) | Patch, block, unblock, remove |
| `accounts/src/normly_accounts/routers/admin_users.py` (create) | List, summary, role matrix |
| `accounts/src/normly_accounts/routers/invitation.py` (create) | `POST /v1/accounts/invitations/accept` |
| `accounts/src/normly_accounts/{dependencies.py,routers/session.py,routers/login.py,routers/magic_link.py,routers/password_reset.py,routers/google.py,routers/account_management.py,schemas.py,main.py}` (modify) | Guard, block enforcement, session fields, export |
| `accounts/tests/admin_support.py` (create) | Test helpers: accounts, publishers, sign-in headers |
| Docs (modify) | ADR-030, ADR-017, ADR-027, SRS, glossary, self-hosting, operations |

---

### Task 1: Schema, domain types and table groups

**Files:**
- Create: `core/migrations/versions/0041_user_management.py`
- Modify: `core/src/normly_core/graph/domain.py` (after `class AccountTokenPurpose`, the `Account` dataclass at ~line 1087)
- Modify: `core/src/normly_core/graph/postgres/orm.py` (imports, `AccountORM` ~line 432, new classes after `OAuthStateORM`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (`_account_to_domain` ~line 2159)
- Modify: `core/src/normly_core/exchange/tables.py` (`USER_TABLES`)
- Test: `core/tests/graph/test_user_management_migration.py` (create)

**Interfaces:**
- Produces: `Role`, `BlockReason`, `AdminAction` (str enums); `Account.role: Role = Role.USER`, `Account.publisher_id: uuid.UUID | None = None`, `Account.blocked_at: datetime | None = None`, `Account.block_reason: BlockReason | None = None`; dataclasses `Publisher`, `AccountInvitation`, `AdminAuditEntry`, `AdminUserRow`, `AdminUserPage`, `AdminSummary`; `PublisherNameTakenError`; ORM classes `PublisherORM`, `AccountInvitationORM`, `AdminAuditLogORM`.

- [ ] **Step 1: Write the failing migration test**

`core/tests/graph/test_user_management_migration.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

CORE_DIR = Path(__file__).parents[2]


def _alembic(db_url) -> Config:
    cfg = Config(str(CORE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_0041_round_trip_makes_existing_accounts_users(db_url, migrated_engine):
    cfg = _alembic(db_url)
    account = uuid.uuid4()
    try:
        command.downgrade(cfg, "0040")
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO account (id, email) VALUES (:a, 'mig0041@example.de')"),
                {"a": account},
            )
        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            row = connection.execute(
                sa.text("SELECT role, publisher_id, blocked_at FROM account WHERE id = :a"),
                {"a": account},
            ).one()
        assert tuple(row) == ("user", None, None)
    finally:
        command.upgrade(cfg, "head")
        with migrated_engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM account WHERE id = :a"), {"a": account})


@pytest.mark.parametrize("statement", [
    # publisher without binding
    "INSERT INTO account (id, email, role) VALUES (gen_random_uuid(), 'x1@example.de', 'publisher')",
    # binding without publisher role
    "INSERT INTO account (id, email, role, publisher_id) VALUES "
    "(gen_random_uuid(), 'x2@example.de', 'user', (SELECT id FROM publisher LIMIT 1))",
    # block time without reason
    "INSERT INTO account (id, email, blocked_at) VALUES (gen_random_uuid(), 'x3@example.de', now())",
    # unknown role
    "INSERT INTO account (id, email, role) VALUES (gen_random_uuid(), 'x4@example.de', 'owner')",
])
def test_account_constraints_reject_inconsistent_rows(db_session, statement):
    db_session.execute(sa.text(
        "INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'Constraint Verlag')"
    ))
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(sa.text(statement))


def test_publisher_names_are_unique_ignoring_case(db_session):
    db_session.execute(sa.text("INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'VDE Verlag')"))
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(
                sa.text("INSERT INTO publisher (id, name) VALUES (gen_random_uuid(), 'vde verlag')")
            )
```

- [ ] **Step 2: Run it and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_user_management_migration.py -v`
Expected: FAIL — `Can't locate revision identified by '0040'`-style errors are NOT expected; the failures are `column "role" does not exist` / `relation "publisher" does not exist`.

- [ ] **Step 3: Write the migration**

`core/migrations/versions/0041_user_management.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""user management: roles, publishers, invitations, admin audit log

Exactly one role per account; a publisher account is bound to one publisher
(the contract partner). Invitations bind a role only when their link is used.
The audit log keeps IDs only and survives account deletion (issue #60).

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

_ROLES = "('user', 'publisher', 'administrator')"
_BLOCK_REASONS = "('bulk_retrieval', 'abuse', 'terms_violation', 'other')"
_ADMIN_ACTIONS = (
    "('invitation_created', 'invitation_resent', 'invitation_withdrawn', "
    "'invitation_accepted', 'role_changed', 'publisher_changed', 'account_blocked', "
    "'account_unblocked', 'account_removed', 'publisher_created', "
    "'administrator_granted_cli')"
)


def upgrade() -> None:
    op.create_table(
        "publisher",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_publisher_name_lower", "publisher", [sa.text("lower(name)")], unique=True
    )

    op.add_column(
        "account",
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
    )
    op.add_column(
        "account",
        sa.Column(
            "publisher_id", UUID(as_uuid=True),
            sa.ForeignKey("publisher.id", name="fk_account_publisher_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("account", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("account", sa.Column("block_reason", sa.String(20), nullable=True))
    op.create_check_constraint("ck_account_role", "account", f"role IN {_ROLES}")
    op.create_check_constraint(
        "ck_account_block_reason", "account", f"block_reason IN {_BLOCK_REASONS}"
    )
    op.create_check_constraint(
        "ck_account_publisher_binding", "account",
        "(role = 'publisher') = (publisher_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_account_block", "account", "(blocked_at IS NULL) = (block_reason IS NULL)"
    )

    op.create_table(
        "account_invitation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "publisher_id", UUID(as_uuid=True),
            sa.ForeignKey("publisher.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("token", sa.String, nullable=False),
        sa.Column(
            "invited_by", UUID(as_uuid=True),
            sa.ForeignKey("account.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token", name="uq_account_invitation_token"),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_account_invitation_role"),
        sa.CheckConstraint("locale IN ('de', 'en')", name="ck_account_invitation_locale"),
        sa.CheckConstraint(
            "(role = 'publisher') = (publisher_id IS NOT NULL)",
            name="ck_account_invitation_publisher_binding",
        ),
    )
    op.create_index(
        "uq_account_invitation_email_lower", "account_invitation",
        [sa.text("lower(email)")], unique=True,
    )
    op.create_index("ix_account_invitation_expires_at", "account_invitation", ["expires_at"])

    op.create_table(
        "admin_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        # No foreign keys: entries must outlive the accounts they name.
        sa.Column("actor_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_invitation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_publisher_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(f"action IN {_ADMIN_ACTIONS}", name="ck_admin_audit_log_action"),
    )
    op.create_index("ix_admin_audit_log_occurred_at", "admin_audit_log", ["occurred_at"])
    op.create_index(
        "ix_admin_audit_log_target_account_id", "admin_audit_log", ["target_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_target_account_id", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_occurred_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_index("ix_account_invitation_expires_at", table_name="account_invitation")
    op.drop_index("uq_account_invitation_email_lower", table_name="account_invitation")
    op.drop_table("account_invitation")
    op.drop_constraint("ck_account_block", "account", type_="check")
    op.drop_constraint("ck_account_publisher_binding", "account", type_="check")
    op.drop_constraint("ck_account_block_reason", "account", type_="check")
    op.drop_constraint("ck_account_role", "account", type_="check")
    op.drop_column("account", "block_reason")
    op.drop_column("account", "blocked_at")
    op.drop_column("account", "publisher_id")
    op.drop_column("account", "role")
    op.drop_index("uq_publisher_name_lower", table_name="publisher")
    op.drop_table("publisher")
```

- [ ] **Step 4: Add the domain types**

In `core/src/normly_core/graph/domain.py`, directly after `class AccountTokenPurpose`:

```python
class Role(str, Enum):
    """Exactly one per account. Publisher and administrator include everything a user can do."""
    USER = "user"
    PUBLISHER = "publisher"
    ADMINISTRATOR = "administrator"


class BlockReason(str, Enum):
    BULK_RETRIEVAL = "bulk_retrieval"
    ABUSE = "abuse"
    TERMS_VIOLATION = "terms_violation"
    OTHER = "other"


class AdminAction(str, Enum):
    INVITATION_CREATED = "invitation_created"
    INVITATION_RESENT = "invitation_resent"
    INVITATION_WITHDRAWN = "invitation_withdrawn"
    INVITATION_ACCEPTED = "invitation_accepted"
    ROLE_CHANGED = "role_changed"
    PUBLISHER_CHANGED = "publisher_changed"
    ACCOUNT_BLOCKED = "account_blocked"
    ACCOUNT_UNBLOCKED = "account_unblocked"
    ACCOUNT_REMOVED = "account_removed"
    PUBLISHER_CREATED = "publisher_created"
    ADMINISTRATOR_GRANTED_CLI = "administrator_granted_cli"


class PublisherNameTakenError(Exception):
    def __init__(self, name: str):
        super().__init__(f"a publisher named {name!r} already exists")
        self.name = name
```

Extend `Account` (keep the existing fields; new ones last, with defaults so existing constructors keep working):

```python
    locale: str | None  # None = unknown (account created before it was stored)
    role: Role = Role.USER
    publisher_id: uuid.UUID | None = None
    blocked_at: datetime | None = None
    block_reason: BlockReason | None = None
```

After `OAuthState`, add:

```python
@dataclass(frozen=True)
class Publisher:
    """A contract partner whose content usage a publisher account may later see."""
    id: uuid.UUID
    name: str
    created_at: datetime


@dataclass(frozen=True)
class AccountInvitation:
    id: uuid.UUID
    email: str
    role: Role
    publisher_id: uuid.UUID | None
    locale: str
    token: str
    invited_by: uuid.UUID | None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class AdminAuditEntry:
    id: uuid.UUID
    occurred_at: datetime
    action: AdminAction
    actor_account_id: uuid.UUID | None
    target_account_id: uuid.UUID | None
    target_invitation_id: uuid.UUID | None
    target_publisher_id: uuid.UUID | None
    details: dict


@dataclass(frozen=True)
class AdminUserRow:
    """One row of the admin table: an account or an open/expired invitation."""
    kind: str  # "account" | "invitation"
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    sign_in_methods: tuple[str, ...]  # subset of ("email", "google"), in that order
    role: Role
    publisher_id: uuid.UUID | None
    publisher_name: str | None
    last_login_at: datetime | None
    created_at: datetime | None  # None for invitations
    status: str  # "active" | "blocked" | "invited" | "expired"
    block_reason: BlockReason | None
    expires_at: datetime | None  # invitations only


@dataclass(frozen=True)
class AdminUserPage:
    rows: list[AdminUserRow]
    total: int


@dataclass(frozen=True)
class AdminSummary:
    accounts_total: int
    accounts_active: int
    accounts_by_role: dict[Role, int]
    publishers_with_accounts: int
    open_invitations: int
    blocked: int
    most_frequent_block_reason: BlockReason | None
```

- [ ] **Step 5: Add the ORM mapping**

In `orm.py` import `AdminAction, BlockReason, Role` from `normly_core.graph.domain` and `JSONB` from `sqlalchemy.dialects.postgresql`. Add to `AccountORM` after `locale`:

```python
    # Exactly one role (ck_account_role); a publisher is bound to one publisher
    # (ck_account_publisher_binding). Read on every request, never cached.
    role: Mapped[Role] = mapped_column(
        sa.Enum(
            Role, name="account_role", native_enum=False, create_constraint=False,
            values_callable=_enum_values, length=16,
        ),
        nullable=False, default=Role.USER, server_default=Role.USER.value,
    )
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("publisher.id"), nullable=True
    )
    blocked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    block_reason: Mapped[BlockReason | None] = mapped_column(
        sa.Enum(
            BlockReason, name="block_reason", native_enum=False, create_constraint=False,
            values_callable=_enum_values, length=20,
        ),
        nullable=True,
    )
```

(`create_constraint=False`: the CHECK constraints are created by the migration under explicit names.)

After `OAuthStateORM` add:

```python
class PublisherORM(Base):
    __tablename__ = "publisher"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


sa.Index("uq_publisher_name_lower", sa.func.lower(PublisherORM.name), unique=True)


class AccountInvitationORM(Base):
    __tablename__ = "account_invitation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str]
    role: Mapped[Role] = mapped_column(
        sa.Enum(
            Role, name="account_role", native_enum=False, create_constraint=False,
            values_callable=_enum_values, length=16,
        )
    )
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("publisher.id"), nullable=True
    )
    locale: Mapped[str] = mapped_column(sa.String(2))
    token: Mapped[str]
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("token", name="uq_account_invitation_token"),
        sa.Index("ix_account_invitation_expires_at", "expires_at"),
    )


sa.Index(
    "uq_account_invitation_email_lower", sa.func.lower(AccountInvitationORM.email), unique=True
)


class AdminAuditLogORM(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    action: Mapped[AdminAction] = mapped_column(
        sa.Enum(
            AdminAction, name="admin_action", native_enum=False, create_constraint=False,
            values_callable=_enum_values, length=32,
        )
    )
    # No foreign keys: an entry outlives the account it names (ADR-030).
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_invitation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_publisher_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        sa.Index("ix_admin_audit_log_occurred_at", "occurred_at"),
        sa.Index("ix_admin_audit_log_target_account_id", "target_account_id"),
    )
```

`PublisherORM` must be defined before `AccountORM` references it only by string (`"publisher.id"`), so placement after `OAuthStateORM` is fine.

- [ ] **Step 6: Map the new account fields and register the tables**

In `repositories.py` replace `_account_to_domain` with:

```python
def _account_to_domain(orm: AccountORM) -> Account:
    return Account(
        id=orm.id, email=orm.email, password_hash=orm.password_hash,
        email_verified_at=orm.email_verified_at, created_at=orm.created_at,
        first_name=orm.first_name, last_name=orm.last_name,
        avatar_image=orm.avatar_image, avatar_content_type=orm.avatar_content_type,
        notification_preference=orm.notification_preference,
        locale=orm.locale, role=orm.role, publisher_id=orm.publisher_id,
        blocked_at=orm.blocked_at, block_reason=orm.block_reason,
    )
```

In `core/src/normly_core/exchange/tables.py`, `USER_TABLES` becomes (order is foreign-key safe: `publisher` before `account`, `account_invitation` after both):

```python
USER_TABLES: tuple[str, ...] = (
    "publisher",
    "account",
    "account_session",
    "account_google_identity",
    "account_token",
    "account_invitation",
    "admin_audit_log",
    "oauth_state",
    ...  # the remaining entries unchanged, in their current order
)
```

- [ ] **Step 7: Run the new test and the schema guards**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_user_management_migration.py tests/graph/test_orm_migration_consistency.py tests/graph/test_migration_determinism.py tests/exchange/test_tables.py tests/graph/test_account_repository.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add core/migrations/versions/0041_user_management.py core/src/normly_core/graph core/src/normly_core/exchange/tables.py core/tests/graph/test_user_management_migration.py
git commit -s -m "feat(core): add roles, publishers, invitations and admin audit schema" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 2: Publisher and audit repositories

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (Protocols after `AccountRepository`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py` (after `PostgresDeletionLogRepository`)
- Modify: `core/tests/graph/test_architecture.py` (`JURISDICTION_EXEMPT_READS`)
- Test: `core/tests/graph/test_publisher_and_audit_repository.py` (create)

**Interfaces:**
- Consumes: Task 1 types and ORM classes.
- Produces:
  - `PostgresPublisherRepository(session)`: `create_publisher(*, name: str, created_at: datetime) -> Publisher` (raises `PublisherNameTakenError`), `get_publisher(publisher_id: uuid.UUID) -> Publisher | None`, `list_publishers() -> list[Publisher]` (ordered by `lower(name)`).
  - `PostgresAdminAuditRepository(session)`: `record(*, action: AdminAction, actor_account_id: uuid.UUID | None, occurred_at: datetime, target_account_id: uuid.UUID | None = None, target_invitation_id: uuid.UUID | None = None, target_publisher_id: uuid.UUID | None = None, details: dict | None = None) -> None`, `list_for_target_account(account_id: uuid.UUID) -> list[AdminAuditEntry]` (oldest first), `delete_older_than(cutoff: datetime) -> int`.

- [ ] **Step 1: Write the failing tests**

`core/tests/graph/test_publisher_and_audit_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from normly_core.graph.domain import AdminAction, PublisherNameTakenError
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def test_create_and_list_publishers_sorted_by_name(db_session):
    repo = PostgresPublisherRepository(db_session)
    vde = repo.create_publisher(name="VDE Verlag", created_at=NOW)
    din = repo.create_publisher(name="DIN Media", created_at=NOW)

    assert [p.name for p in repo.list_publishers()] == ["DIN Media", "VDE Verlag"]
    assert repo.get_publisher(vde.id) == vde
    assert repo.get_publisher(uuid.uuid4()) is None
    assert din.created_at == NOW


def test_duplicate_publisher_name_raises_and_keeps_the_session_usable(db_session):
    repo = PostgresPublisherRepository(db_session)
    repo.create_publisher(name="DIN Media", created_at=NOW)
    with pytest.raises(PublisherNameTakenError):
        repo.create_publisher(name="din media", created_at=NOW)
    assert len(repo.list_publishers()) == 1


def test_audit_entries_survive_account_deletion_and_carry_no_email(db_session):
    accounts = PostgresAccountRepository(db_session)
    target = accounts.create_account(email="audited@example.de", password_hash=None)
    audit = PostgresAdminAuditRepository(db_session)
    audit.record(
        action=AdminAction.ACCOUNT_BLOCKED, actor_account_id=None, occurred_at=NOW,
        target_account_id=target.id, details={"reason": "abuse"},
    )
    accounts.delete_account(target.id)

    entries = audit.list_for_target_account(target.id)
    assert [(e.action, e.details) for e in entries] == [
        (AdminAction.ACCOUNT_BLOCKED, {"reason": "abuse"})
    ]
    assert "audited@example.de" not in repr(entries)


def test_delete_older_than_only_removes_old_entries(db_session):
    audit = PostgresAdminAuditRepository(db_session)
    target = uuid.uuid4()
    audit.record(action=AdminAction.ROLE_CHANGED, actor_account_id=None,
                 occurred_at=NOW - timedelta(days=800), target_account_id=target)
    audit.record(action=AdminAction.ROLE_CHANGED, actor_account_id=None,
                 occurred_at=NOW, target_account_id=target)

    assert audit.delete_older_than(NOW - timedelta(days=730)) == 1
    assert len(audit.list_for_target_account(target)) == 1
```

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_publisher_and_audit_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresAdminAuditRepository'`.

- [ ] **Step 3: Add the Protocols**

In `domain.py`, after `class AccountRepository`:

```python
class PublisherRepository(Protocol):
    def create_publisher(self, *, name: str, created_at: datetime) -> Publisher: ...

    def get_publisher(self, publisher_id: uuid.UUID) -> Publisher | None: ...

    def list_publishers(self) -> list[Publisher]: ...


class AdminAuditRepository(Protocol):
    """Administrative actions. IDs only, never an e-mail address (ADR-030)."""

    def record(
        self, *, action: AdminAction, actor_account_id: uuid.UUID | None,
        occurred_at: datetime, target_account_id: uuid.UUID | None = None,
        target_invitation_id: uuid.UUID | None = None,
        target_publisher_id: uuid.UUID | None = None, details: dict | None = None,
    ) -> None: ...

    def list_for_target_account(self, account_id: uuid.UUID) -> list[AdminAuditEntry]: ...

    def delete_older_than(self, cutoff: datetime) -> int: ...
```

- [ ] **Step 4: Implement the repositories**

In `repositories.py` (import `AdminAuditEntry, AdminAuditRepository, AdminAction, Publisher, PublisherNameTakenError, PublisherRepository` from the domain and `AdminAuditLogORM, PublisherORM` from the ORM), after `PostgresDeletionLogRepository`:

```python
def _publisher_to_domain(orm: PublisherORM) -> Publisher:
    return Publisher(id=orm.id, name=orm.name, created_at=orm.created_at)


class PostgresPublisherRepository(PublisherRepository):
    def __init__(self, session: Session):
        self._session = session

    def create_publisher(self, *, name: str, created_at: datetime) -> Publisher:
        orm = PublisherORM(id=uuid.uuid4(), name=name, created_at=created_at)
        # Savepoint like create_account: uq_publisher_name_lower surfaces as a
        # clean domain error instead of aborting the whole session.
        try:
            with self._session.begin_nested():
                self._session.add(orm)
                self._session.flush()
        except IntegrityError as exc:
            raise PublisherNameTakenError(name) from exc
        return _publisher_to_domain(orm)

    def get_publisher(self, publisher_id: uuid.UUID) -> Publisher | None:
        orm = self._session.get(PublisherORM, publisher_id)
        return _publisher_to_domain(orm) if orm else None

    def list_publishers(self) -> list[Publisher]:
        rows = self._session.execute(
            select(PublisherORM).order_by(sa.func.lower(PublisherORM.name))
        ).scalars()
        return [_publisher_to_domain(orm) for orm in rows]


def _audit_to_domain(orm: AdminAuditLogORM) -> AdminAuditEntry:
    return AdminAuditEntry(
        id=orm.id, occurred_at=orm.occurred_at, action=orm.action,
        actor_account_id=orm.actor_account_id, target_account_id=orm.target_account_id,
        target_invitation_id=orm.target_invitation_id,
        target_publisher_id=orm.target_publisher_id, details=dict(orm.details),
    )


class PostgresAdminAuditRepository(AdminAuditRepository):
    def __init__(self, session: Session):
        self._session = session

    def record(
        self, *, action: AdminAction, actor_account_id: uuid.UUID | None,
        occurred_at: datetime, target_account_id: uuid.UUID | None = None,
        target_invitation_id: uuid.UUID | None = None,
        target_publisher_id: uuid.UUID | None = None, details: dict | None = None,
    ) -> None:
        self._session.add(AdminAuditLogORM(
            id=uuid.uuid4(), occurred_at=occurred_at, action=action,
            actor_account_id=actor_account_id, target_account_id=target_account_id,
            target_invitation_id=target_invitation_id,
            target_publisher_id=target_publisher_id, details=details or {},
        ))
        self._session.flush()

    def list_for_target_account(self, account_id: uuid.UUID) -> list[AdminAuditEntry]:
        rows = self._session.execute(
            select(AdminAuditLogORM)
            .where(AdminAuditLogORM.target_account_id == account_id)
            .order_by(AdminAuditLogORM.occurred_at, AdminAuditLogORM.id)
        ).scalars()
        return [_audit_to_domain(orm) for orm in rows]

    def delete_older_than(self, cutoff: datetime) -> int:
        result = self._session.execute(
            sa.delete(AdminAuditLogORM).where(AdminAuditLogORM.occurred_at < cutoff)
        )
        return result.rowcount
```

- [ ] **Step 5: Exempt the new reads in the architecture test**

Add to `JURISDICTION_EXEMPT_READS` in `core/tests/graph/test_architecture.py`:

```python
    # User management (ADR-030): publishers are contract partners and the
    # audit log records administrative actions -- bookkeeping, not
    # rights-gated document content. Neither is jurisdiction-scoped.
    "PublisherRepository.get_publisher",
    "PublisherRepository.list_publishers",
    "AdminAuditRepository.list_for_target_account",
```

- [ ] **Step 6: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_publisher_and_audit_repository.py tests/graph/test_architecture.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph core/tests/graph
git commit -s -m "feat(core): add publisher and admin audit repositories" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 3: Invitation repository

**Files:**
- Modify: `core/src/normly_core/graph/domain.py`, `core/src/normly_core/graph/postgres/repositories.py`, `core/tests/graph/test_architecture.py`
- Test: `core/tests/graph/test_invitation_repository.py` (create)

**Interfaces:**
- Produces `PostgresInvitationRepository(session)`:
  - `save_invitation(*, email: str, role: Role, publisher_id: uuid.UUID | None, locale: str, token: str, invited_by: uuid.UUID | None, created_at: datetime, expires_at: datetime) -> AccountInvitation` — inserts, or replaces the row with the same `lower(email)` keeping its `id`.
  - `get_invitation(invitation_id: uuid.UUID) -> AccountInvitation | None`
  - `get_invitation_by_email(email: str) -> AccountInvitation | None` (case-insensitive)
  - `get_invitation_by_token(token: str, *, lock: bool = False) -> AccountInvitation | None`
  - `renew_invitation(invitation_id: uuid.UUID, *, token: str, expires_at: datetime) -> AccountInvitation | None`
  - `delete_invitation(invitation_id: uuid.UUID) -> bool`
  - `delete_expired_before(cutoff: datetime) -> int` — deletes rows with `expires_at < cutoff`.

- [ ] **Step 1: Write the failing tests**

`core/tests/graph/test_invitation_repository.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import (
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _save(repo, email, *, role=Role.USER, publisher_id=None, token="t1", expires_at=None):
    return repo.save_invitation(
        email=email, role=role, publisher_id=publisher_id, locale="de", token=token,
        invited_by=None, created_at=NOW, expires_at=expires_at or NOW + timedelta(days=7),
    )


def test_saving_twice_for_the_same_address_replaces_the_invitation(db_session):
    repo = PostgresInvitationRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(name="VDE Verlag", created_at=NOW)
    first = _save(repo, "Partner@vde-verlag.de", token="old")
    second = _save(repo, "partner@vde-verlag.de", role=Role.PUBLISHER,
                   publisher_id=publisher.id, token="new")

    assert second.id == first.id
    assert (second.role, second.publisher_id, second.token) == (Role.PUBLISHER, publisher.id, "new")
    assert repo.get_invitation_by_token("old") is None
    assert repo.get_invitation_by_email("PARTNER@vde-verlag.de").id == first.id


def test_renew_issues_a_new_token_and_expiry(db_session):
    repo = PostgresInvitationRepository(db_session)
    invitation = _save(repo, "renew@example.de", token="before")
    renewed = repo.renew_invitation(invitation.id, token="after", expires_at=NOW + timedelta(days=9))

    assert (renewed.token, renewed.expires_at) == ("after", NOW + timedelta(days=9))
    assert repo.get_invitation_by_token("before") is None
    assert repo.renew_invitation(uuid.uuid4(), token="x", expires_at=NOW) is None


def test_delete_and_expiry_cleanup(db_session):
    repo = PostgresInvitationRepository(db_session)
    kept = _save(repo, "kept@example.de", token="k", expires_at=NOW - timedelta(days=29))
    _save(repo, "gone@example.de", token="g", expires_at=NOW - timedelta(days=31))
    withdrawn = _save(repo, "withdrawn@example.de", token="w")

    assert repo.delete_invitation(withdrawn.id) is True
    assert repo.delete_invitation(withdrawn.id) is False
    assert repo.delete_expired_before(NOW - timedelta(days=30)) == 1
    assert repo.get_invitation(kept.id) is not None
```

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_invitation_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostgresInvitationRepository'`.

- [ ] **Step 3: Add the Protocol**

In `domain.py` after `PublisherRepository`:

```python
class InvitationRepository(Protocol):
    """
    Open and expired invitations. A row exists only until it is accepted or
    withdrawn; one row per address (case-insensitive).
    """

    def save_invitation(
        self, *, email: str, role: Role, publisher_id: uuid.UUID | None, locale: str,
        token: str, invited_by: uuid.UUID | None, created_at: datetime, expires_at: datetime,
    ) -> AccountInvitation: ...

    def get_invitation(self, invitation_id: uuid.UUID) -> AccountInvitation | None: ...

    def get_invitation_by_email(self, email: str) -> AccountInvitation | None: ...

    def get_invitation_by_token(
        self, token: str, *, lock: bool = False
    ) -> AccountInvitation | None: ...

    def renew_invitation(
        self, invitation_id: uuid.UUID, *, token: str, expires_at: datetime
    ) -> AccountInvitation | None: ...

    def delete_invitation(self, invitation_id: uuid.UUID) -> bool: ...

    def delete_expired_before(self, cutoff: datetime) -> int: ...
```

- [ ] **Step 4: Implement**

In `repositories.py` (import `AccountInvitation, InvitationRepository, Role` and `AccountInvitationORM`):

```python
def _invitation_to_domain(orm: AccountInvitationORM) -> AccountInvitation:
    return AccountInvitation(
        id=orm.id, email=orm.email, role=orm.role, publisher_id=orm.publisher_id,
        locale=orm.locale, token=orm.token, invited_by=orm.invited_by,
        created_at=orm.created_at, expires_at=orm.expires_at,
    )


class PostgresInvitationRepository(InvitationRepository):
    def __init__(self, session: Session):
        self._session = session

    def save_invitation(
        self, *, email: str, role: Role, publisher_id: uuid.UUID | None, locale: str,
        token: str, invited_by: uuid.UUID | None, created_at: datetime, expires_at: datetime,
    ) -> AccountInvitation:
        values = dict(
            email=email, role=role, publisher_id=publisher_id, locale=locale, token=token,
            invited_by=invited_by, created_at=created_at, expires_at=expires_at,
        )
        # One invitation per address: a new one replaces the old row but keeps
        # its ID, so audit entries of both refer to the same invitation.
        statement = (
            pg_insert(AccountInvitationORM)
            .values(id=uuid.uuid4(), **values)
            .on_conflict_do_update(
                index_elements=[sa.func.lower(AccountInvitationORM.email)], set_=values,
            )
            .returning(AccountInvitationORM.id)
        )
        invitation_id = self._session.execute(statement).scalar_one()
        self._session.expire_all()
        return self.get_invitation(invitation_id)

    def get_invitation(self, invitation_id: uuid.UUID) -> AccountInvitation | None:
        orm = self._session.get(AccountInvitationORM, invitation_id)
        return _invitation_to_domain(orm) if orm else None

    def get_invitation_by_email(self, email: str) -> AccountInvitation | None:
        orm = self._session.execute(
            select(AccountInvitationORM).where(
                sa.func.lower(AccountInvitationORM.email) == email.lower()
            )
        ).scalar_one_or_none()
        return _invitation_to_domain(orm) if orm else None

    def get_invitation_by_token(
        self, token: str, *, lock: bool = False
    ) -> AccountInvitation | None:
        query = select(AccountInvitationORM).where(AccountInvitationORM.token == token)
        if lock:
            # Two clicks on the same link: the second waits and then finds no row.
            query = query.with_for_update()
        orm = self._session.execute(query).scalar_one_or_none()
        return _invitation_to_domain(orm) if orm else None

    def renew_invitation(
        self, invitation_id: uuid.UUID, *, token: str, expires_at: datetime
    ) -> AccountInvitation | None:
        result = self._session.execute(
            sa.update(AccountInvitationORM)
            .where(AccountInvitationORM.id == invitation_id)
            .values(token=token, expires_at=expires_at)
        )
        if result.rowcount == 0:
            return None
        self._session.expire_all()
        return self.get_invitation(invitation_id)

    def delete_invitation(self, invitation_id: uuid.UUID) -> bool:
        result = self._session.execute(
            sa.delete(AccountInvitationORM).where(AccountInvitationORM.id == invitation_id)
        )
        return result.rowcount == 1

    def delete_expired_before(self, cutoff: datetime) -> int:
        result = self._session.execute(
            sa.delete(AccountInvitationORM).where(AccountInvitationORM.expires_at < cutoff)
        )
        return result.rowcount
```

- [ ] **Step 5: Exempt the reads**

Add to `JURISDICTION_EXEMPT_READS`:

```python
    "InvitationRepository.get_invitation",
    "InvitationRepository.get_invitation_by_email",
    "InvitationRepository.get_invitation_by_token",
```

- [ ] **Step 6: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_invitation_repository.py tests/graph/test_architecture.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/graph core/tests/graph
git commit -s -m "feat(core): add the invitation repository" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 4: Account role/block methods and the admin directory

**Files:**
- Modify: `core/src/normly_core/graph/domain.py` (`AccountRepository`, `AccountSessionRepository`, new `AdminDirectoryRepository`)
- Modify: `core/src/normly_core/graph/postgres/repositories.py`
- Modify: `core/tests/graph/test_architecture.py`
- Test: `core/tests/graph/test_admin_directory.py` (create)

**Interfaces:**
- Produces on `PostgresAccountRepository`: `set_role(account_id, *, role: Role, publisher_id: uuid.UUID | None) -> None`, `block_account(account_id, *, reason: BlockReason, blocked_at: datetime) -> None`, `unblock_account(account_id) -> None`, `lock_active_administrator_ids() -> list[uuid.UUID]` (`SELECT … FOR UPDATE` of unblocked administrators).
- Produces on `PostgresAccountSessionRepository`: `delete_sessions_for_account(account_id) -> int`.
- Produces `PostgresAdminDirectoryRepository(session)`:
  - `list_users(*, query: str | None, role: Role | None, status: str | None, sort: str, descending: bool, page: int, page_size: int, now: datetime) -> AdminUserPage`; `sort` ∈ `email, first_name, last_name, sign_in, role, publisher, last_login_at, created_at, status`; `status` ∈ `active, blocked, invited, expired`.
  - `summarize(*, now: datetime, active_since: datetime) -> AdminSummary`.

- [ ] **Step 1: Write the failing tests**

`core/tests/graph/test_admin_directory.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import BlockReason, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountGoogleIdentityRepository,
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAdminDirectoryRepository,
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _seed(db_session):
    accounts = PostgresAccountRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(
        name="DIN Media", created_at=NOW
    )
    admin = accounts.create_account(email="ops@normly.example", password_hash="x")
    accounts.set_role(admin.id, role=Role.ADMINISTRATOR, publisher_id=None)
    partner = accounts.create_account(email="lizenzen@dinmedia.example", password_hash=None)
    accounts.set_role(partner.id, role=Role.PUBLISHER, publisher_id=publisher.id)
    PostgresAccountGoogleIdentityRepository(db_session).link_google_identity(
        account_id=partner.id, google_subject_id="g-partner"
    )
    crawler = accounts.create_account(email="crawler@mailbox.example", password_hash="x")
    accounts.block_account(crawler.id, reason=BlockReason.BULK_RETRIEVAL, blocked_at=NOW)
    accounts.update_profile_names(admin.id, first_name="Jonas", last_name="Keller")
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=admin.id, session_token="s-admin", created_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=29),
    )
    invitations = PostgresInvitationRepository(db_session)
    invitations.save_invitation(
        email="partner@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id,
        locale="de", token="inv-open", invited_by=admin.id, created_at=NOW,
        expires_at=NOW + timedelta(days=7),
    )
    invitations.save_invitation(
        email="late@example.de", role=Role.USER, publisher_id=None, locale="en",
        token="inv-expired", invited_by=admin.id, created_at=NOW - timedelta(days=9),
        expires_at=NOW - timedelta(days=2),
    )
    return admin, partner, crawler, publisher


def _list(db_session, **kwargs):
    params = dict(query=None, role=None, status=None, sort="email", descending=False,
                  page=1, page_size=50, now=NOW)
    params.update(kwargs)
    return PostgresAdminDirectoryRepository(db_session).list_users(**params)


def test_lists_accounts_and_invitations_together(db_session):
    _seed(db_session)
    page = _list(db_session)

    assert page.total == 5
    by_email = {row.email: row for row in page.rows}
    assert by_email["lizenzen@dinmedia.example"].sign_in_methods == ("google",)
    assert by_email["lizenzen@dinmedia.example"].publisher_name == "DIN Media"
    assert by_email["ops@normly.example"].sign_in_methods == ("email",)
    assert by_email["crawler@mailbox.example"].status == "blocked"
    assert by_email["crawler@mailbox.example"].block_reason is BlockReason.BULK_RETRIEVAL
    assert by_email["partner@vde.example"].status == "invited"
    assert by_email["partner@vde.example"].kind == "invitation"
    assert by_email["partner@vde.example"].created_at is None
    assert by_email["late@example.de"].status == "expired"


def test_filters_search_sort_and_paging(db_session):
    _seed(db_session)
    assert [r.email for r in _list(db_session, role=Role.PUBLISHER).rows] == [
        "lizenzen@dinmedia.example", "partner@vde.example",
    ]
    assert [r.email for r in _list(db_session, status="expired").rows] == ["late@example.de"]
    assert [r.email for r in _list(db_session, query="kell").rows] == ["ops@normly.example"]
    # LIKE wildcards in the search are literal characters
    assert _list(db_session, query="%").total == 0

    newest_login_first = _list(db_session, sort="last_login_at", descending=True)
    assert newest_login_first.rows[0].email == "ops@normly.example"  # NULLs last

    second_page = _list(db_session, page=2, page_size=2)
    assert second_page.total == 5
    assert len(second_page.rows) == 2


def test_summary(db_session):
    _seed(db_session)
    summary = PostgresAdminDirectoryRepository(db_session).summarize(
        now=NOW, active_since=NOW - timedelta(days=30)
    )

    assert summary.accounts_total == 3
    assert summary.accounts_active == 1
    assert summary.accounts_by_role == {Role.USER: 1, Role.PUBLISHER: 1, Role.ADMINISTRATOR: 1}
    assert summary.publishers_with_accounts == 1
    assert summary.open_invitations == 1
    assert summary.blocked == 1
    assert summary.most_frequent_block_reason is BlockReason.BULK_RETRIEVAL


def test_lock_active_administrator_ids_ignores_blocked_ones(db_session):
    admin, _, _, _ = _seed(db_session)
    accounts = PostgresAccountRepository(db_session)
    second = accounts.create_account(email="second-admin@example.de", password_hash=None)
    accounts.set_role(second.id, role=Role.ADMINISTRATOR, publisher_id=None)
    accounts.block_account(second.id, reason=BlockReason.OTHER, blocked_at=NOW)

    assert accounts.lock_active_administrator_ids() == [admin.id]
    accounts.unblock_account(second.id)
    assert set(accounts.lock_active_administrator_ids()) == {admin.id, second.id}


def test_delete_sessions_for_account(db_session):
    admin, _, _, _ = _seed(db_session)
    sessions = PostgresAccountSessionRepository(db_session)
    assert sessions.delete_sessions_for_account(admin.id) == 1
    assert sessions.get_session_by_token("s-admin") is None
```

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_admin_directory.py -v`
Expected: FAIL with `AttributeError: 'PostgresAccountRepository' object has no attribute 'set_role'` (import of `PostgresAdminDirectoryRepository` fails first).

- [ ] **Step 3: Extend the Protocols**

Add to `AccountRepository` in `domain.py`:

```python
    def set_role(
        self, account_id: uuid.UUID, *, role: Role, publisher_id: uuid.UUID | None
    ) -> None: ...

    def block_account(
        self, account_id: uuid.UUID, *, reason: BlockReason, blocked_at: datetime
    ) -> None: ...

    def unblock_account(self, account_id: uuid.UUID) -> None: ...

    def lock_active_administrator_ids(self) -> list[uuid.UUID]:
        """Unblocked administrators, row-locked until the transaction ends."""
        ...
```

Add to `AccountSessionRepository`:

```python
    def delete_sessions_for_account(self, account_id: uuid.UUID) -> int: ...
```

New Protocol after `InvitationRepository`:

```python
class AdminDirectoryRepository(Protocol):
    """The admin table: accounts and invitations in one paged list."""

    def list_users(
        self, *, query: str | None, role: Role | None, status: str | None, sort: str,
        descending: bool, page: int, page_size: int, now: datetime,
    ) -> AdminUserPage: ...

    def summarize(self, *, now: datetime, active_since: datetime) -> AdminSummary: ...
```

- [ ] **Step 4: Implement the account and session methods**

In `PostgresAccountRepository`:

```python
    def set_role(
        self, account_id: uuid.UUID, *, role: Role, publisher_id: uuid.UUID | None
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(role=role, publisher_id=publisher_id)
        )

    def block_account(
        self, account_id: uuid.UUID, *, reason: BlockReason, blocked_at: datetime
    ) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(blocked_at=blocked_at, block_reason=reason)
        )

    def unblock_account(self, account_id: uuid.UUID) -> None:
        self._session.execute(
            sa.update(AccountORM)
            .where(AccountORM.id == account_id)
            .values(blocked_at=None, block_reason=None)
        )

    def lock_active_administrator_ids(self) -> list[uuid.UUID]:
        # FOR UPDATE: two administrators demoting each other at the same time
        # serialize here, so the second one sees that only one remains.
        return list(self._session.execute(
            select(AccountORM.id)
            .where(AccountORM.role == Role.ADMINISTRATOR, AccountORM.blocked_at.is_(None))
            .order_by(AccountORM.id)
            .with_for_update()
        ).scalars())
```

In `PostgresAccountSessionRepository`:

```python
    def delete_sessions_for_account(self, account_id: uuid.UUID) -> int:
        result = self._session.execute(
            sa.delete(AccountSessionORM).where(AccountSessionORM.account_id == account_id)
        )
        return result.rowcount
```

- [ ] **Step 5: Implement the admin directory**

In `repositories.py` (import `AdminDirectoryRepository, AdminSummary, AdminUserPage, AdminUserRow, BlockReason`):

```python
def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PostgresAdminDirectoryRepository(AdminDirectoryRepository):
    def __init__(self, session: Session):
        self._session = session

    def _union(self, now: datetime):
        google = sa.exists().where(AccountGoogleIdentityORM.account_id == AccountORM.id)
        accounts = (
            select(
                sa.literal("account").label("kind"),
                AccountORM.id.label("id"),
                AccountORM.email.label("email"),
                AccountORM.first_name.label("first_name"),
                AccountORM.last_name.label("last_name"),
                google.label("google"),
                # Without Google there is always e-mail (password or magic link).
                sa.or_(AccountORM.password_hash.is_not(None), ~google).label("email_sign_in"),
                AccountORM.role.label("role"),
                AccountORM.publisher_id.label("publisher_id"),
                PublisherORM.name.label("publisher_name"),
                AccountORM.last_login_at.label("last_login_at"),
                AccountORM.created_at.label("created_at"),
                sa.case(
                    (AccountORM.blocked_at.is_not(None), "blocked"), else_="active"
                ).label("status"),
                AccountORM.block_reason.label("block_reason"),
                sa.cast(sa.null(), sa.DateTime(timezone=True)).label("expires_at"),
            )
            .outerjoin(PublisherORM, PublisherORM.id == AccountORM.publisher_id)
        )
        invitations = (
            select(
                sa.literal("invitation"),
                AccountInvitationORM.id,
                AccountInvitationORM.email,
                sa.cast(sa.null(), sa.String),
                sa.cast(sa.null(), sa.String),
                sa.false(),
                sa.false(),
                AccountInvitationORM.role,
                AccountInvitationORM.publisher_id,
                PublisherORM.name,
                sa.cast(sa.null(), sa.DateTime(timezone=True)),
                sa.cast(sa.null(), sa.DateTime(timezone=True)),
                sa.case(
                    (AccountInvitationORM.expires_at > now, "invited"), else_="expired"
                ),
                sa.cast(sa.null(), sa.String(20)),
                AccountInvitationORM.expires_at,
            )
            .outerjoin(PublisherORM, PublisherORM.id == AccountInvitationORM.publisher_id)
        )
        return sa.union_all(accounts, invitations).subquery("directory")

    def list_users(
        self, *, query: str | None, role: Role | None, status: str | None, sort: str,
        descending: bool, page: int, page_size: int, now: datetime,
    ) -> AdminUserPage:
        u = self._union(now)
        conditions = []
        if query:
            pattern = f"%{_escape_like(query.strip())}%"
            conditions.append(sa.or_(
                u.c.email.ilike(pattern, escape="\\"),
                u.c.first_name.ilike(pattern, escape="\\"),
                u.c.last_name.ilike(pattern, escape="\\"),
            ))
        if role is not None:
            conditions.append(u.c.role == role)
        if status is not None:
            conditions.append(u.c.status == status)

        sort_columns = {
            "email": u.c.email, "first_name": u.c.first_name, "last_name": u.c.last_name,
            "sign_in": u.c.google, "role": u.c.role, "publisher": u.c.publisher_name,
            "last_login_at": u.c.last_login_at, "created_at": u.c.created_at,
            "status": u.c.status,
        }
        column = sort_columns[sort]
        ordered = (column.desc() if descending else column.asc()).nulls_last()

        total = self._session.execute(
            select(sa.func.count()).select_from(u).where(*conditions)
        ).scalar_one()
        rows = self._session.execute(
            select(u).where(*conditions).order_by(ordered, u.c.id)
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return AdminUserPage(rows=[self._row(r) for r in rows], total=total)

    @staticmethod
    def _row(r) -> AdminUserRow:
        methods = tuple(
            name for name, present in (("email", r.email_sign_in), ("google", r.google))
            if present
        )
        return AdminUserRow(
            kind=r.kind, id=r.id, email=r.email, first_name=r.first_name,
            last_name=r.last_name, sign_in_methods=methods, role=Role(r.role),
            publisher_id=r.publisher_id, publisher_name=r.publisher_name,
            last_login_at=r.last_login_at, created_at=r.created_at, status=r.status,
            block_reason=BlockReason(r.block_reason) if r.block_reason else None,
            expires_at=r.expires_at,
        )

    def summarize(self, *, now: datetime, active_since: datetime) -> AdminSummary:
        count = sa.func.count()
        accounts_total, accounts_active, blocked, publishers = self._session.execute(
            select(
                count,
                sa.func.count().filter(AccountORM.last_login_at >= active_since),
                sa.func.count().filter(AccountORM.blocked_at.is_not(None)),
                sa.func.count(sa.distinct(AccountORM.publisher_id)),
            ).select_from(AccountORM)
        ).one()
        by_role = {role: 0 for role in Role}
        for role, n in self._session.execute(
            select(AccountORM.role, count).group_by(AccountORM.role)
        ):
            by_role[role] = n
        open_invitations = self._session.execute(
            select(count).select_from(AccountInvitationORM)
            .where(AccountInvitationORM.expires_at > now)
        ).scalar_one()
        top_reason = self._session.execute(
            select(AccountORM.block_reason)
            .where(AccountORM.block_reason.is_not(None))
            .group_by(AccountORM.block_reason)
            .order_by(count.desc(), AccountORM.block_reason)
            .limit(1)
        ).scalar_one_or_none()
        return AdminSummary(
            accounts_total=accounts_total, accounts_active=accounts_active,
            accounts_by_role=by_role, publishers_with_accounts=publishers,
            open_invitations=open_invitations, blocked=blocked,
            most_frequent_block_reason=top_reason,
        )
```

Note on the union: the `role` column comes back as a plain string from the first select's processing when the enum types differ; `Role(r.role)` accepts both a `Role` and its value. If the first select's `Enum` type processes it already, `Role(Role.USER)` is still `Role.USER`.

- [ ] **Step 6: Exempt the list read**

Add to `JURISDICTION_EXEMPT_READS`:

```python
    # The admin table: account administration, not document content.
    "AdminDirectoryRepository.list_users",
```

- [ ] **Step 7: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/graph/test_admin_directory.py tests/graph/test_architecture.py tests/graph/test_account_sessions_and_deletion.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/src/normly_core/graph core/tests/graph
git commit -s -m "feat(core): add role and block methods and the admin directory" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 5: Retention for invitations and the audit log

**Files:**
- Modify: `core/src/normly_core/retention.py`
- Modify: `core/src/normly_core/pipeline/cli.py` (`_cleanup_user_data`)
- Test: `core/tests/retention/test_cleanup_user_data.py` (append)

**Interfaces:**
- Produces: `retention.INVITATION_EXPIRED_GRACE = timedelta(days=30)`, `retention.ADMIN_AUDIT_RETENTION = timedelta(days=730)`; summary line gains ` invitations={n} admin_audit={n}`.

- [ ] **Step 1: Write the failing test** (append to `core/tests/retention/test_cleanup_user_data.py`; it already imports `NullEmailSender`, `_cleanup_user_data`, `NOW`, `timedelta`)

```python
def test_cleanup_removes_old_invitations_and_audit_entries(db_session):
    from normly_core.graph.domain import AdminAction, Role
    from normly_core.graph.postgres.repositories import (
        PostgresAdminAuditRepository,
        PostgresInvitationRepository,
    )

    invitations = PostgresInvitationRepository(db_session)
    for email, expired_days_ago in (("old@example.de", 31), ("recent@example.de", 29)):
        invitations.save_invitation(
            email=email, role=Role.USER, publisher_id=None, locale="de",
            token=f"tok-{email}", invited_by=None, created_at=NOW - timedelta(days=40),
            expires_at=NOW - timedelta(days=expired_days_ago),
        )
    audit = PostgresAdminAuditRepository(db_session)
    for days in (731, 729):
        audit.record(action=AdminAction.ROLE_CHANGED, actor_account_id=None,
                     occurred_at=NOW - timedelta(days=days))

    summary = _cleanup_user_data(db_session, NOW, NullEmailSender())

    assert "invitations=1" in summary
    assert "admin_audit=1" in summary
    assert invitations.get_invitation_by_email("recent@example.de") is not None
    assert invitations.get_invitation_by_email("old@example.de") is None
```

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/retention/test_cleanup_user_data.py::test_cleanup_removes_old_invitations_and_audit_entries -v`
Expected: FAIL on `assert "invitations=1" in summary`.

- [ ] **Step 3: Add the constants**

Append to `core/src/normly_core/retention.py`:

```python
#: Expired invitations, measured from `expires_at`; open ones are never touched.
INVITATION_EXPIRED_GRACE = timedelta(days=30)

#: Administrative audit entries, measured from `occurred_at` (ADR-030).
ADMIN_AUDIT_RETENTION = timedelta(days=730)
```

- [ ] **Step 4: Extend the cleanup**

In `cli.py` import `PostgresAdminAuditRepository, PostgresInvitationRepository`. In `_cleanup_user_data`, before the deletion-log step:

```python
    invitations = PostgresInvitationRepository(session).delete_expired_before(
        now - retention.INVITATION_EXPIRED_GRACE
    )
    admin_audit = PostgresAdminAuditRepository(session).delete_older_than(
        now - retention.ADMIN_AUDIT_RETENTION
    )
```

and extend the returned string:

```python
        f"anonymous_chats={anonymous_chats} invitations={invitations} "
        f"admin_audit={admin_audit} deletion_log={log}"
```

- [ ] **Step 5: Run the retention tests**

Run: `cd core && ../.venv/bin/pytest tests/retention -v`
Expected: PASS. If `test_cleanup_user_data_command_runs_all_periods_and_commits` asserts the exact summary string, add ` invitations=0 admin_audit=0` at the right place in its expected value.

- [ ] **Step 6: Commit**

```bash
git add core/src/normly_core/retention.py core/src/normly_core/pipeline/cli.py core/tests/retention
git commit -s -m "feat(core): apply retention to invitations and the admin audit log" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 6: Mail kinds for invitation, block and removal

**Files:**
- Modify: `core/src/normly_core/notifications/mail/texts.py`, `render.py`, `__init__.py`, `templates/base.txt.j2`, `templates/base.html.j2`
- Test: `core/tests/notifications/test_mail_render.py` (append)

**Interfaces:**
- Produces:
  - `render_email(kind, locale, *, base_url, action_url=None, quote: str | None = None, **params)` — `quote` is shown as a labelled, escaped paragraph.
  - `render_bilingual_email(kind, *, base_url, action_url=None, params)` unchanged.
  - `format_days(days: int, locale: str) -> str` — `"7 Tage"` / `"7 days"`.
  - `contact_address() -> str` — `NORMLY_CONTACT_EMAIL`, else `NORMLY_IMPRINT_URL`, else `NORMLY_PUBLIC_BASE_URL`, else `"http://localhost:3000"`.
  - `ROLE_LABELS: dict[str, dict[str, str]]` in `texts.py`.
  - Kinds: `invitation` (params `role`, `publisher`, `validity`), `account_blocked` and `account_removed` (param `contact`, no button).

- [ ] **Step 1: Write the failing tests** (append to `core/tests/notifications/test_mail_render.py`; add `format_days` and `contact_address` to its import from `normly_core.notifications.mail`)

```python
@pytest.mark.parametrize("locale", ["de", "en"])
def test_invitation_renders_role_publisher_and_the_escaped_personal_message(locale):
    mail = render_email(
        "invitation", locale, base_url="https://app.example.org", action_url=ACTION,
        quote="Hallo <b>Team</b>\nwie besprochen", role="Publisher",
        publisher=" für VDE Verlag" if locale == "de" else " for VDE Verlag",
        validity=format_days(7, locale),
    )
    assert "VDE Verlag" in mail.text and "Publisher" in mail.text
    assert "Hallo <b>Team</b>" in mail.text
    assert "Hallo &lt;b&gt;Team&lt;/b&gt;" in mail.html
    assert ACTION in mail.text
    assert "{" not in mail.text


def test_mails_without_a_quote_show_no_quote_label():
    mail = render_email("magic_link", "de", base_url=None, action_url=ACTION, validity="15 Minuten")
    assert "Persönliche Nachricht" not in mail.text


@pytest.mark.parametrize("kind", ["account_blocked", "account_removed"])
@pytest.mark.parametrize("locale", ["de", "en"])
def test_account_notices_name_the_contact_and_have_no_button(kind, locale):
    mail = render_email(kind, locale, base_url=None, contact="support@normly.example")
    assert "support@normly.example" in mail.text
    # The fallback-link sentence is rendered only together with a button.
    assert COMMON[locale]["fallback_link"] not in mail.text
    assert "{" not in mail.text


def test_account_notice_bilingual():
    mail = render_bilingual_email(
        "account_blocked", base_url=None,
        params={"de": {"contact": "a@b.example"}, "en": {"contact": "a@b.example"}},
    )
    assert mail.subject == "Dein normly-Konto wurde gesperrt / Your normly account has been blocked"


def test_format_days():
    assert format_days(7, "de") == "7 Tage"
    assert format_days(1, "en") == "1 day"


def test_contact_address_prefers_the_contact_variable(monkeypatch):
    monkeypatch.setenv("NORMLY_CONTACT_EMAIL", "kontakt@normly.example")
    monkeypatch.setenv("NORMLY_IMPRINT_URL", "https://normly.example/impressum")
    assert contact_address() == "kontakt@normly.example"
    monkeypatch.delenv("NORMLY_CONTACT_EMAIL")
    assert contact_address() == "https://normly.example/impressum"
```

Also add `from normly_core.notifications.mail.texts import COMMON` to the imports of that test file.

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/notifications/test_mail_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_days'`.

- [ ] **Step 3: Add texts**

In `texts.py` add to `COMMON["de"]` `"personal_message": "Persönliche Nachricht:"` and to `COMMON["en"]` `"personal_message": "Personal message:"`. Add after `COMMON`:

```python
ROLE_LABELS: dict[str, dict[str, str]] = {
    "de": {"user": "Nutzer", "publisher": "Publisher", "administrator": "Administrator"},
    "en": {"user": "User", "publisher": "Publisher", "administrator": "Administrator"},
}
```

Add to `KINDS["de"]`:

```python
        "invitation": {
            "subject": "Einladung zu normly",
            "heading": "Du wurdest zu normly eingeladen",
            "paragraph": "Du wurdest eingeladen, normly mit der Rolle „{role}“{publisher} zu "
                         "nutzen. Mit dem Klick auf den Button nimmst du die Einladung an und "
                         "wirst angemeldet; ein bestehendes Konto mit dieser Adresse erhält "
                         "dabei die Rolle.",
            "button": "Einladung annehmen",
            "note": "Der Link ist {validity} gültig und nur einmal verwendbar. Du hast keine "
                    "Einladung erwartet? Dann ignoriere diese Mail.",
        },
        "account_blocked": {
            "subject": "Dein normly-Konto wurde gesperrt",
            "heading": "Dein Konto wurde gesperrt",
            "paragraph": "Dein normly-Konto wurde gesperrt; eine Anmeldung ist nicht mehr "
                         "möglich. Frei verfügbare Inhalte bleiben ohne Anmeldung nutzbar.",
            "button": None,
            "note": "Bei Fragen wende dich an {contact}.",
        },
        "account_removed": {
            "subject": "Dein normly-Konto wurde entfernt",
            "heading": "Dein Konto wurde entfernt",
            "paragraph": "Dein normly-Konto und die zugehörigen Daten wurden gelöscht. Frei "
                         "verfügbare Inhalte bleiben ohne Anmeldung nutzbar.",
            "button": None,
            "note": "Bei Fragen wende dich an {contact}.",
        },
```

Add to `KINDS["en"]`:

```python
        "invitation": {
            "subject": "Invitation to normly",
            "heading": "You have been invited to normly",
            "paragraph": "You have been invited to use normly with the role “{role}”"
                         "{publisher}. Clicking the button accepts the invitation and signs "
                         "you in; an existing account with this address receives the role.",
            "button": "Accept invitation",
            "note": "The link is valid for {validity} and can be used once. You did not "
                    "expect an invitation? Then ignore this email.",
        },
        "account_blocked": {
            "subject": "Your normly account has been blocked",
            "heading": "Your account has been blocked",
            "paragraph": "Your normly account has been blocked; you can no longer sign in. "
                         "Freely available content remains usable without signing in.",
            "button": None,
            "note": "If you have questions, contact {contact}.",
        },
        "account_removed": {
            "subject": "Your normly account has been removed",
            "heading": "Your account has been removed",
            "paragraph": "Your normly account and its data have been deleted. Freely "
                         "available content remains usable without signing in.",
            "button": None,
            "note": "If you have questions, contact {contact}.",
        },
```

- [ ] **Step 4: Extend the renderer**

In `render.py`:

```python
_UNITS = {
    "de": {"minute": ("Minute", "Minuten"), "hour": ("Stunde", "Stunden"), "day": ("Tag", "Tage")},
    "en": {"minute": ("minute", "minutes"), "hour": ("hour", "hours"), "day": ("day", "days")},
}


def format_days(days: int, locale: str) -> str:
    singular, plural = _UNITS[_supported(locale)]["day"]
    return f"{days} {singular if days == 1 else plural}"


def contact_address() -> str:
    """Where a blocked or removed person can turn to (ADR-030)."""
    return (
        os.environ.get("NORMLY_CONTACT_EMAIL")
        or os.environ.get("NORMLY_IMPRINT_URL")
        or os.environ.get("NORMLY_PUBLIC_BASE_URL")
        or "http://localhost:3000"
    )
```

Change `_block` to take the quote and always set both keys (the templates use `StrictUndefined`):

```python
def _block(
    kind: str, locale: str, action_url: str | None, params: dict[str, str],
    quote: str | None = None,
) -> dict:
    ...  # unchanged body up to the return
    return {
        "subject": copy["subject"],
        "heading": copy["heading"],
        "paragraph": copy["paragraph"],
        "quote": quote,
        "quote_label": COMMON[locale]["personal_message"],
        "button": copy["button"] if action_url else None,
        "action_url": action_url,
        "note": copy["note"],
        "fallback_link": COMMON[locale]["fallback_link"],
    }
```

Change `render_email`:

```python
def render_email(
    kind: str, locale: str, *, base_url: str | None, action_url: str | None = None,
    quote: str | None = None, **params: str,
) -> RenderedEmail:
    locale = _supported(locale)
    block = _block(kind, locale, action_url, params, quote)
    return _render([block], block["subject"], locale, base_url)
```

The quote is passed as a template variable, never through `str.format`, so braces in it are harmless; the HTML layout escapes it.

Export `format_days` and `contact_address` from `notifications/mail/__init__.py` next to `format_duration`.

- [ ] **Step 5: Extend the templates**

`base.txt.j2`, between the paragraph and the button block:

```jinja
{{ block.paragraph }}
{% if block.quote %}

{{ block.quote_label }}
{{ block.quote }}
{% endif %}
{% if block.button %}
```

`base.html.j2`, directly after the `{{ block.paragraph }}` line:

```jinja
{% if block.quote %}
<p style="margin:0 0 24px;padding:12px 16px;border-left:3px solid {{ tokens.border }};font-size:15px;line-height:24px;white-space:pre-line"><span style="display:block;font-size:13px;color:{{ tokens.muted_foreground }}">{{ block.quote_label }}</span>{{ block.quote }}</p>
{% endif %}
```

- [ ] **Step 6: Run the mail tests**

Run: `cd core && ../.venv/bin/pytest tests/notifications -v`
Expected: PASS (the existing parametrized tests still pass: `quote` defaults to `None`).

- [ ] **Step 7: Commit**

```bash
git add core/src/normly_core/notifications core/tests/notifications
git commit -s -m "feat(core): add invitation, block and removal mails" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 7: Capability guard, block enforcement and session fields

**Files:**
- Create: `accounts/src/normly_accounts/permissions.py`
- Create: `accounts/tests/admin_support.py`
- Modify: `accounts/src/normly_accounts/dependencies.py`, `routers/session.py`, `routers/login.py`, `routers/magic_link.py`, `routers/password_reset.py`, `routers/google.py`, `schemas.py`
- Test: `accounts/tests/test_blocked_accounts.py` (create), `accounts/tests/test_permissions.py` (create)

**Interfaces:**
- Produces:
  - `permissions.MATRIX_ROLES = ("anonymous", "user", "publisher", "administrator")`, `permissions.Capability(key, planned, values)`, `permissions.CAPABILITIES`, `permissions.USER_MANAGEMENT = "user_management"`, `permissions.allows(role: Role, key: str) -> bool`.
  - `dependencies.require_capability(key: str)` → a FastAPI dependency returning the current `Account`; 401 without a valid session, 403 `"forbidden"` without the capability.
  - `SessionValidationResponse` gains `role: str`, `publisher_id: uuid.UUID | None`.
  - Session creation for a blocked account raises `HTTPException(403, "account_blocked")`.
  - Test helpers in `accounts/tests/admin_support.py`: `make_account`, `make_publisher`, `auth_headers`, `make_admin`.

- [ ] **Step 1: Write the test helpers**

`accounts/tests/admin_support.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Builds accounts in a given state directly through the repositories."""

from datetime import datetime, timedelta, timezone

from normly_core.graph.domain import Account, BlockReason, Publisher, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresPublisherRepository,
)

from normly_accounts.security import generate_token, hash_password


def make_publisher(db_session, name: str = "VDE Verlag") -> Publisher:
    return PostgresPublisherRepository(db_session).create_publisher(
        name=name, created_at=datetime.now(timezone.utc)
    )


def make_account(
    db_session, email: str, *, role: Role = Role.USER, publisher_id=None,
    password: str | None = None, blocked: bool = False, locale: str = "de",
) -> Account:
    repo = PostgresAccountRepository(db_session)
    account = repo.create_account(
        email=email, password_hash=hash_password(password) if password else None, locale=locale,
    )
    if role is not Role.USER:
        repo.set_role(account.id, role=role, publisher_id=publisher_id)
    if blocked:
        repo.block_account(account.id, reason=BlockReason.ABUSE, blocked_at=datetime.now(timezone.utc))
    db_session.flush()
    return repo.get_account_by_id(account.id)


def auth_headers(db_session, account: Account) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = generate_token()
    PostgresAccountSessionRepository(db_session).create_session(
        account_id=account.id, session_token=token, created_at=now,
        expires_at=now + timedelta(days=30),
    )
    db_session.flush()
    return {"Authorization": f"Bearer {token}"}


def make_admin(db_session, email: str = "admin@normly.example") -> tuple[Account, dict[str, str]]:
    admin = make_account(db_session, email, role=Role.ADMINISTRATOR)
    return admin, auth_headers(db_session, admin)
```

- [ ] **Step 2: Write the failing tests**

`accounts/tests/test_permissions.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import Role

from normly_accounts.permissions import CAPABILITIES, MATRIX_ROLES, USER_MANAGEMENT, allows


def test_only_administrators_may_manage_users():
    assert allows(Role.ADMINISTRATOR, USER_MANAGEMENT)
    assert not allows(Role.PUBLISHER, USER_MANAGEMENT)
    assert not allows(Role.USER, USER_MANAGEMENT)


def test_every_capability_names_every_matrix_role():
    for capability in CAPABILITIES:
        assert set(capability.values) == set(MATRIX_ROLES), capability.key


def test_nobody_sees_chats_or_personal_usage_data_of_others():
    by_key = {c.key: c for c in CAPABILITIES}
    for key in ("chats_of_others", "personal_usage_data_of_others"):
        assert set(by_key[key].values.values()) == {"no"}
```

`accounts/tests/test_blocked_accounts.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import AccountTokenPurpose, Role
from normly_core.graph.postgres.repositories import PostgresAccountTokenRepository

from tests.admin_support import auth_headers, make_account, make_publisher


def test_session_reports_role_and_publisher(client, db_session):
    publisher = make_publisher(db_session)
    account = make_account(db_session, "p@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id)
    body = client.get("/v1/accounts/session", headers=auth_headers(db_session, account)).json()
    assert body["role"] == "publisher"
    assert body["publisher_id"] == str(publisher.id)


def test_a_blocked_account_has_no_valid_session(client, db_session):
    account = make_account(db_session, "blocked@example.de", blocked=True)
    headers = auth_headers(db_session, account)
    assert client.get("/v1/accounts/session", headers=headers).status_code == 401
    assert client.get("/v1/accounts/export", headers=headers).status_code == 401


def test_password_login_of_a_blocked_account_is_refused(client, db_session):
    make_account(db_session, "blocked-pw@example.de", password="correct horse", blocked=True)
    response = client.post(
        "/v1/accounts/login", json={"email": "blocked-pw@example.de", "password": "correct horse"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "account_blocked"


def test_a_wrong_password_still_answers_401_for_a_blocked_account(client, db_session):
    make_account(db_session, "blocked-pw2@example.de", password="correct horse", blocked=True)
    response = client.post(
        "/v1/accounts/login", json={"email": "blocked-pw2@example.de", "password": "wrong"}
    )
    assert response.status_code == 401


def test_magic_link_and_reset_requests_send_nothing_for_a_blocked_account(
    client, db_session, email_sender
):
    make_account(db_session, "blocked-ml@example.de", blocked=True)
    for path in ("/v1/accounts/magic-link/request", "/v1/accounts/password-reset/request"):
        response = client.post(path, json={"email": "blocked-ml@example.de"})
        assert response.status_code == 200
    assert email_sender.sent == []


def test_magic_link_confirm_of_a_blocked_account_is_refused(client, db_session):
    from datetime import datetime, timedelta, timezone

    account = make_account(db_session, "blocked-ml2@example.de", blocked=True)
    now = datetime.now(timezone.utc)
    PostgresAccountTokenRepository(db_session).create_token(
        account_id=account.id, purpose=AccountTokenPurpose.MAGIC_LINK, token="ml-blocked",
        created_at=now, expires_at=now + timedelta(minutes=15),
    )
    response = client.post("/v1/accounts/magic-link/confirm", json={"token": "ml-blocked"})
    assert response.status_code == 403
    assert response.json()["detail"] == "account_blocked"
```

Append to `accounts/tests/test_google_login.py` (it already defines `_override_google_client` and `_seed_state`):

```python
def test_google_callback_refuses_a_blocked_account_without_linking_it(client, db_session):
    from normly_core.graph.postgres.repositories import PostgresAccountGoogleIdentityRepository
    from tests.admin_support import make_account

    account = make_account(db_session, "blocked-google@example.de", blocked=True)
    _override_google_client(
        client.app, GoogleProfile(
            subject_id="google-sub-blocked", email="blocked-google@example.de",
            email_verified=True,
        )
    )
    _seed_state(db_session, "blocked-state")

    response = client.get(
        "/v1/accounts/google/callback", params={"code": "fake-code", "state": "blocked-state"}
    )

    assert (response.status_code, response.json()["detail"]) == (403, "account_blocked")
    assert not PostgresAccountGoogleIdentityRepository(db_session).has_google_identity(account.id)
```

- [ ] **Step 3: Run and see it fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_permissions.py tests/test_blocked_accounts.py -v`
Expected: FAIL (`ModuleNotFoundError: normly_accounts.permissions`, then `KeyError: 'role'`, 200 instead of 401/403).

- [ ] **Step 4: Write the capability matrix**

`accounts/src/normly_accounts/permissions.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
What each role may do -- the one definition both the server-side guard and the
"What the roles see" dialog read, so the two cannot drift apart (ADR-030).

Values: "yes", "no", "own" (only the person's own data), "own_aggregated"
(only the publisher's own content, aggregated, never per person), "all".
Planned capabilities are shown in the dialog but guard nothing yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from normly_core.graph.domain import Role

MATRIX_ROLES = ("anonymous", "user", "publisher", "administrator")
USER_MANAGEMENT = "user_management"


@dataclass(frozen=True)
class Capability:
    key: str
    planned: bool
    values: dict[str, str]


def _row(key: str, anonymous: str, user: str, publisher: str, administrator: str,
         *, planned: bool = False) -> Capability:
    return Capability(key=key, planned=planned, values={
        "anonymous": anonymous, "user": user, "publisher": publisher,
        "administrator": administrator,
    })


CAPABILITIES: tuple[Capability, ...] = (
    _row("search_and_free_content", "yes", "yes", "yes", "yes"),
    # Anonymous chats are not stored; the conversation lives in the tab (ADR-027).
    _row("chat_and_history", "no", "own", "own", "own"),
    _row("chats_of_others", "no", "no", "no", "no"),
    _row("personal_usage_data_of_others", "no", "no", "no", "no"),
    _row("usage_and_demand", "no", "no", "own_aggregated", "all", planned=True),
    _row("deliveries", "no", "no", "own", "all", planned=True),
    _row("billing", "no", "no", "own", "all", planned=True),
    _row(USER_MANAGEMENT, "no", "no", "no", "yes"),
)

_BY_KEY = {capability.key: capability for capability in CAPABILITIES}


def allows(role: Role, key: str) -> bool:
    capability = _BY_KEY[key]
    return not capability.planned and capability.values[role.value] != "no"
```

- [ ] **Step 5: Guard and block checks in `dependencies.py`**

Replace the end of `get_current_account` and add `require_capability`:

```python
    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    if account.blocked_at is not None:
        # Blocking deletes all sessions; this also covers a session created
        # in the moment between the block and that deletion.
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return account


def require_capability(key: str):
    """
    Dependency factory: the current account must hold `key` per
    permissions.CAPABILITIES. The role comes from the database on every
    request, so a downgrade or block takes effect on the next one.
    """
    def dependency(account: Account = Depends(get_current_account)) -> Account:
        if not allows(account.role, key):
            raise HTTPException(status_code=403, detail="forbidden")
        return account

    return dependency
```

(import `from normly_accounts.permissions import allows`).

- [ ] **Step 6: Session validation**

In `routers/session.py`, after loading `account`:

```python
    account = PostgresAccountRepository(session).get_account_by_id(account_session.account_id)
    if account.blocked_at is not None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return SessionValidationResponse(
        account_id=account.id, email=account.email,
        first_name=account.first_name, last_name=account.last_name,
        has_avatar=account.avatar_image is not None,
        has_password=account.password_hash is not None,
        notification_preference=account.notification_preference.value,
        role=account.role.value, publisher_id=account.publisher_id,
    )
```

In `schemas.py` add to `SessionValidationResponse`:

```python
    # Read by the frontend to show the administrator menu; the server checks
    # the role again on every admin request.
    role: str
    publisher_id: uuid.UUID | None
```

- [ ] **Step 7: Refuse session creation for blocked accounts**

In `routers/login.py`, at the top of `_create_session_response`:

```python
def _create_session_response(account: Account, session: Session) -> SessionResponse:
    # Every sign-in path ends here (password, magic link, Google, registration,
    # invitation), so this one check refuses a blocked account on all of them.
    if account.blocked_at is not None:
        raise HTTPException(status_code=403, detail="account_blocked")
    now = datetime.now(timezone.utc)
    ...
```

In `routers/google.py`, inside the `if existing is not None:` branch, before the `email_verified` check:

```python
            if existing.blocked_at is not None:
                # Refuse before linking: a blocked account gains no new sign-in path.
                raise HTTPException(status_code=403, detail="account_blocked")
```

In `routers/magic_link.py::request_magic_link`, right after loading `account`:

```python
    if account is not None and account.blocked_at is not None:
        # Same neutral answer as for any address: no token, no mail.
        return {"status": "if_the_request_is_valid_an_email_was_sent"}
```

In `routers/password_reset.py::request_password_reset`, change the condition:

```python
    if account is not None and account.blocked_at is None:
```

- [ ] **Step 8: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: all PASS (whole suite: the session response change must not break existing tests).

- [ ] **Step 9: Commit**

```bash
git add accounts/src accounts/tests
git commit -s -m "feat(accounts): enforce blocks and expose the role in the session" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 8: Admin rules, mails, publishers and invitations API

**Files:**
- Create: `accounts/src/normly_accounts/admin_rules.py`, `admin_mail.py`, `admin_schemas.py`, `routers/admin_publishers.py`, `routers/admin_invitations.py`
- Modify: `accounts/src/normly_accounts/main.py`, `accounts/tests/test_openapi_and_end_to_end.py`
- Test: `accounts/tests/test_admin_invitations.py` (create)

**Interfaces:**
- Consumes: `require_capability`, `USER_MANAGEMENT`, repositories from Tasks 2–4, `render_email`, `render_bilingual_email`, `format_days`, `contact_address`, `ROLE_LABELS`.
- Produces:
  - `admin_rules.snapshot(account) -> dict`, `target_account_or_404(session, account_id) -> Account`, `ensure_not_self(admin, target)`, `ensure_administrator_remains(session, target)`, `publisher_or_400(session, publisher_id) -> Publisher | None`.
  - `admin_mail.INVITATION_LIFETIME_DAYS = 7`, `admin_mail.public_base_url() -> str`, `send_invitation(sender, invitation, *, publisher_name: str | None, message: str | None) -> bool`, `send_account_notice(sender, kind: str, *, email: str, locale: str | None) -> bool`.
  - Endpoints: `GET/POST /v1/admin/publishers`, `GET /v1/admin/invitations/check`, `POST /v1/admin/invitations`, `POST /v1/admin/invitations/{invitation_id}/resend`, `DELETE /v1/admin/invitations/{invitation_id}`.

- [ ] **Step 1: Write the failing tests**

`accounts/tests/test_admin_invitations.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest
import sqlalchemy as sa

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import auth_headers, make_account, make_admin, make_publisher

ADMIN_ENDPOINTS = [
    ("GET", "/v1/admin/publishers", None),
    ("POST", "/v1/admin/publishers", {"name": "X"}),
    ("GET", "/v1/admin/invitations/check?email=a@b.example", None),
    ("POST", "/v1/admin/invitations", {"email": "a@b.example", "role": "user"}),
]


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ENDPOINTS)
def test_admin_endpoints_need_an_administrator(client, db_session, method, path, body):
    assert client.request(method, path, json=body).status_code == 401
    for role in (Role.USER, Role.PUBLISHER):
        publisher_id = make_publisher(db_session, f"P-{role.value}").id if role is Role.PUBLISHER else None
        account = make_account(db_session, f"{role.value}@example.de", role=role, publisher_id=publisher_id)
        response = client.request(method, path, json=body, headers=auth_headers(db_session, account))
        assert response.status_code == 403


def test_create_and_list_publishers(client, db_session):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/publishers", json={"name": "  DIN Media  "}, headers=headers)
    assert created.status_code == 201
    assert created.json()["name"] == "DIN Media"
    duplicate = client.post("/v1/admin/publishers", json={"name": "din media"}, headers=headers)
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "publisher_name_taken")
    assert [p["name"] for p in client.get("/v1/admin/publishers", headers=headers).json()] == ["DIN Media"]


def test_invite_a_publisher_sends_the_mail_with_the_personal_message(client, db_session, email_sender):
    admin, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    response = client.post("/v1/admin/invitations", headers=headers, json={
        "email": "partner@vde.example", "role": "publisher", "publisher_id": str(publisher.id),
        "locale": "de", "message": "Wie besprochen.",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["email_sent"] is True and body["role"] == "publisher"
    invitation = PostgresInvitationRepository(db_session).get_invitation_by_email("partner@vde.example")
    [mail] = email_sender.sent
    assert mail["to"] == "partner@vde.example"
    assert f"/invitation?token={invitation.token}" in mail["body"]
    assert "Wie besprochen." in mail["body"] and "VDE Verlag" in mail["body"]
    assert PostgresAdminAuditRepository(db_session).list_for_target_account(admin.id) == []


@pytest.mark.parametrize("payload", [
    {"email": "x@example.de", "role": "publisher"},  # missing publisher
    {"email": "x@example.de", "role": "user", "publisher_id": "00000000-0000-0000-0000-000000000001"},
    {"email": "x@example.de", "role": "user", "message": "x" * 501},
    {"email": "x@example.de", "role": "publisher", "publisher_id": "00000000-0000-0000-0000-000000000001"},
])
def test_invalid_invitations_are_rejected_with_400(client, db_session, payload):
    _, headers = make_admin(db_session)
    assert client.post("/v1/admin/invitations", json=payload, headers=headers).status_code == 400


def test_a_blocked_account_cannot_be_invited(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "blocked@example.de", blocked=True)
    response = client.post("/v1/admin/invitations", headers=headers,
                           json={"email": "blocked@example.de", "role": "user"})
    assert (response.status_code, response.json()["detail"]) == (409, "account_blocked")


def test_check_reports_existing_account_and_open_invitation(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "known@example.de")
    client.post("/v1/admin/invitations", headers=headers, json={"email": "known@example.de", "role": "user"})
    body = client.get("/v1/admin/invitations/check?email=known@example.de", headers=headers).json()
    assert body == {"existing_account": True, "blocked": False, "open_invitation": True}


def test_resend_replaces_the_token_and_sends_no_personal_message(client, db_session, email_sender):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/invitations", headers=headers, json={
        "email": "again@example.de", "role": "user", "message": "Erste Nachricht",
    }).json()
    repo = PostgresInvitationRepository(db_session)
    old_token = repo.get_invitation(created["id"]).token

    response = client.post(f"/v1/admin/invitations/{created['id']}/resend", headers=headers)

    assert response.status_code == 200
    assert repo.get_invitation_by_token(old_token) is None
    assert "Erste Nachricht" not in email_sender.sent[-1]["body"]


def test_withdraw_deletes_the_invitation_and_is_audited(client, db_session):
    _, headers = make_admin(db_session)
    created = client.post("/v1/admin/invitations", headers=headers,
                          json={"email": "gone@example.de", "role": "user"}).json()
    assert client.delete(f"/v1/admin/invitations/{created['id']}", headers=headers).status_code == 204
    assert client.delete(f"/v1/admin/invitations/{created['id']}", headers=headers).status_code == 404
    actions = [
        row[0] for row in db_session.execute(
            sa.text(
                "SELECT action FROM admin_audit_log WHERE target_invitation_id = :i "
                "ORDER BY occurred_at"
            ), {"i": created["id"]},
        )
    ]
    assert actions == [AdminAction.INVITATION_CREATED.value, AdminAction.INVITATION_WITHDRAWN.value]


def test_a_failing_mail_relay_keeps_the_invitation(client, db_session):
    from normly_accounts.dependencies import get_email_sender

    class Raising:
        def send(self, **kwargs):
            raise OSError("simulated SMTP outage")

    client.app.dependency_overrides[get_email_sender] = lambda: Raising()
    _, headers = make_admin(db_session)
    response = client.post("/v1/admin/invitations", headers=headers,
                           json={"email": "nomail@example.de", "role": "user"})
    assert response.status_code == 201
    assert response.json()["email_sent"] is False
```

- [ ] **Step 2: Run and see it fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_admin_invitations.py -v`
Expected: FAIL with 404 for every admin path.

- [ ] **Step 3: Shared rules**

`accounts/src/normly_accounts/admin_rules.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Checks every administrative change shares (ADR-030)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, Publisher, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresPublisherRepository,
)


def snapshot(account: Account) -> dict[str, str | None]:
    """Role and binding for the audit log -- IDs only, never the address."""
    return {
        "role": account.role.value,
        "publisher_id": str(account.publisher_id) if account.publisher_id else None,
    }


def target_account_or_404(session: Session, account_id: uuid.UUID) -> Account:
    account = PostgresAccountRepository(session).get_account_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


def ensure_not_self(admin: Account, target: Account) -> None:
    if admin.id == target.id:
        raise HTTPException(status_code=409, detail="self_action")


def ensure_administrator_remains(session: Session, target: Account) -> None:
    """Call before anything that ends `target`'s active administrator status."""
    if target.role is not Role.ADMINISTRATOR or target.blocked_at is not None:
        return
    others = [
        account_id
        for account_id in PostgresAccountRepository(session).lock_active_administrator_ids()
        if account_id != target.id
    ]
    if not others:
        raise HTTPException(status_code=409, detail="last_administrator")


def publisher_or_400(session: Session, publisher_id: uuid.UUID | None) -> Publisher | None:
    if publisher_id is None:
        return None
    publisher = PostgresPublisherRepository(session).get_publisher(publisher_id)
    if publisher is None:
        raise HTTPException(status_code=400, detail="unknown publisher")
    return publisher
```

- [ ] **Step 4: Mail helpers**

`accounts/src/normly_accounts/admin_mail.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Mails of the user management. Sending never fails the administrative action."""

from __future__ import annotations

import logging
import os

from normly_core.graph.domain import AccountInvitation
from normly_core.notifications.email import EmailSender
from normly_core.notifications.mail import (
    contact_address, format_days, render_bilingual_email, render_email,
)
from normly_core.notifications.mail.texts import ROLE_LABELS

logger = logging.getLogger(__name__)

INVITATION_LIFETIME_DAYS = 7
_PUBLISHER_CLAUSE = {"de": " für {name}", "en": " for {name}"}


def public_base_url() -> str:
    return os.environ.get("NORMLY_PUBLIC_BASE_URL", "http://localhost:3000")


def _send(sender: EmailSender, *, to: str, mail) -> bool:
    try:
        sender.send(to=to, subject=mail.subject, body=mail.text, html=mail.html)
    except Exception:
        # Never log the token or the address' mail body.
        logger.exception("user management email delivery failed")
        return False
    return True


def send_invitation(
    sender: EmailSender, invitation: AccountInvitation, *, publisher_name: str | None,
    message: str | None,
) -> bool:
    locale = invitation.locale
    mail = render_email(
        "invitation", locale, base_url=public_base_url(),
        action_url=f"{public_base_url()}/invitation?token={invitation.token}",
        quote=message or None,
        role=ROLE_LABELS[locale][invitation.role.value],
        publisher=_PUBLISHER_CLAUSE[locale].format(name=publisher_name) if publisher_name else "",
        validity=format_days(INVITATION_LIFETIME_DAYS, locale),
    )
    return _send(sender, to=invitation.email, mail=mail)


def send_account_notice(
    sender: EmailSender, kind: str, *, email: str, locale: str | None
) -> bool:
    contact = contact_address()
    if locale is None:
        mail = render_bilingual_email(
            kind, base_url=public_base_url(),
            params={"de": {"contact": contact}, "en": {"contact": contact}},
        )
    else:
        mail = render_email(kind, locale, base_url=public_base_url(), contact=contact)
    return _send(sender, to=email, mail=mail)
```

- [ ] **Step 5: Schemas**

`accounts/src/normly_accounts/admin_schemas.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from normly_core.graph.domain import BlockReason, Role

Locale = Literal["de", "en"]
PublisherName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreatePublisherRequest(BaseModel):
    name: PublisherName


class PublisherResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class InvitationCheckResponse(BaseModel):
    existing_account: bool
    blocked: bool
    open_invitation: bool


def _binding_is_consistent(role: Role, publisher_id: uuid.UUID | None) -> None:
    if (role is Role.PUBLISHER) != (publisher_id is not None):
        raise ValueError("a publisher_id is required for the publisher role and only for it")


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: Role
    publisher_id: uuid.UUID | None = None
    locale: Locale = "de"
    message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_binding(self) -> "CreateInvitationRequest":
        _binding_is_consistent(self.role, self.publisher_id)
        return self


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    publisher_id: uuid.UUID | None
    expires_at: datetime
    email_sent: bool


class EmailSentResponse(BaseModel):
    email_sent: bool


class UpdateAccountRequest(BaseModel):
    role: Role | None = None
    publisher_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "UpdateAccountRequest":
        if (self.role is None) == (self.publisher_id is None):
            raise ValueError("send either role or publisher_id")
        return self


class BlockAccountRequest(BaseModel):
    reason: BlockReason


class RemoveAccountRequest(BaseModel):
    confirm_email: str


class AdminUserResponse(BaseModel):
    kind: Literal["account", "invitation"]
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    sign_in_methods: list[str]
    role: Role
    publisher_id: uuid.UUID | None
    publisher_name: str | None
    last_login_at: datetime | None
    created_at: datetime | None
    status: Literal["active", "blocked", "invited", "expired"]
    block_reason: BlockReason | None
    expires_at: datetime | None


class AdminUserPageResponse(BaseModel):
    rows: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminSummaryResponse(BaseModel):
    accounts_total: int
    accounts_active_30_days: int
    accounts_by_role: dict[str, int]
    publishers_with_accounts: int
    open_invitations: int
    blocked: int
    most_frequent_block_reason: BlockReason | None


class RoleMatrixRow(BaseModel):
    capability: str
    planned: bool
    values: dict[str, str]


class RoleMatrixResponse(BaseModel):
    roles: list[str]
    rows: list[RoleMatrixRow]
```

- [ ] **Step 6: Publishers router**

`accounts/src/normly_accounts/routers/admin_publishers.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AdminAction, PublisherNameTakenError
from normly_core.graph.postgres.repositories import (
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

from normly_accounts.admin_schemas import CreatePublisherRequest, PublisherResponse
from normly_accounts.dependencies import get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT

admin_publishers_router = APIRouter(prefix="/v1/admin/publishers", tags=["admin"])


@admin_publishers_router.get("", response_model=list[PublisherResponse])
def list_publishers(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> list[PublisherResponse]:
    return [
        PublisherResponse(id=p.id, name=p.name, created_at=p.created_at)
        for p in PostgresPublisherRepository(session).list_publishers()
    ]


@admin_publishers_router.post("", response_model=PublisherResponse, status_code=201)
def create_publisher(
    payload: CreatePublisherRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> PublisherResponse:
    now = datetime.now(timezone.utc)
    try:
        publisher = PostgresPublisherRepository(session).create_publisher(
            name=payload.name, created_at=now
        )
    except PublisherNameTakenError:
        raise HTTPException(status_code=409, detail="publisher_name_taken")
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.PUBLISHER_CREATED, actor_account_id=admin.id, occurred_at=now,
        target_publisher_id=publisher.id,
    )
    session.commit()
    return PublisherResponse(id=publisher.id, name=publisher.name, created_at=publisher.created_at)
```

- [ ] **Step 7: Invitations router**

`accounts/src/normly_accounts/routers/admin_invitations.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import EmailStr
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AccountInvitation, AdminAction
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
    PostgresPublisherRepository,
)
from normly_core.notifications.email import EmailSender

from normly_accounts.admin_mail import INVITATION_LIFETIME_DAYS, send_invitation
from normly_accounts.admin_rules import publisher_or_400
from normly_accounts.admin_schemas import (
    CreateInvitationRequest, InvitationCheckResponse, InvitationResponse,
)
from normly_accounts.dependencies import get_email_sender, get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT
from normly_accounts.security import generate_token

admin_invitations_router = APIRouter(prefix="/v1/admin/invitations", tags=["admin"])

_LIFETIME = timedelta(days=INVITATION_LIFETIME_DAYS)


def _response(invitation: AccountInvitation, email_sent: bool) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id, email=invitation.email, role=invitation.role,
        publisher_id=invitation.publisher_id, expires_at=invitation.expires_at,
        email_sent=email_sent,
    )


def _refuse_blocked(session: Session, email: str) -> Account | None:
    account = PostgresAccountRepository(session).get_account_by_email(email)
    if account is not None and account.blocked_at is not None:
        raise HTTPException(status_code=409, detail="account_blocked")
    return account


@admin_invitations_router.get("/check", response_model=InvitationCheckResponse)
def check_invitation(
    email: EmailStr,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> InvitationCheckResponse:
    account = PostgresAccountRepository(session).get_account_by_email(email)
    invitation = PostgresInvitationRepository(session).get_invitation_by_email(email)
    return InvitationCheckResponse(
        existing_account=account is not None,
        blocked=account is not None and account.blocked_at is not None,
        open_invitation=invitation is not None
        and invitation.expires_at > datetime.now(timezone.utc),
    )


@admin_invitations_router.post("", response_model=InvitationResponse, status_code=201)
def create_invitation(
    payload: CreateInvitationRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> InvitationResponse:
    publisher = publisher_or_400(session, payload.publisher_id)
    account = _refuse_blocked(session, payload.email)
    now = datetime.now(timezone.utc)
    invitation = PostgresInvitationRepository(session).save_invitation(
        email=payload.email, role=payload.role, publisher_id=payload.publisher_id,
        locale=payload.locale, token=generate_token(), invited_by=admin.id,
        created_at=now, expires_at=now + _LIFETIME,
    )
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_CREATED, actor_account_id=admin.id, occurred_at=now,
        target_account_id=account.id if account else None,
        target_invitation_id=invitation.id, target_publisher_id=payload.publisher_id,
        details={
            "role": payload.role.value, "locale": payload.locale,
            "publisher_id": str(payload.publisher_id) if payload.publisher_id else None,
        },
    )
    # Durable before the mail goes out: a link must never point to a token
    # that a failed commit threw away. The message itself is never stored.
    session.commit()
    sent = send_invitation(
        email_sender, invitation, publisher_name=publisher.name if publisher else None,
        message=payload.message,
    )
    return _response(invitation, sent)


@admin_invitations_router.post("/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(
    invitation_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> InvitationResponse:
    repo = PostgresInvitationRepository(session)
    invitation = repo.get_invitation(invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="invitation not found")
    account = _refuse_blocked(session, invitation.email)
    now = datetime.now(timezone.utc)
    renewed = repo.renew_invitation(invitation_id, token=generate_token(), expires_at=now + _LIFETIME)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_RESENT, actor_account_id=admin.id, occurred_at=now,
        target_account_id=account.id if account else None, target_invitation_id=invitation_id,
    )
    session.commit()
    publisher = (
        PostgresPublisherRepository(session).get_publisher(renewed.publisher_id)
        if renewed.publisher_id else None
    )
    sent = send_invitation(
        email_sender, renewed, publisher_name=publisher.name if publisher else None, message=None,
    )
    return _response(renewed, sent)


@admin_invitations_router.delete("/{invitation_id}", status_code=204)
def withdraw_invitation(
    invitation_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    if not PostgresInvitationRepository(session).delete_invitation(invitation_id):
        raise HTTPException(status_code=404, detail="invitation not found")
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_WITHDRAWN, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_invitation_id=invitation_id,
    )
    session.commit()
    return Response(status_code=204)
```

- [ ] **Step 8: Register the routers and update the OpenAPI test**

In `main.py` import and add:

```python
    app.include_router(admin_publishers_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(admin_invitations_router, responses=COMMON_ERROR_RESPONSES)
```

In `accounts/tests/test_openapi_and_end_to_end.py` add to the expected set:

```python
        "/v1/admin/publishers",
        "/v1/admin/invitations",
        "/v1/admin/invitations/check",
        "/v1/admin/invitations/{invitation_id}/resend",
        "/v1/admin/invitations/{invitation_id}",
```

- [ ] **Step 9: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest tests/test_admin_invitations.py tests/test_openapi_and_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add accounts/src accounts/tests
git commit -s -m "feat(accounts): add publisher and invitation admin endpoints" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 9: Account administration, list, summary and role matrix

**Files:**
- Create: `accounts/src/normly_accounts/routers/admin_accounts.py`, `routers/admin_users.py`
- Modify: `accounts/src/normly_accounts/main.py`, `accounts/tests/test_openapi_and_end_to_end.py`
- Test: `accounts/tests/test_admin_accounts.py` (create), `accounts/tests/test_admin_users.py` (create)

**Interfaces:**
- Consumes: Task 8 modules.
- Produces: `PATCH /v1/admin/accounts/{account_id}` (204), `POST …/block` (`EmailSentResponse`), `POST …/unblock` (204), `DELETE /v1/admin/accounts/{account_id}` (`EmailSentResponse`), `GET /v1/admin/users`, `GET /v1/admin/users/summary`, `GET /v1/admin/role-matrix`.

- [ ] **Step 1: Write the failing account tests**

`accounts/tests/test_admin_accounts.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import sqlalchemy as sa

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import PostgresAccountRepository

from tests.admin_support import auth_headers, make_account, make_admin, make_publisher


def _actions(db_session, account_id):
    return [r[0] for r in db_session.execute(sa.text(
        "SELECT action FROM admin_audit_log WHERE target_account_id = :a ORDER BY occurred_at"
    ), {"a": account_id})]


def test_downgrade_to_user_takes_effect_on_the_next_request(client, db_session):
    _, headers = make_admin(db_session)
    other, other_headers = make_admin(db_session, "second@normly.example")
    assert client.get("/v1/admin/publishers", headers=other_headers).status_code == 200

    response = client.patch(f"/v1/admin/accounts/{other.id}", json={"role": "user"}, headers=headers)

    assert response.status_code == 204
    assert client.get("/v1/admin/publishers", headers=other_headers).status_code == 403
    assert _actions(db_session, other.id) == ["role_changed"]


def test_upgrades_need_an_invitation(client, db_session):
    _, headers = make_admin(db_session)
    user = make_account(db_session, "plain@example.de")
    response = client.patch(f"/v1/admin/accounts/{user.id}", json={"role": "administrator"}, headers=headers)
    assert (response.status_code, response.json()["detail"]) == (409, "upgrade_requires_invitation")


def test_change_publisher(client, db_session):
    _, headers = make_admin(db_session)
    din, vde = make_publisher(db_session, "DIN Media"), make_publisher(db_session, "VDE Verlag")
    partner = make_account(db_session, "p@example.de", role=Role.PUBLISHER, publisher_id=din.id)

    response = client.patch(f"/v1/admin/accounts/{partner.id}",
                            json={"publisher_id": str(vde.id)}, headers=headers)

    assert response.status_code == 204
    assert PostgresAccountRepository(db_session).get_account_by_id(partner.id).publisher_id == vde.id
    user = make_account(db_session, "u@example.de")
    not_publisher = client.patch(f"/v1/admin/accounts/{user.id}",
                                 json={"publisher_id": str(vde.id)}, headers=headers)
    assert (not_publisher.status_code, not_publisher.json()["detail"]) == (409, "not_a_publisher")


def test_the_own_account_is_protected(client, db_session):
    admin, headers = make_admin(db_session)
    for method, path, body in (
        ("PATCH", f"/v1/admin/accounts/{admin.id}", {"role": "user"}),
        ("POST", f"/v1/admin/accounts/{admin.id}/block", {"reason": "other"}),
        ("DELETE", f"/v1/admin/accounts/{admin.id}", {"confirm_email": admin.email}),
    ):
        response = client.request(method, path, json=body, headers=headers)
        assert (response.status_code, response.json()["detail"]) == (409, "self_action")


def test_ensure_administrator_remains(db_session):
    """
    Through the panel the acting administrator is itself active, so the rule
    only bites when two administrators act at the same time (the row lock in
    lock_active_administrator_ids serializes them) and when an invitation is
    accepted (test_invitation_accept.py). Hence tested directly here.
    """
    import pytest
    from fastapi import HTTPException

    from normly_accounts.admin_rules import ensure_administrator_remains

    only = make_account(db_session, "only-admin@normly.example", role=Role.ADMINISTRATOR)
    with pytest.raises(HTTPException) as caught:
        ensure_administrator_remains(db_session, only)
    assert (caught.value.status_code, caught.value.detail) == (409, "last_administrator")

    blocked_admin = make_account(db_session, "blocked-admin@normly.example",
                                 role=Role.ADMINISTRATOR, blocked=True)
    with pytest.raises(HTTPException):
        ensure_administrator_remains(db_session, only)  # a blocked admin does not count
    ensure_administrator_remains(db_session, blocked_admin)  # not active: nothing to protect

    make_account(db_session, "second-admin@normly.example", role=Role.ADMINISTRATOR)
    ensure_administrator_remains(db_session, only)  # another active admin exists
    ensure_administrator_remains(db_session, make_account(db_session, "u@normly.example"))


def test_block_ends_sessions_mails_neutrally_and_unblock_restores(client, db_session, email_sender, monkeypatch):
    monkeypatch.setenv("NORMLY_CONTACT_EMAIL", "kontakt@normly.example")
    _, headers = make_admin(db_session)
    user = make_account(db_session, "crawler@example.de", locale="en")
    user_headers = auth_headers(db_session, user)

    response = client.post(f"/v1/admin/accounts/{user.id}/block",
                           json={"reason": "bulk_retrieval"}, headers=headers)

    assert response.json() == {"email_sent": True}
    assert client.get("/v1/accounts/session", headers=user_headers).status_code == 401
    [mail] = email_sender.sent
    assert mail["subject"] == "Your normly account has been blocked"
    assert "kontakt@normly.example" in mail["body"] and "bulk" not in mail["body"]
    again = client.post(f"/v1/admin/accounts/{user.id}/block", json={"reason": "abuse"}, headers=headers)
    assert (again.status_code, again.json()["detail"]) == (409, "already_blocked")

    assert client.post(f"/v1/admin/accounts/{user.id}/unblock", headers=headers).status_code == 204
    assert PostgresAccountRepository(db_session).get_account_by_id(user.id).blocked_at is None
    assert _actions(db_session, user.id) == ["account_blocked", "account_unblocked"]


def test_remove_needs_the_confirmation_address_and_keeps_the_audit(client, db_session, email_sender):
    _, headers = make_admin(db_session)
    user = make_account(db_session, "leaving@example.de")

    wrong = client.request("DELETE", f"/v1/admin/accounts/{user.id}",
                           json={"confirm_email": "other@example.de"}, headers=headers)
    assert wrong.status_code == 400

    response = client.request("DELETE", f"/v1/admin/accounts/{user.id}",
                              json={"confirm_email": " Leaving@example.de "}, headers=headers)

    assert response.json() == {"email_sent": True}
    assert PostgresAccountRepository(db_session).get_account_by_id(user.id) is None
    assert _actions(db_session, user.id) == ["account_removed"]
    assert email_sender.sent[-1]["to"] == "leaving@example.de"
    stored = db_session.execute(sa.text("SELECT details::text FROM admin_audit_log")).scalars().all()
    assert not any("leaving@example.de" in d for d in stored)
```

- [ ] **Step 2: Write the failing list tests**

`accounts/tests/test_admin_users.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import Role

from tests.admin_support import make_account, make_admin, make_publisher


def test_list_filters_and_pages(client, db_session):
    _, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    make_account(db_session, "p@vde.example", role=Role.PUBLISHER, publisher_id=publisher.id)
    make_account(db_session, "blocked@example.de", blocked=True)
    client.post("/v1/admin/invitations", headers=headers, json={"email": "new@example.de", "role": "user"})

    page = client.get("/v1/admin/users?page_size=10", headers=headers).json()
    assert page["total"] == 4 and page["page"] == 1
    assert {r["status"] for r in page["rows"]} == {"active", "blocked", "invited"}

    blocked = client.get("/v1/admin/users?status=blocked", headers=headers).json()
    assert [r["email"] for r in blocked["rows"]] == ["blocked@example.de"]
    publishers = client.get("/v1/admin/users?role=publisher", headers=headers).json()
    assert publishers["rows"][0]["publisher_name"] == "VDE Verlag"
    assert client.get("/v1/admin/users?page_size=7", headers=headers).status_code == 400
    assert client.get("/v1/admin/users?sort=password_hash", headers=headers).status_code == 400


def test_summary_and_role_matrix(client, db_session):
    _, headers = make_admin(db_session)
    make_account(db_session, "blocked@example.de", blocked=True)

    summary = client.get("/v1/admin/users/summary", headers=headers).json()
    assert summary["accounts_total"] == 2
    assert summary["accounts_by_role"] == {"user": 1, "publisher": 0, "administrator": 1}
    assert summary["most_frequent_block_reason"] == "abuse"

    matrix = client.get("/v1/admin/role-matrix", headers=headers).json()
    assert matrix["roles"] == ["anonymous", "user", "publisher", "administrator"]
    management = next(r for r in matrix["rows"] if r["capability"] == "user_management")
    assert management["values"]["administrator"] == "yes"
```

- [ ] **Step 3: Run and see them fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_admin_accounts.py tests/test_admin_users.py -v`
Expected: FAIL with 404/405.

- [ ] **Step 4: Account administration router**

`accounts/src/normly_accounts/routers/admin_accounts.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAccountSessionRepository,
    PostgresAdminAuditRepository,
)
from normly_core.notifications.email import EmailSender

from normly_accounts.admin_mail import send_account_notice
from normly_accounts.admin_rules import (
    ensure_administrator_remains, ensure_not_self, publisher_or_400, snapshot,
    target_account_or_404,
)
from normly_accounts.admin_schemas import (
    BlockAccountRequest, EmailSentResponse, RemoveAccountRequest, UpdateAccountRequest,
)
from normly_accounts.dependencies import get_email_sender, get_session, require_capability
from normly_accounts.permissions import USER_MANAGEMENT

admin_accounts_router = APIRouter(prefix="/v1/admin/accounts", tags=["admin"])


@admin_accounts_router.patch("/{account_id}", status_code=204)
def update_account(
    account_id: uuid.UUID, payload: UpdateAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    """Downgrade to user or change a publisher's binding; upgrades go through an invitation."""
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    accounts = PostgresAccountRepository(session)
    if payload.role is not None:
        if payload.role is not Role.USER:
            raise HTTPException(status_code=409, detail="upgrade_requires_invitation")
        if target.role is Role.USER:
            return Response(status_code=204)
        ensure_administrator_remains(session, target)
        accounts.set_role(target.id, role=Role.USER, publisher_id=None)
        action = AdminAction.ROLE_CHANGED
    else:
        if target.role is not Role.PUBLISHER:
            raise HTTPException(status_code=409, detail="not_a_publisher")
        publisher_or_400(session, payload.publisher_id)
        if target.publisher_id == payload.publisher_id:
            return Response(status_code=204)
        accounts.set_role(target.id, role=Role.PUBLISHER, publisher_id=payload.publisher_id)
        action = AdminAction.PUBLISHER_CHANGED
    after = accounts.get_account_by_id(target.id)
    PostgresAdminAuditRepository(session).record(
        action=action, actor_account_id=admin.id, occurred_at=datetime.now(timezone.utc),
        target_account_id=target.id, target_publisher_id=after.publisher_id or target.publisher_id,
        details={"before": snapshot(target), "after": snapshot(after)},
    )
    session.commit()
    return Response(status_code=204)


@admin_accounts_router.post("/{account_id}/block", response_model=EmailSentResponse)
def block_account(
    account_id: uuid.UUID, payload: BlockAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EmailSentResponse:
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    if target.blocked_at is not None:
        raise HTTPException(status_code=409, detail="already_blocked")
    ensure_administrator_remains(session, target)
    now = datetime.now(timezone.utc)
    PostgresAccountRepository(session).block_account(target.id, reason=payload.reason, blocked_at=now)
    PostgresAccountSessionRepository(session).delete_sessions_for_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_BLOCKED, actor_account_id=admin.id, occurred_at=now,
        target_account_id=target.id, details={"reason": payload.reason.value},
    )
    session.commit()
    sent = send_account_notice(email_sender, "account_blocked", email=target.email, locale=target.locale)
    return EmailSentResponse(email_sent=sent)


@admin_accounts_router.post("/{account_id}/unblock", status_code=204)
def unblock_account(
    account_id: uuid.UUID,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> Response:
    target = target_account_or_404(session, account_id)
    if target.blocked_at is None:
        raise HTTPException(status_code=409, detail="not_blocked")
    PostgresAccountRepository(session).unblock_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_UNBLOCKED, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_account_id=target.id,
        details={"reason": target.block_reason.value},
    )
    session.commit()
    return Response(status_code=204)


@admin_accounts_router.delete("/{account_id}", response_model=EmailSentResponse)
def remove_account(
    account_id: uuid.UUID, payload: RemoveAccountRequest,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EmailSentResponse:
    target = target_account_or_404(session, account_id)
    ensure_not_self(admin, target)
    if payload.confirm_email.strip().lower() != target.email.lower():
        raise HTTPException(status_code=400, detail="confirmation does not match")
    ensure_administrator_remains(session, target)
    # Same path as self-deletion (ADR-027): cascade plus deletion_log entry.
    PostgresAccountRepository(session).delete_account(target.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ACCOUNT_REMOVED, actor_account_id=admin.id,
        occurred_at=datetime.now(timezone.utc), target_account_id=target.id,
        details={"before": snapshot(target)},
    )
    session.commit()
    # After the commit: no mail announces a deletion that did not happen.
    sent = send_account_notice(email_sender, "account_removed", email=target.email, locale=target.locale)
    return EmailSentResponse(email_sent=sent)
```

- [ ] **Step 5: List, summary and matrix router**

`accounts/src/normly_accounts/routers/admin_users.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from normly_core.graph.domain import Account, Role
from normly_core.graph.postgres.repositories import PostgresAdminDirectoryRepository

from normly_accounts.admin_schemas import (
    AdminSummaryResponse, AdminUserPageResponse, AdminUserResponse, RoleMatrixResponse,
    RoleMatrixRow,
)
from normly_accounts.dependencies import get_session, require_capability
from normly_accounts.permissions import CAPABILITIES, MATRIX_ROLES, USER_MANAGEMENT

admin_users_router = APIRouter(prefix="/v1/admin", tags=["admin"])

ACTIVE_WINDOW = timedelta(days=30)
PAGE_SIZES = (10, 20, 50)
SortKey = Literal[
    "email", "first_name", "last_name", "sign_in", "role", "publisher", "last_login_at",
    "created_at", "status",
]


@admin_users_router.get("/users", response_model=AdminUserPageResponse)
def list_users(
    q: str | None = Query(default=None, max_length=200),
    role: Role | None = None,
    status: Literal["active", "blocked", "invited", "expired"] | None = None,
    sort: SortKey = "email",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = 10,
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> AdminUserPageResponse:
    if page_size not in PAGE_SIZES:
        raise HTTPException(status_code=400, detail="page_size must be 10, 20 or 50")
    result = PostgresAdminDirectoryRepository(session).list_users(
        query=q, role=role, status=status, sort=sort, descending=order == "desc",
        page=page, page_size=page_size, now=datetime.now(timezone.utc),
    )
    return AdminUserPageResponse(
        rows=[
            AdminUserResponse(**{**row.__dict__, "sign_in_methods": list(row.sign_in_methods)})
            for row in result.rows
        ],
        total=result.total, page=page, page_size=page_size,
    )


@admin_users_router.get("/users/summary", response_model=AdminSummaryResponse)
def summarize_users(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
    session: Session = Depends(get_session),
) -> AdminSummaryResponse:
    now = datetime.now(timezone.utc)
    summary = PostgresAdminDirectoryRepository(session).summarize(
        now=now, active_since=now - ACTIVE_WINDOW
    )
    return AdminSummaryResponse(
        accounts_total=summary.accounts_total,
        accounts_active_30_days=summary.accounts_active,
        accounts_by_role={role.value: n for role, n in summary.accounts_by_role.items()},
        publishers_with_accounts=summary.publishers_with_accounts,
        open_invitations=summary.open_invitations, blocked=summary.blocked,
        most_frequent_block_reason=summary.most_frequent_block_reason,
    )


@admin_users_router.get("/role-matrix", response_model=RoleMatrixResponse)
def role_matrix(
    admin: Account = Depends(require_capability(USER_MANAGEMENT)),
) -> RoleMatrixResponse:
    return RoleMatrixResponse(
        roles=list(MATRIX_ROLES),
        rows=[
            RoleMatrixRow(capability=c.key, planned=c.planned, values=c.values)
            for c in CAPABILITIES
        ],
    )
```

`AdminUserRow` is a frozen dataclass; `row.__dict__` works for `@dataclass(frozen=True)` without `slots`. If `slots=True` is ever added, switch to `dataclasses.asdict(row)`.

- [ ] **Step 6: Register and update the OpenAPI test**

`main.py`:

```python
    app.include_router(admin_accounts_router, responses=COMMON_ERROR_RESPONSES)
    app.include_router(admin_users_router, responses=COMMON_ERROR_RESPONSES)
```

Expected paths gain:

```python
        "/v1/admin/accounts/{account_id}",
        "/v1/admin/accounts/{account_id}/block",
        "/v1/admin/accounts/{account_id}/unblock",
        "/v1/admin/users",
        "/v1/admin/users/summary",
        "/v1/admin/role-matrix",
```

- [ ] **Step 7: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: PASS (whole suite).

- [ ] **Step 8: Commit**

```bash
git add accounts/src accounts/tests
git commit -s -m "feat(accounts): add account administration, user list and role matrix" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 10: Accepting an invitation

**Files:**
- Create: `accounts/src/normly_accounts/routers/invitation.py`
- Modify: `accounts/src/normly_accounts/schemas.py`, `main.py`, `accounts/tests/test_openapi_and_end_to_end.py`
- Test: `accounts/tests/test_invitation_accept.py` (create)

**Interfaces:**
- Produces: `POST /v1/accounts/invitations/accept` with body `AcceptInvitationRequest {token: str}` → `SessionResponse`; 410 `invitation_invalid`, 403 `account_blocked`, 409 `last_administrator`.

- [ ] **Step 1: Write the failing tests**

`accounts/tests/test_invitation_accept.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from normly_core.graph.domain import Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresInvitationRepository,
)

from tests.admin_support import make_account, make_admin, make_publisher


def _invite(client, headers, db_session, email, **extra):
    client.post("/v1/admin/invitations", headers=headers, json={"email": email, **extra})
    return PostgresInvitationRepository(db_session).get_invitation_by_email(email).token


def test_accepting_creates_a_verified_signed_in_publisher(client, db_session):
    _, headers = make_admin(db_session)
    publisher = make_publisher(db_session)
    token = _invite(client, headers, db_session, "partner@vde.example",
                    role="publisher", publisher_id=str(publisher.id), locale="en")

    response = client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert response.status_code == 200
    session_token = response.json()["session_token"]
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {session_token}"}).json()
    assert (session["role"], session["publisher_id"]) == ("publisher", str(publisher.id))
    account = PostgresAccountRepository(db_session).get_account_by_email("partner@vde.example")
    assert account.email_verified_at is not None and account.locale == "en"
    assert PostgresInvitationRepository(db_session).get_invitation_by_token(token) is None
    again = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (again.status_code, again.json()["detail"]) == (410, "invitation_invalid")


def test_an_existing_account_gets_the_role_only_on_accept(client, db_session):
    _, headers = make_admin(db_session)
    existing = make_account(db_session, "colleague@example.de", password="correct horse")
    token = _invite(client, headers, db_session, "colleague@example.de", role="administrator")
    accounts = PostgresAccountRepository(db_session)
    assert accounts.get_account_by_id(existing.id).role is Role.USER

    client.post("/v1/accounts/invitations/accept", json={"token": token})

    assert accounts.get_account_by_id(existing.id).role is Role.ADMINISTRATOR


def test_a_matching_address_alone_never_grants_the_role(client, db_session):
    """Someone registers the invited address first; without the link nothing changes."""
    _, headers = make_admin(db_session)
    _invite(client, headers, db_session, "target@vde.example", role="administrator")
    client.post("/v1/accounts/register", json={"email": "target@vde.example", "password": "correct horse"})
    login = client.post("/v1/accounts/login", json={"email": "target@vde.example", "password": "correct horse"})
    session = client.get("/v1/accounts/session",
                         headers={"Authorization": f"Bearer {login.json()['session_token']}"}).json()
    assert session["role"] == "user"


def test_expired_and_blocked(client, db_session):
    _, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, "late@example.de", role="user")
    db_session.execute(sa.text("UPDATE account_invitation SET expires_at = :t WHERE token = :k"),
                       {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "k": token})
    assert client.post("/v1/accounts/invitations/accept", json={"token": token}).status_code == 410

    make_account(db_session, "soon-blocked@example.de")
    token = _invite(client, headers, db_session, "soon-blocked@example.de", role="user")
    account = PostgresAccountRepository(db_session).get_account_by_email("soon-blocked@example.de")
    client.post(f"/v1/admin/accounts/{account.id}/block", json={"reason": "abuse"}, headers=headers)
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (403, "account_blocked")


def test_accepting_a_user_invitation_cannot_remove_the_last_administrator(client, db_session):
    admin, headers = make_admin(db_session)
    token = _invite(client, headers, db_session, admin.email, role="user")
    response = client.post("/v1/accounts/invitations/accept", json={"token": token})
    assert (response.status_code, response.json()["detail"]) == (409, "last_administrator")
    assert PostgresAccountRepository(db_session).get_account_by_id(admin.id).role is Role.ADMINISTRATOR
```

- [ ] **Step 2: Run and see it fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_invitation_accept.py -v`
Expected: FAIL with 404 on `/v1/accounts/invitations/accept`.

- [ ] **Step 3: Implement**

`schemas.py`:

```python
class AcceptInvitationRequest(BaseModel):
    token: str
```

`accounts/src/normly_accounts/routers/invitation.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresInvitationRepository,
)

from normly_accounts.admin_rules import ensure_administrator_remains, snapshot
from normly_accounts.dependencies import get_session
from normly_accounts.routers.login import _create_session_response
from normly_accounts.schemas import AcceptInvitationRequest, SessionResponse

invitation_router = APIRouter(prefix="/v1/accounts/invitations", tags=["invitations"])


@invitation_router.post("/accept", response_model=SessionResponse)
def accept_invitation(
    payload: AcceptInvitationRequest, session: Session = Depends(get_session),
) -> SessionResponse:
    """
    The click on the invitation link: proves the mailbox, binds role and
    publisher and signs the person in. A role is never granted because an
    address merely matches (ADR-030).
    """
    now = datetime.now(timezone.utc)
    invitations = PostgresInvitationRepository(session)
    invitation = invitations.get_invitation_by_token(payload.token, lock=True)
    if invitation is None or invitation.expires_at <= now:
        raise HTTPException(status_code=410, detail="invitation_invalid")

    accounts = PostgresAccountRepository(session)
    account = accounts.get_account_by_email(invitation.email)
    if account is None:
        account = accounts.create_account(
            email=invitation.email, password_hash=None, locale=invitation.locale,
        )
    if account.blocked_at is not None:
        raise HTTPException(status_code=403, detail="account_blocked")
    if invitation.role is not Role.ADMINISTRATOR:
        ensure_administrator_remains(session, account)

    if account.email_verified_at is None:
        accounts.mark_email_verified(account.id, now)
    accounts.set_role(account.id, role=invitation.role, publisher_id=invitation.publisher_id)
    invitations.delete_invitation(invitation.id)
    after = accounts.get_account_by_id(account.id)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.INVITATION_ACCEPTED, actor_account_id=account.id, occurred_at=now,
        target_account_id=account.id, target_invitation_id=invitation.id,
        target_publisher_id=invitation.publisher_id,
        details={"before": snapshot(account), "after": snapshot(after)},
    )
    # Commits before the response, like every sign-in path.
    return _create_session_response(after, session)
```

`main.py`: `app.include_router(invitation_router, responses=COMMON_ERROR_RESPONSES)`. OpenAPI test: add `"/v1/accounts/invitations/accept"`.

- [ ] **Step 4: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add accounts/src accounts/tests
git commit -s -m "feat(accounts): accept invitations through their link" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 11: `grant-admin` CLI

**Files:**
- Create: `core/src/normly_core/admin.py`
- Modify: `core/src/normly_core/pipeline/cli.py`
- Test: `core/tests/pipeline/test_grant_admin.py` (create)

**Interfaces:**
- Produces: `normly_core.admin.grant_administrator(session, *, email: str, now: datetime) -> str` returning `"granted"` or `"unchanged"`; raises `AdminGrantError` (message for stderr) when the account is missing or blocked. CLI: `python -m normly_core.pipeline grant-admin --email <address>`.

- [ ] **Step 1: Write the failing test**

`core/tests/pipeline/test_grant_admin.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import datetime, timezone

import pytest

from normly_core.admin import AdminGrantError, grant_administrator
from normly_core.graph.domain import AdminAction, BlockReason, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
    PostgresPublisherRepository,
)

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def test_grant_sets_the_role_clears_a_binding_and_is_idempotent(db_session):
    accounts = PostgresAccountRepository(db_session)
    publisher = PostgresPublisherRepository(db_session).create_publisher(name="DIN Media", created_at=NOW)
    account = accounts.create_account(email="first-admin@example.de", password_hash=None)
    accounts.set_role(account.id, role=Role.PUBLISHER, publisher_id=publisher.id)

    assert grant_administrator(db_session, email="first-admin@example.de", now=NOW) == "granted"
    assert grant_administrator(db_session, email="first-admin@example.de", now=NOW) == "unchanged"

    granted = accounts.get_account_by_id(account.id)
    assert (granted.role, granted.publisher_id) == (Role.ADMINISTRATOR, None)
    [entry] = PostgresAdminAuditRepository(db_session).list_for_target_account(account.id)
    assert (entry.action, entry.actor_account_id) == (AdminAction.ADMINISTRATOR_GRANTED_CLI, None)


def test_grant_refuses_unknown_and_blocked_accounts(db_session):
    with pytest.raises(AdminGrantError, match="no account"):
        grant_administrator(db_session, email="nobody@example.de", now=NOW)
    accounts = PostgresAccountRepository(db_session)
    blocked = accounts.create_account(email="blocked-admin@example.de", password_hash=None)
    accounts.block_account(blocked.id, reason=BlockReason.OTHER, blocked_at=NOW)
    with pytest.raises(AdminGrantError, match="blocked"):
        grant_administrator(db_session, email="blocked-admin@example.de", now=NOW)
```

- [ ] **Step 2: Run and see it fail**

Run: `cd core && ../.venv/bin/pytest tests/pipeline/test_grant_admin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normly_core.admin'`.

- [ ] **Step 3: Implement**

`core/src/normly_core/admin.py`:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Bootstrapping the first administrator of an instance (ADR-030)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from normly_core.graph.domain import AdminAction, Role
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresAdminAuditRepository,
)


class AdminGrantError(Exception):
    pass


def grant_administrator(session: Session, *, email: str, now: datetime) -> str:
    accounts = PostgresAccountRepository(session)
    account = accounts.get_account_by_email(email)
    if account is None:
        raise AdminGrantError(f"no account with the address {email}; sign up first")
    if account.blocked_at is not None:
        raise AdminGrantError("the account is blocked; unblock it first")
    if account.role is Role.ADMINISTRATOR:
        return "unchanged"
    accounts.set_role(account.id, role=Role.ADMINISTRATOR, publisher_id=None)
    PostgresAdminAuditRepository(session).record(
        action=AdminAction.ADMINISTRATOR_GRANTED_CLI, actor_account_id=None, occurred_at=now,
        target_account_id=account.id,
        details={
            "before": {
                "role": account.role.value,
                "publisher_id": str(account.publisher_id) if account.publisher_id else None,
            },
            "after": {"role": Role.ADMINISTRATOR.value, "publisher_id": None},
        },
    )
    return "granted"
```

In `cli.py`, import `from normly_core.admin import AdminGrantError, grant_administrator`; register the parser after `notify-watchers`:

```python
    grant_parser = subparsers.add_parser("grant-admin")
    grant_parser.add_argument("--email", required=True, help="address of an existing account")
```

and the branch in the `with Session(engine) as session:` block:

```python
            elif args.command == "grant-admin":
                try:
                    outcome = grant_administrator(
                        session, email=args.email, now=datetime.now(timezone.utc)
                    )
                except AdminGrantError as exc:
                    print(f"grant-admin: {exc}", file=sys.stderr)
                    return 1
                session.commit()
                print(f"grant-admin: {outcome}")
```

- [ ] **Step 4: Run the tests**

Run: `cd core && ../.venv/bin/pytest tests/pipeline/test_grant_admin.py tests/pipeline/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/src/normly_core/admin.py core/src/normly_core/pipeline/cli.py core/tests/pipeline/test_grant_admin.py
git commit -s -m "feat(core): add the grant-admin command" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 12: Export contains role, block and audit entries

**Files:**
- Modify: `accounts/src/normly_accounts/schemas.py` (`ExportAccountFields`, `ExportResponse`), `routers/account_management.py`
- Test: `accounts/tests/test_account_export.py` (append)

**Interfaces:**
- Produces: `ExportAccountFields` gains `role: str`, `publisher_name: str | None`; `ExportResponse` gains `admin_actions: list[ExportAdminAction]` with `ExportAdminAction {action: str, occurred_at: datetime, details: dict}` (no actor).

Blocked accounts cannot sign in, so the export shows no block status (a signed-in exporter is never blocked); a blocked person's access request is answered by the operator. The block's history still appears through `admin_actions` once unblocked.

- [ ] **Step 1: Write the failing test** (append to `accounts/tests/test_account_export.py`)

```python
def test_export_contains_role_publisher_and_admin_actions_without_the_actor(client, db_session):
    from normly_core.graph.domain import Role
    from tests.admin_support import auth_headers, make_account, make_admin, make_publisher

    admin, headers = make_admin(db_session)
    din, vde = make_publisher(db_session, "DIN Media"), make_publisher(db_session, "VDE Verlag")
    partner = make_account(db_session, "export-partner@example.de", role=Role.PUBLISHER, publisher_id=din.id)
    client.patch(f"/v1/admin/accounts/{partner.id}", json={"publisher_id": str(vde.id)}, headers=headers)

    body = client.get("/v1/accounts/export", headers=auth_headers(db_session, partner)).json()

    assert body["account"]["role"] == "publisher"
    assert body["account"]["publisher_name"] == "VDE Verlag"
    [action] = body["admin_actions"]
    assert action["action"] == "publisher_changed"
    assert str(admin.id) not in str(body)
```

- [ ] **Step 2: Run and see it fail**

Run: `cd accounts && ../.venv/bin/pytest tests/test_account_export.py -v`
Expected: FAIL with `KeyError: 'role'`.

- [ ] **Step 3: Implement**

`schemas.py`:

```python
class ExportAccountFields(BaseModel):
    ...  # existing fields
    role: str
    publisher_name: str | None


class ExportAdminAction(BaseModel):
    action: str
    occurred_at: datetime
    # Values before/after; the acting administrator is deliberately left out.
    details: dict


class ExportResponse(BaseModel):
    account: ExportAccountFields
    chat_sessions: list[ExportChatSession]
    watchlist: list[ExportWatchlistEntry]
    notifications: list[ExportNotification]
    admin_actions: list[ExportAdminAction]
```

In `account_management.py::export_account_data` (import `PostgresAdminAuditRepository`, `PostgresPublisherRepository`, `ExportAdminAction`):

```python
    publisher = (
        PostgresPublisherRepository(session).get_publisher(account.publisher_id)
        if account.publisher_id else None
    )
    admin_actions = [
        ExportAdminAction(action=e.action.value, occurred_at=e.occurred_at, details=e.details)
        for e in PostgresAdminAuditRepository(session).list_for_target_account(account.id)
    ]
```

pass `role=account.role.value, publisher_name=publisher.name if publisher else None` into `ExportAccountFields(...)` and `admin_actions=admin_actions` into `ExportResponse(...)`.

- [ ] **Step 4: Run the tests**

Run: `cd accounts && ../.venv/bin/pytest tests/test_account_export.py tests/test_account_lifecycle_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add accounts/src accounts/tests
git commit -s -m "feat(accounts): include role and admin actions in the export" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 13: Documentation

**Files:**
- Modify: `docs/adr/README.md` (new ADR-030 after ADR-029; ADR-017 list; ADR-027 inventory)
- Modify: `docs/srs/03-requirements.md` (REQ-ACC-004, new REQ-ACC-006), `docs/srs/README.md` (index, count)
- Modify: `docs/glossary.md`, `docs/guide/self-hosting.md`, `docs/guide/operations.md`

- [ ] **Step 1: ADR-030**

Append after ADR-029 in `docs/adr/README.md`:

```markdown
---

## ADR-030 — Roles, publishers and user management

**Status:** accepted (2026-10-31)

**Decision:** Every account has exactly one role: `user`, `publisher` or
`administrator`. Publisher and administrator include everything a user can
do. A publisher account is bound to exactly one entry of the new `publisher`
table. A publisher entry is the **contract partner** whose content usage the
account may later see — for example a distributor such as DIN Media, not
necessarily the issuing body.

- **Consent for more rights.** A role above `user` is granted only through an
  invitation link (7 days, single use), which proves control of the mailbox.
  An address that merely matches never receives a role. Inviting an existing
  account is allowed; its role changes when the link is used.
- **Fewer rights at once.** Administrators can downgrade to `user`, change a
  publisher's binding and block an account immediately. Blocking ends all
  sessions and refuses every sign-in path; anonymous use of free content
  stays possible (ADR-017). The reason comes from a fixed list; the person
  receives a neutral mail with a contact address.
- **Protection.** The last active administrator cannot be downgraded,
  blocked or removed; nobody can do any of this to their own account through
  the panel. The first administrator is set with
  `python -m normly_core.pipeline grant-admin --email …`.
- **Checks.** The role is read from the database on every request. One
  capability matrix (`accounts/src/normly_accounts/permissions.py`) drives
  both the server-side guard and the "What the roles see" dialog.
- **Audit.** Every administrative action is logged with account, invitation
  and publisher IDs and before/after values, without e-mail addresses and
  without foreign keys, so entries outlive deleted accounts. Retention 2
  years.

**Rationale:** Every partner feature (usage analytics, deliveries,
billing) depends on a role model. Consent through the invitation link closes
the gap that an attacker who registers an invited address first would
otherwise inherit its role. Granting through an invitation also limits what
a taken-over administrator account can do unnoticed.

**Rejected:** Several roles per account (no current need, harder to check
and to display). The role in the session token (a downgrade or block would
only take effect at the next sign-in). Free-text block reasons (they invite
personal notes about users). Publishers as free text (no stable key for
statistics or the per-publisher data key of ADR-014).

**Consequences:** REQ-ACC-004 and ADR-017 list role-bound administrative and
partner functions; REQ-ACC-006 describes the role model. The data inventory
of ADR-027 gains `publisher`, `account_invitation` and `admin_audit_log`.
```

- [ ] **Step 2: ADR-017 and ADR-027**

In ADR-017's decision, change the list to: "Account required for: higher quotas, histories and bookmark lists, own uploads, licensed content, offline use, paid services, role-bound administrative and partner functions (ADR-030) — the list is **exhaustive**."

In ADR-027's data-inventory table add, after the `account_token` row:

```markdown
| `publisher` | contract partners for publisher accounts (ADR-030) | none (organization names) | until removed by the operator | operator |
| `account_invitation` | open or expired invitation | e-mail address, invited role | until accepted or withdrawn; expired ones 30 days after expiry | administrator; cleanup command |
| `admin_audit_log` | record of administrative actions (ADR-030) | account IDs only, no e-mail address | 2 years | cleanup command |
```

and add `role`, `publisher_id`, `blocked_at`, `block_reason` to the purpose text of the `account` row ("…, role and block (ADR-030)").

- [ ] **Step 3: SRS**

In `docs/srs/03-requirements.md`, REQ-ACC-004 statement: append "role-bound administrative and partner functions (REQ-ACC-006)" to the list before "This list is exhaustive". After REQ-ACC-005 add:

```markdown
### REQ-ACC-006 — Roles and user management

**Statement:** Every account has exactly one role: user, publisher or administrator. A publisher account is bound to exactly one publisher (contract partner). Roles above user are granted only through an invitation link that the invited person follows; administrators can downgrade, change a publisher binding, block and remove accounts at once. Role-bound functions are checked on the server on every request. Every administrative action is logged without e-mail addresses and kept for two years.

**Rationale:** Partner functions (REQ-PART-001, REQ-PART-003) and the manual block under REQ-SEC-004 need a role model. Consent through the invitation link prevents a role from passing to whoever registers an invited address first (ADR-030).

**Acceptance criteria:** Admin functions answer 403 to every other role; a downgrade or block takes effect on the next request; the last active administrator cannot be removed; audit entries survive account deletion.

**Acceptance test:** An administrator invites a publisher, the invited person accepts and sees the publisher role; after a block, every sign-in path is refused and the audit log shows both actions.
```

In `docs/srs/README.md` add the index row:

```markdown
| [`REQ-ACC-006`](03-requirements.md#req-acc-006-roles-and-user-management) | Roles and user management | 3.16 |
```

and increase the requirement count wherever the README states it (search for the current total and add one).

- [ ] **Step 4: Glossary**

Add to `docs/glossary.md` after "Normenausschuss vs. publisher":

```markdown
**Publisher (contract partner)**
: In user management, the organization a publisher account is bound to —
  the contract partner whose content usage the account may see, e.g. a
  distributor. Not necessarily the publisher that releases a standard. See
  [ADR-030](adr/README.md#adr-030-roles-publishers-and-user-management).

**Roles: user, publisher, administrator**
: Exactly one per account. *User* is every self-registered account;
  *publisher* staff of a contract partner; *administrator* runs the
  instance's user management. Not to be confused with *operator*, whoever
  runs an instance.
```

- [ ] **Step 5: Guides**

`docs/guide/self-hosting.md`, in the mail bullet after the imprint sentence: "Block and removal mails name `NORMLY_CONTACT_EMAIL` as the contact; without it they link the imprint." In the commands list next to `cleanup-user-data` add `grant-admin`, and add a bullet:

```markdown
- **First administrator.** Sign up in the web app, then grant the role:
  `docker compose run --rm pipeline grant-admin --email you@example.org`.
  Further administrators and publishers are invited from *User management*.
```

`docs/guide/operations.md`, next to the `cleanup-user-data` section: note that it now also deletes expired invitations (30 days after expiry) and audit entries older than two years, and document `grant-admin` with the same command as above.

- [ ] **Step 6: Check links and build**

Run: `uv run zensical build --strict 2>&1 | tail -20` from the repository root if the docs build is set up there (see `zensical.toml`); otherwise check the new anchors by hand: `#adr-030-roles-publishers-and-user-management`, `#req-acc-006-roles-and-user-management`.
Expected: no broken-link warnings.

- [ ] **Step 7: Commit**

```bash
git add docs
git commit -s -m "docs: record roles and user management (ADR-030, REQ-ACC-006)" -m "Refs: #60" -m "Assisted-by: Claude Code"
```

---

### Task 14: Full verification

- [ ] **Step 1: Run both suites**

Run: `cd core && ../.venv/bin/pytest -q` and `cd accounts && ../.venv/bin/pytest -q`
Expected: no failures beyond those already failing on `develop` (compare with a run on `develop` if anything unrelated fails).

- [ ] **Step 2: Run the chat suite**

Run: `cd chat && ../.venv/bin/pytest -q`
Expected: PASS — chat validates sessions through the accounts service and tolerates the extra `role`/`publisher_id` fields.

- [ ] **Step 3: Lint**

Run the linters CI runs (see `.github/workflows/ci.yml`), e.g. `uv run ruff check core accounts` if configured.
Expected: clean.

- [ ] **Step 4: Manual smoke test against Compose (optional, local)**

`docker compose up -d`, register an account, `docker compose run --rm pipeline grant-admin --email <it>`, then `curl` `GET /v1/admin/users` through the accounts container with the session token. Expected: 200 with one row.
