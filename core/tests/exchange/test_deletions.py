# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Deletion log export and replay for the rollback (user-data lifecycle)."""

import io
import json
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from normly_core.exchange import __main__ as cli
from normly_core.exchange.deletions import build_document, parse_document
from normly_core.graph.domain import ChatMessageRole, WorkCreatedVia
from normly_core.graph.postgres.orm import (
    AccountORM,
    ChatMessageORM,
    ChatSessionORM,
    WatchlistORM,
)
from normly_core.graph.postgres.repositories import (
    PostgresAccountRepository,
    PostgresChatRepository,
    PostgresDeletionLogRepository,
    PostgresWatchlistRepository,
    PostgresWorkRepository,
)

from .test_tombstones import _BorrowedSession

SINCE = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)
ENV_SH = Path(__file__).parents[3] / "scripts" / "normly-env.sh"


@pytest.fixture()
def cli_on_test_db(monkeypatch, db_session):
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    borrowed = _BorrowedSession(db_session)
    monkeypatch.setattr(cli, "create_engine", lambda url: type("E", (), {"dispose": lambda self: None})())
    monkeypatch.setattr(cli, "Session", lambda engine: borrowed)
    return borrowed


def _account(db_session, email="a@example.de"):
    return PostgresAccountRepository(db_session).create_account(email=email, password_hash=None)


def _chat(db_session, account_id=None, token="tok"):
    repo = PostgresChatRepository(db_session)
    chat = repo.create_session(
        session_token=token, jurisdiction="DE", language="de", created_at=SINCE,
        account_id=account_id,
    )
    repo.create_message(
        session_id=chat.id, role=ChatMessageRole.USER, content="hello",
        answer_type=None, created_at=SINCE,
    )
    return chat


def _log(db_session):
    return {
        (kind, entity)
        for kind, entity, _ in PostgresDeletionLogRepository(db_session).entries_since(
            SINCE - timedelta(days=365)
        )
    }


def _count(db_session, orm):
    return db_session.execute(sa.select(sa.func.count()).select_from(orm)).scalar_one()


def _replay(monkeypatch, capsys, document, *extra):
    monkeypatch.setattr("sys.stdin", io.StringIO(document))
    code = cli.main(["replay-deletions", *extra])
    return code, capsys.readouterr()


def _document(*entries):
    return build_document(
        [(kind, entity, SINCE) for kind, entity in entries], created_at=SINCE,
    )


# --- document format ---------------------------------------------------------


def test_document_round_trip_is_sorted():
    a, b = uuid.UUID(int=1), uuid.UUID(int=2)
    later = SINCE + timedelta(hours=1)
    text = build_document(
        [("chat_session", b, later), ("chat_session", a, later), ("account", b, SINCE)],
        created_at=SINCE,
    )
    document = json.loads(text)
    assert document["format"] == 1
    assert [(e["kind"], e["entity_id"]) for e in document["entries"]] == [
        ("account", str(b)), ("chat_session", str(a)), ("chat_session", str(b)),
    ]
    assert parse_document(text) == [("account", b), ("chat_session", a), ("chat_session", b)]


def test_build_requires_a_timezone():
    with pytest.raises(ValueError):
        build_document([], created_at=datetime(2026, 1, 1))


GOOD_ENTRY = {
    "kind": "account", "entity_id": str(uuid.UUID(int=7)), "deleted_at": "2026-10-09T10:00:00+00:00",
}
GOOD = {"format": 1, "created_at": "2026-10-09T10:00:00+00:00", "entries": [GOOD_ENTRY]}


def _with(**changes):
    return {**GOOD, **changes}


def _entry(**changes):
    return _with(entries=[{**GOOD_ENTRY, **changes}])


SAMPLES = {
    "valid": (json.dumps(GOOD), True),
    "valid-empty": (json.dumps(_with(entries=[])), True),
    "valid-chat": (json.dumps(_entry(kind="chat_session")), True),
    "not-json": ("nope", False),
    "array": ("[]", False),
    "wrong-format": (json.dumps(_with(format=2)), False),
    "format-float": (json.dumps(_with(format=1.0)), False),
    "format-bool": (json.dumps(_with(format=True)), False),
    "format-string": (json.dumps(_with(format="1")), False),
    "no-created-at": (json.dumps({"format": 1, "entries": []}), False),
    "created-at-number": (json.dumps(_with(created_at=5)), False),
    "created-at-garbage": (json.dumps(_with(created_at="yesterday")), False),
    "created-at-naive": (json.dumps(_with(created_at="2026-10-09T10:00:00")), False),
    "entries-dict": (json.dumps(_with(entries={})), False),
    "entry-not-object": (json.dumps(_with(entries=["x"])), False),
    "unknown-kind": (json.dumps(_entry(kind="document")), False),
    "kind-missing": (json.dumps(_with(entries=[{"entity_id": GOOD_ENTRY["entity_id"], "deleted_at": GOOD_ENTRY["deleted_at"]}])), False),
    "entity-not-uuid": (json.dumps(_entry(entity_id="1; DROP TABLE x")), False),
    "entity-number": (json.dumps(_entry(entity_id=7)), False),
    "deleted-at-missing": (json.dumps(_with(entries=[{"kind": "account", "entity_id": GOOD_ENTRY["entity_id"]}])), False),
    "deleted-at-garbage": (json.dumps(_entry(deleted_at="soon")), False),
    "deleted-at-naive": (json.dumps(_entry(deleted_at="2026-10-09T10:00:00")), False),
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_parse_and_the_shell_validator_agree(name, tmp_path):
    text, valid = SAMPLES[name]
    try:
        parse_document(text)
        python_ok = True
    except ValueError:
        python_ok = False
    path = tmp_path / "deletions.json"
    path.write_text(text)
    shell = subprocess.run(
        ["bash", "-c", '. "$1"; normly_check_deletions "$2"', "_", str(ENV_SH), str(path)],
        capture_output=True, text=True,
    )
    assert python_ok == valid
    assert (shell.returncode == 0) == valid, shell.stderr


# --- export ------------------------------------------------------------------


def test_export_prints_only_entries_after_the_timestamp(db_session, cli_on_test_db, capsys):
    log = PostgresDeletionLogRepository(db_session)
    at, before, after, chat = (uuid.uuid4() for _ in range(4))
    log.record(kind="account", entity_id=before, deleted_at=SINCE - timedelta(seconds=1))
    log.record(kind="account", entity_id=at, deleted_at=SINCE)
    log.record(kind="account", entity_id=after, deleted_at=SINCE + timedelta(seconds=1))
    log.record(kind="chat_session", entity_id=chat, deleted_at=SINCE + timedelta(days=1))

    assert cli.main(["export-deletions", "--since", SINCE.isoformat()]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert parse_document(captured.out) == [("account", after), ("chat_session", chat)]
    assert captured.out.count("\n") > 1 and captured.out.startswith("{")


def test_export_of_nothing_is_a_valid_empty_document(cli_on_test_db, capsys):
    assert cli.main(["export-deletions", "--since", SINCE.isoformat()]) == 0
    assert parse_document(capsys.readouterr().out) == []


@pytest.mark.parametrize("since", ["garbage", "2026-10-09T10:00:00"])
def test_export_rejects_a_timestamp_without_timezone(cli_on_test_db, capsys, since):
    assert cli.main(["export-deletions", "--since", since]) == 1
    assert "--since" in capsys.readouterr().err


# --- replay ------------------------------------------------------------------


def test_replay_deletes_an_account_and_logs_it(db_session, cli_on_test_db, monkeypatch, capsys):
    account = _account(db_session)
    chat = _chat(db_session, account.id)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=work.id)

    code, out = _replay(monkeypatch, capsys, _document(("account", account.id)))

    assert code == 0, out.err
    assert "replayed deletions: 1 applied, 0 already gone" in out.out
    assert cli_on_test_db.committed
    assert PostgresAccountRepository(db_session).get_account_by_id(account.id) is None
    assert _count(db_session, ChatSessionORM) == 0 and _count(db_session, WatchlistORM) == 0
    assert ("account", account.id) in _log(db_session)
    assert chat.id


def test_replay_of_a_missing_account_is_already_gone(db_session, cli_on_test_db, monkeypatch, capsys):
    ghost = uuid.uuid4()
    code, out = _replay(monkeypatch, capsys, _document(("account", ghost)))
    assert code == 0
    assert "replayed deletions: 0 applied, 1 already gone" in out.out
    assert ("account", ghost) in _log(db_session)


def test_replay_deletes_a_chat_session_without_an_owner_check(
    db_session, cli_on_test_db, monkeypatch, capsys
):
    owner = _account(db_session)
    owned = _chat(db_session, owner.id, token="a")
    anonymous = _chat(db_session, None, token="b")
    keep = _chat(db_session, owner.id, token="c")

    code, out = _replay(
        monkeypatch, capsys,
        _document(("chat_session", owned.id), ("chat_session", anonymous.id)),
    )

    assert code == 0
    assert "2 applied, 0 already gone" in out.out
    left = set(db_session.execute(sa.select(ChatSessionORM.id)).scalars())
    assert left == {keep.id}
    assert _count(db_session, ChatMessageORM) == 1
    assert {("chat_session", owned.id), ("chat_session", anonymous.id)} <= _log(db_session)


def test_replay_is_idempotent(db_session, cli_on_test_db, monkeypatch, capsys):
    account = _account(db_session)
    chat = _chat(db_session, None)
    document = _document(("account", account.id), ("chat_session", chat.id))

    assert _replay(monkeypatch, capsys, document)[0] == 0
    state = (_count(db_session, AccountORM), _count(db_session, ChatSessionORM), _log(db_session))
    code, out = _replay(monkeypatch, capsys, document)

    assert code == 0
    assert "0 applied, 2 already gone" in out.out
    assert (_count(db_session, AccountORM), _count(db_session, ChatSessionORM), _log(db_session)) == state


@pytest.mark.parametrize("text", ["nope", '{"format": 2}', json.dumps(_entry(kind="x"))])
def test_replay_of_an_invalid_document_changes_nothing(
    db_session, cli_on_test_db, monkeypatch, capsys, text
):
    account = _account(db_session)
    code, out = _replay(monkeypatch, capsys, text)
    assert code == 1
    assert "invalid deletion document" in out.err
    assert not cli_on_test_db.committed
    assert PostgresAccountRepository(db_session).get_account_by_id(account.id) is not None


def test_replay_check_needs_no_database(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    assert cli.main(["replay-deletions", "--check"]) == 0
    assert "replay-deletions" in capsys.readouterr().out


def test_replay_without_a_database_url_fails(monkeypatch, capsys):
    monkeypatch.delenv("NORMLY_DATABASE_URL", raising=False)
    assert cli.main(["replay-deletions"]) == 1
    assert "NORMLY_DATABASE_URL" in capsys.readouterr().err


# --- repository --------------------------------------------------------------


def test_delete_chat_session_by_id_is_idempotent_and_logs(db_session):
    repo = PostgresChatRepository(db_session)
    chat = _chat(db_session, None)
    other = _chat(db_session, None, token="other")

    assert repo.delete_chat_session_by_id(chat.id) is True
    assert repo.delete_chat_session_by_id(chat.id) is False
    assert _log(db_session) == {("chat_session", chat.id)}
    assert [c.id for c in repo.list_sessions_for_account(uuid.uuid4())] == []
    assert db_session.get(ChatSessionORM, other.id) is not None


# --- end to end ---------------------------------------------------------------


def test_rollback_scenario_deletes_the_account_again(
    db_session, cli_on_test_db, monkeypatch, capsys
):
    """A is deleted after the backup; the restore brings A back; the replay removes A."""
    account = _account(db_session)
    _chat(db_session, account.id)
    work = PostgresWorkRepository(db_session).create_work(created_via=WorkCreatedVia.MANUAL)
    PostgresWatchlistRepository(db_session).add_watch(account_id=account.id, work_id=work.id)
    tables = [AccountORM.__table__, ChatSessionORM.__table__, ChatMessageORM.__table__,
              WatchlistORM.__table__]
    backup = {t.name: [dict(r._mapping) for r in db_session.execute(sa.select(t))] for t in tables}

    PostgresAccountRepository(db_session).delete_account(account.id)  # after the backup
    assert _count(db_session, AccountORM) == 0

    assert cli.main(["export-deletions", "--since", (SINCE - timedelta(days=1)).isoformat()]) == 0
    exported = capsys.readouterr().out

    # restore: the data-only backup puts A and her rows back
    for table in tables:
        for row in backup[table.name]:
            db_session.execute(sa.insert(table).values(**row))
    assert _count(db_session, AccountORM) == 1 and _count(db_session, ChatSessionORM) == 1

    code, out = _replay(monkeypatch, capsys, exported)

    assert code == 0, out.err
    assert "1 applied" in out.out
    assert _count(db_session, AccountORM) == 0
    assert _count(db_session, ChatSessionORM) == 0
    assert _count(db_session, ChatMessageORM) == 0
    assert _count(db_session, WatchlistORM) == 0
    assert ("account", account.id) in _log(db_session)
