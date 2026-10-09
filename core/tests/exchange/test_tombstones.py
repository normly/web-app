# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Tombstone support file: closure, format, restore and the rollback (ADR-026)."""

import io
import json
import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from normly_core.exchange import __main__ as cli
from normly_core.exchange.tables import KNOWLEDGE_TABLES, USER_TABLES
from normly_core.exchange.tombstones import (
    TOMBSTONE_FORMAT,
    TOMBSTONE_SUPPORT_TABLES,
    build_document,
    parse_document,
)
from normly_core.graph.postgres.exchange import PostgresKnowledgeExchangeRepository, _kind
from normly_core.graph.postgres.orm import Base
from normly_core.graph.postgres.repositories import PostgresDocumentRepository

from .helpers import make_delivery, make_document, make_source
from .test_takedown import LATER, RECORD, _dump, _frozen, _scenario, _without_document

RESTORED_AT = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _taken_down(db_session):
    """
    A scenario with a retired DROP document and edge, plus an unrelated live
    document on its own source and delivery that must stay out of the file.
    """
    s = _scenario(db_session)
    other_source = make_source(db_session, publisher="Other")
    other_delivery = make_delivery(db_session, other_source, "other")
    s.other = make_document(db_session, other_delivery, "OTHER")
    s.full = _dump(s.repository)
    s.without = _without_document(s.full, s.drop.id)
    s.repository.replace_knowledge_base(_frozen(s.without), record=RECORD)
    return s


def _ids(rows):
    return {r["id"] for r in rows}


def _table_rows(db_session, name):
    table = Base.metadata.tables[name]
    return [dict(r._mapping) for r in db_session.execute(sa.select(table))]


def _wipe(db_session, tables):
    for name in tables:
        db_session.execute(sa.delete(Base.metadata.tables[name]))


# (1) closure ----------------------------------------------------------------


def test_closure_contains_retired_rows_and_their_parents_only(db_session):
    s = _taken_down(db_session)
    rows = s.repository.export_tombstone_support()

    assert tuple(rows) == TOMBSTONE_SUPPORT_TABLES
    # DROP (retired) and KEEP (live, parent of the retired edge) with their works.
    assert _ids(rows["document"]) == {str(s.drop.id), str(s.keep.id)}
    assert _ids(rows["work"]) == {str(s.drop.work_id), str(s.keep.work_id)}
    assert _ids(rows["edge"]) == {str(s.edge.id)}
    assert _ids(rows["delivery"]) == {str(s.delivery.id)}
    assert _ids(rows["source"]) == {str(s.delivery.source_id)}
    assert str(s.other.id) not in _ids(rows["document"])
    assert str(s.other.work_id) not in _ids(rows["work"])


def test_closure_follows_the_merged_into_chain(db_session):
    s = _taken_down(db_session)
    # OTHER's work is merged into a third work; retire OTHER's work only.
    target = uuid.uuid4()
    work = Base.metadata.tables["work"]
    template = db_session.execute(
        sa.select(work).where(work.c.id == s.other.work_id)
    ).one()._mapping
    db_session.execute(sa.insert(work).values({**template, "id": target}))
    db_session.execute(
        sa.update(work)
        .where(work.c.id == s.other.work_id)
        .values(merged_into_work_id=target, retired_at=RESTORED_AT)
    )
    rows = s.repository.export_tombstone_support()
    assert str(target) in _ids(rows["work"])
    assert str(s.other.work_id) in _ids(rows["work"])


def test_values_are_exchange_types_and_sorted(db_session):
    s = _taken_down(db_session)
    rows = s.repository.export_tombstone_support()
    for table_rows in rows.values():
        assert [r["id"] for r in table_rows] == sorted(r["id"] for r in table_rows)
    document = next(r for r in rows["document"] if r["id"] == str(s.drop.id))
    assert isinstance(document["id"], str) and isinstance(document["work_id"], str)
    assert isinstance(document["retired_at"], datetime)
    edge = rows["edge"][0]
    assert edge["edge_type"] == "references" and edge["layer"] == "free"
    json.dumps(build_document(rows, created_at=RESTORED_AT))  # serializable


# (2) content ----------------------------------------------------------------


def test_no_content_but_retired_and_revoked_columns(db_session):
    s = _taken_down(db_session)
    rows = s.repository.export_tombstone_support()
    assert set(rows) == set(TOMBSTONE_SUPPORT_TABLES)
    for forbidden in ("segment", "rights_classification", "embedding"):
        assert forbidden not in rows
    drop_document = next(r for r in rows["document"] if r["id"] == str(s.drop.id))
    keep_document = next(r for r in rows["document"] if r["id"] == str(s.keep.id))
    assert drop_document["retired_at"] is not None
    assert keep_document["retired_at"] is None
    assert rows["edge"][0]["retired_at"] is not None
    assert rows["edge"][0]["revoked_at"] is not None


def test_support_tables_have_no_vector_columns():
    for name in TOMBSTONE_SUPPORT_TABLES:
        kinds = {_kind(c) for c in Base.metadata.tables[name].columns}
        assert "vector" not in kinds
        assert kinds <= {"string", "bool", "int", "float", "timestamp", "date"}


# (3) format -----------------------------------------------------------------


def test_document_round_trip(db_session):
    s = _taken_down(db_session)
    rows = s.repository.export_tombstone_support()
    text = build_document(rows, created_at=RESTORED_AT)
    parsed, created_at = parse_document(text)
    assert created_at == RESTORED_AT and created_at.tzinfo is not None
    assert json.loads(text)["format"] == TOMBSTONE_FORMAT
    assert tuple(parsed) == TOMBSTONE_SUPPORT_TABLES
    for name in TOMBSTONE_SUPPORT_TABLES:
        assert [r["id"] for r in parsed[name]] == [r["id"] for r in rows[name]]
    document = next(r for r in parsed["document"] if r["id"] == str(s.drop.id))
    assert datetime.fromisoformat(document["retired_at"]).tzinfo is not None


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        json.dumps({"format": 2, "created_at": "2026-11-01T00:00:00+00:00", "rows": {}}),
        json.dumps({"created_at": "2026-11-01T00:00:00+00:00", "rows": {}}),
        json.dumps({"format": 1, "created_at": "2026-11-01T00:00:00", "rows": {}}),
        json.dumps({"format": 1, "created_at": "yesterday", "rows": {}}),
        json.dumps({"format": 1, "created_at": "2026-11-01T00:00:00+00:00"}),
        json.dumps({
            "format": 1, "created_at": "2026-11-01T00:00:00+00:00",
            "rows": {name: [] for name in TOMBSTONE_SUPPORT_TABLES[:-1]},
        }),
        json.dumps({
            "format": 1, "created_at": "2026-11-01T00:00:00+00:00",
            "rows": {**{n: [] for n in TOMBSTONE_SUPPORT_TABLES}, "work": ["x"]},
        }),
    ],
)
def test_parse_rejects_broken_documents(text):
    with pytest.raises(ValueError):
        parse_document(text)


# (4) restore ----------------------------------------------------------------


def _empty_environment(db_session):
    """Support rows of a takedown scenario, with all user and knowledge rows gone."""
    s = _taken_down(db_session)
    support = s.repository.export_tombstone_support()
    _wipe(db_session, reversed(USER_TABLES))
    _wipe(db_session, reversed(KNOWLEDGE_TABLES))
    return s, support


def test_restore_into_an_empty_environment(db_session):
    s, support = _empty_environment(db_session)
    rows, _ = parse_document(build_document(support, created_at=RESTORED_AT))
    s.repository.restore_tombstone_support(rows, restored_at=RESTORED_AT)

    documents = {str(r["id"]): r for r in _table_rows(db_session, "document")}
    assert set(documents) == {str(s.drop.id), str(s.keep.id)}
    assert documents[str(s.drop.id)]["retired_at"] is not None
    # A live parent the older dump does not know counts as retired.
    assert documents[str(s.keep.id)]["retired_at"] == RESTORED_AT
    works = {str(r["id"]): r for r in _table_rows(db_session, "work")}
    assert works[str(s.keep.work_id)]["retired_at"] == RESTORED_AT
    (edge,) = _table_rows(db_session, "edge")
    assert edge["revoked_at"] is not None and edge["retired_at"] is not None
    assert len(_table_rows(db_session, "delivery")) == 1
    assert len(_table_rows(db_session, "source")) == 1


def test_restored_rows_have_no_classification_and_stay_invisible(db_session):
    s, support = _empty_environment(db_session)
    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)
    db_session.expire_all()

    assert _table_rows(db_session, "rights_classification") == []
    assert _table_rows(db_session, "segment") == []
    documents = PostgresDocumentRepository(db_session)
    assert documents.list_documents_for_jurisdiction("DE") == []
    assert documents.list_exportable_documents_for_jurisdiction("DE") == []
    # source and delivery are provenance rows; the gate exports them on their
    # own (as before this feature). Everything derived from documents stays empty.
    for table in KNOWLEDGE_TABLES[2:]:
        assert [r for batch in s.repository.iter_exportable_rows(table) for r in batch] == []


def test_restore_defers_merged_into_work_id(db_session):
    s, support = _empty_environment(db_session)
    # The child sorts (and is inserted) before the work it is merged into.
    template = dict(support["work"][0])
    child = {**template, "id": "00000000-0000-4000-8000-000000000001",
             "merged_into_work_id": "ffffffff-ffff-4fff-8fff-ffffffffffff"}
    parent = {**template, "id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
              "merged_into_work_id": None}
    support["work"] = [child, parent, *support["work"]]
    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)

    works = {str(r["id"]): r for r in _table_rows(db_session, "work")}
    assert str(works[child["id"]]["merged_into_work_id"]) == parent["id"]


def test_restore_never_changes_existing_rows_and_is_idempotent(db_session):
    s, support = _empty_environment(db_session)
    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)
    document = Base.metadata.tables["document"]
    work = Base.metadata.tables["work"]
    db_session.execute(
        sa.update(document).where(document.c.id == s.keep.id).values(edition="changed")
    )
    db_session.execute(
        sa.update(work).where(work.c.id == s.keep.work_id).values(retired_at=None)
    )
    before = {name: _table_rows(db_session, name) for name in TOMBSTONE_SUPPORT_TABLES}

    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT.replace(year=2030))
    after = {name: _table_rows(db_session, name) for name in TOMBSTONE_SUPPORT_TABLES}
    assert after == before


def test_restore_does_not_touch_merged_into_of_existing_work(db_session):
    s, support = _empty_environment(db_session)
    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)
    other_work = uuid.uuid4()
    work = Base.metadata.tables["work"]
    template = db_session.execute(sa.select(work)).first()._mapping
    db_session.execute(sa.insert(work).values({**template, "id": other_work}))
    # The existing KEEP work stays unmerged although the file says otherwise.
    row = next(r for r in support["work"] if r["id"] == str(s.keep.work_id))
    row["merged_into_work_id"] = str(other_work)
    s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)
    (kept,) = [r for r in _table_rows(db_session, "work") if r["id"] == s.keep.work_id]
    assert kept["merged_into_work_id"] is None


def test_restore_rejects_foreign_columns(db_session):
    s, support = _empty_environment(db_session)
    support["work"][0]["surprise"] = 1
    with pytest.raises(ValueError):
        s.repository.restore_tombstone_support(support, restored_at=RESTORED_AT)


# (5) end to end: the TP4 rollback --------------------------------------------


def test_rollback_restores_user_rows_without_foreign_key_errors(db_session):
    s = _taken_down(db_session)
    # A retired-notification bookkeeping row, as the notifier writes it.
    from normly_core.graph.postgres.repositories import PostgresNotifiedRetirementRepository

    PostgresNotifiedRetirementRepository(db_session).mark_notified(
        account_id=s.account.id, work_id=s.drop.work_id, document_id=s.drop.id,
        retired_at=RESTORED_AT,
    )
    db_session.flush()

    # Backup: tombstone support plus the user rows, as the backup would hold them.
    document_text = build_document(
        s.repository.export_tombstone_support(), created_at=RESTORED_AT
    )
    user_rows = {name: _table_rows(db_session, name) for name in USER_TABLES}
    pointing = ("watchlist", "notification", "rights_notification_baseline", "notified_edge",
                "notified_retirement", "chat_message_citation")
    assert all(user_rows[name] for name in pointing)
    live_dump = _dump(s.repository)  # the then-live set: no retired document in it
    assert str(s.drop.id) not in _ids(live_dump["document"])

    # Rollback: fresh database, older dump imported, then the tombstones, then user data.
    _wipe(db_session, reversed(USER_TABLES))
    _wipe(db_session, reversed(KNOWLEDGE_TABLES))
    s.repository.replace_knowledge_base(_frozen(live_dump), record=LATER)

    def reinsert():
        for name in USER_TABLES:
            if user_rows[name]:
                db_session.execute(sa.insert(Base.metadata.tables[name]), user_rows[name])
        db_session.flush()

    # Without the tombstones the user rows violate their foreign keys.
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            reinsert()

    rows, created_at = parse_document(document_text)
    s.repository.restore_tombstone_support(rows, restored_at=created_at)
    reinsert()

    for name in USER_TABLES:
        assert len(_table_rows(db_session, name)) == len(user_rows[name]), name


# (6) CLI against the real test database --------------------------------------


class _BorrowedSession:
    """Lets the CLI use the test transaction: commit flushes, close is a no-op."""

    def __init__(self, session):
        self._session = session
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        self.committed = True
        self._session.flush()

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.fixture()
def cli_on_test_db(monkeypatch, db_session):
    monkeypatch.setenv("NORMLY_DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:1/z")
    borrowed = _BorrowedSession(db_session)
    monkeypatch.setattr(cli, "create_engine", lambda url: type("E", (), {"dispose": lambda self: None})())
    monkeypatch.setattr(cli, "Session", lambda engine: borrowed)
    return borrowed


def test_cli_export_then_import_round_trip(db_session, cli_on_test_db, monkeypatch, capsys):
    s = _taken_down(db_session)
    expected = s.repository.export_tombstone_support()

    assert cli.main(["export-tombstones"]) == 0
    printed = capsys.readouterr().out
    rows, _ = parse_document(printed)
    assert [r["id"] for r in rows["document"]] == [r["id"] for r in expected["document"]]

    _wipe(db_session, reversed(USER_TABLES))
    _wipe(db_session, reversed(KNOWLEDGE_TABLES))
    monkeypatch.setattr("sys.stdin", io.StringIO(printed))
    assert cli.main(["import-tombstones"]) == 0
    assert "restored tombstone support: 7 rows" in capsys.readouterr().out
    assert cli_on_test_db.committed
    assert len(_table_rows(db_session, "document")) == 2


def test_cli_import_of_a_broken_document_changes_nothing(
    db_session, cli_on_test_db, monkeypatch, capsys
):
    s = _taken_down(db_session)
    def counts():
        return {n: len(_table_rows(db_session, n)) for n in KNOWLEDGE_TABLES}

    before = counts()
    monkeypatch.setattr("sys.stdin", io.StringIO('{"format": 2}'))
    assert cli.main(["import-tombstones"]) == 1
    assert "invalid tombstone document" in capsys.readouterr().err
    assert not cli_on_test_db.committed
    assert counts() == before
    assert s.drop.id
