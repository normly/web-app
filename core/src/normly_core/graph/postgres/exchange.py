# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Postgres implementation of KnowledgeExchangeRepository.

The export gate is evaluated here, in one place (rights classification is the
only gate): a document is exportable when at least one of its classifications
has may_process AND may_export_free, is not revoked, and descends from a
delivery that is not withdrawn and whose source is category A/B/D and not a
commercial catalogue. Every other exported row is derived from exportable
documents, so no exported row can point at a missing parent.
"""

import enum
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from normly_core.exchange.tables import (
    DETACHED_REFERENCES,
    EXCLUDED_EXCHANGE_COLUMNS,
    KNOWLEDGE_TABLES,
    PURGE_TABLES,
    TOMBSTONE_TABLES,
)
from normly_core.graph.domain import (
    ExchangeColumn,
    ImportBlockedError,
    ImportRecord,
    Layer,
    LegalBasisCategory,
    RowBatches,
)
from normly_core.graph.postgres.orm import (
    Base,
    DeliveryORM,
    DocumentORM,
    EdgeORM,
    KnowledgeBaseImportORM,
    RightsClassificationORM,
    SegmentORM,
    SourceORM,
    WorkORM,
)

_FREE_CATEGORIES = (LegalBasisCategory.A, LegalBasisCategory.B, LegalBasisCategory.D)
_WRITE_BATCH = 2000

PUBLISHED_ROLE = "normly maintainers"
"""
Role label published in place of personal names. The dump is public, so the
columns listed in ``_PERSONAL_NAME_COLUMNS`` leave the database as this
constant. The dump never carries a name; whatever names an ingestion operator
enters live only in that operator's own database. An import overwrites those
columns with the label, so never import a dump into an ingestion database
(ADR-025).
"""

_PERSONAL_NAME_COLUMNS = {
    "source": "responsible_person",
    "rights_classification": "classified_by",
}


def _eligible_deliveries():
    return (
        select(DeliveryORM.id)
        .join(SourceORM, SourceORM.id == DeliveryORM.source_id)
        .where(
            DeliveryORM.withdrawn_at.is_(None),
            SourceORM.legal_basis_category.in_(_FREE_CATEGORIES),
            SourceORM.commercial_catalog.is_(False),
        )
    )


def _exportable_rights():
    rc = RightsClassificationORM
    return select(rc.document_id, rc.jurisdiction).where(
        rc.may_process.is_(True),
        rc.may_export_free.is_(True),
        rc.revoked_at.is_(None),
        rc.delivery_id.in_(_eligible_deliveries()),
    )


def _eligible_documents():
    return select(DocumentORM.id).where(
        DocumentORM.id.in_(select(_exportable_rights().subquery().c.document_id)),
        DocumentORM.created_via_delivery_id.in_(_eligible_deliveries()),
    )


def _eligible_works():
    """
    Works of exportable documents, their merge targets, and every Work that
    was merged into one of those. The merged-away Works have no document
    pointing at them any more, but importing instances must still see them
    so the single-hop redirect (get_work) keeps resolving.
    """
    document_works = select(DocumentORM.work_id.label("id")).where(
        DocumentORM.id.in_(_eligible_documents())
    )
    targets = select(WorkORM.merged_into_work_id.label("id")).where(
        WorkORM.id.in_(document_works),
        WorkORM.merged_into_work_id.is_not(None),
    )
    base = sa.union(document_works, targets).subquery()
    reached = select(base.c.id).cte("exportable_work", recursive=True)
    merged_away = select(WorkORM.id).join(reached, WorkORM.merged_into_work_id == reached.c.id)
    reached = reached.union(merged_away)
    return select(reached.c.id)


def _statement(table_name: str):
    table = Base.metadata.tables[table_name]
    delivery_ok = table.c.delivery_id.in_(_eligible_deliveries()) if "delivery_id" in table.c else None

    def with_delivery(*conditions):
        parts = list(conditions)
        if delivery_ok is not None:
            parts.append(delivery_ok)
        return select(table).where(*parts)

    if table_name == "source":
        return select(table).where(
            table.c.id.in_(
                select(DeliveryORM.source_id).where(DeliveryORM.id.in_(_eligible_deliveries()))
            )
        )
    if table_name == "delivery":
        return select(table).where(table.c.id.in_(_eligible_deliveries()))
    if table_name == "work":
        return select(table).where(table.c.id.in_(_eligible_works()))
    if table_name == "document":
        return select(table).where(table.c.id.in_(_eligible_documents()))
    if table_name in ("document_designation", "document_title", "document_embedding", "segment"):
        return with_delivery(table.c.document_id.in_(_eligible_documents()))
    if table_name == "rights_classification":
        rc = RightsClassificationORM
        return select(table).where(
            rc.may_process.is_(True),
            rc.may_export_free.is_(True),
            rc.revoked_at.is_(None),
            rc.delivery_id.in_(_eligible_deliveries()),
            rc.document_id.in_(_eligible_documents()),
        )
    if table_name == "edge":
        left = _exportable_rights().subquery("left_rights")
        right = _exportable_rights().subquery("right_rights")
        shared = (
            select(sa.literal(1))
            .select_from(left)
            .join(right, right.c.jurisdiction == left.c.jurisdiction)
            .where(
                left.c.document_id == EdgeORM.from_document_id,
                right.c.document_id == EdgeORM.to_document_id,
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == left.c.jurisdiction),
            )
            .exists()
        )
        return select(table).where(
            EdgeORM.layer == Layer.FREE,
            EdgeORM.revoked_at.is_(None),
            EdgeORM.delivery_id.in_(_eligible_deliveries()),
            EdgeORM.from_document_id.in_(_eligible_documents()),
            EdgeORM.to_document_id.in_(_eligible_documents()),
            shared,
        )
    if table_name == "embedding":
        exported_segments = select(SegmentORM.id).where(
            SegmentORM.document_id.in_(_eligible_documents()),
            SegmentORM.delivery_id.in_(_eligible_deliveries()),
        )
        return with_delivery(table.c.segment_id.in_(exported_segments))
    raise ValueError(f"not a knowledge-base table: {table_name!r}")


def _kind(column: sa.Column) -> str:
    column_type = column.type
    if isinstance(column_type, Vector):
        return "vector"
    if isinstance(column_type, sa.Boolean):
        return "bool"
    if isinstance(column_type, sa.Integer):
        return "int"
    if isinstance(column_type, sa.Float):
        return "float"
    if isinstance(column_type, sa.DateTime):
        return "timestamp"
    if isinstance(column_type, sa.Date):
        return "date"
    return "string"  # String, Text, Uuid, Enum


def _to_exchange(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if hasattr(value, "tolist"):  # numpy vector from pgvector
        return [float(x) for x in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    return value


def _from_exchange(column: sa.Column, value: Any) -> Any:
    if value is None:
        return None
    column_type = column.type
    if isinstance(column_type, (postgresql.UUID, sa.Uuid)):
        return uuid.UUID(value)
    if isinstance(column_type, sa.Enum) and column_type.enum_class is not None:
        return column_type.enum_class(value)
    return value


def _exchange_columns(sa_table: sa.Table) -> list[sa.Column]:
    excluded = set(EXCLUDED_EXCHANGE_COLUMNS.get(sa_table.name, ()))
    return [c for c in sa_table.columns if c.name not in excluded]


def _primary_key(table: sa.Table) -> list[sa.Column]:
    return list(table.primary_key.columns)


class PostgresKnowledgeExchangeRepository:
    def __init__(self, session: Session):
        self._session = session

    def exchange_columns(self, table: str) -> list[ExchangeColumn]:
        return [ExchangeColumn(c.name, _kind(c)) for c in _exchange_columns(Base.metadata.tables[table])]

    def iter_exportable_rows(
        self, table: str, *, batch_size: int = 5000
    ) -> Iterator[list[dict[str, Any]]]:
        sa_table = Base.metadata.tables[table]
        statement = _statement(table)
        masked_name = _PERSONAL_NAME_COLUMNS.get(table)
        # Fail closed: a renamed column raises KeyError instead of silently
        # exporting the real value.
        masked = sa_table.c[masked_name] if masked_name is not None else None
        # The name never leaves the database: the column is replaced in the
        # statement itself, so the export gate stays in one place. Columns
        # outside the exchange format (retired_at) are not selected at all.
        statement = statement.with_only_columns(
            *(
                sa.literal(PUBLISHED_ROLE, type_=column.type).label(column.name)
                if column is masked
                else column
                for column in _exchange_columns(sa_table)
            )
        )
        statement = statement.order_by(*_primary_key(sa_table))
        # Per-statement options: Connection.execution_options() would mutate
        # the shared session connection and break its savepoint handling.
        result = self._session.connection().execute(
            statement,
            execution_options={"yield_per": batch_size, "stream_results": True},
        )
        for partition in result.partitions():
            yield [
                {name: _to_exchange(value) for name, value in row._mapping.items()}
                for row in partition
            ]

    def exportable_deliveries(self) -> list[tuple[str, str, str]]:
        rows = self._session.execute(
            select(DeliveryORM.id, SourceORM.publisher, SourceORM.legal_basis_category)
            .join(SourceORM, SourceORM.id == DeliveryORM.source_id)
            .where(DeliveryORM.id.in_(_eligible_deliveries()))
            .order_by(DeliveryORM.id)
        )
        return [(str(i), publisher, category.value) for i, publisher, category in rows]

    def imported_version(self) -> ImportRecord | None:
        row = self._session.execute(select(KnowledgeBaseImportORM)).scalar_one_or_none()
        if row is None:
            return None
        return ImportRecord(
            row.dump_version, row.exchange_schema_version,
            row.embedding_model_revision, row.imported_at,
        )

    def replace_knowledge_base(
        self, tables: Mapping[str, RowBatches], *, record: ImportRecord
    ) -> None:
        """
        A takedown always wins: user data never blocks an import (ADR-026).
        What the dump no longer contains is handled by class:

        * content and derivations (PURGE_TABLES) are deleted physically,
          after user references to purged segments were cleared;
        * identifier rows (TOMBSTONE_TABLES) stay with `retired_at` set, so
          watchlists, notifications and citations keep their targets; a row
          that returns clears `retired_at` again;
        * provenance (delivery, source) stays; a missing delivery gets
          `withdrawn_at`.

        Content is deleted BEFORE the upsert so that a purged row cannot
        collide with a new row on a natural unique key. Nothing is committed.
        ImportBlockedError remains only as a last guard for an unexpected
        foreign key; after it the caller must roll back (or use a savepoint).
        """
        connection = self._session.connection()
        now = record.imported_at or datetime.now(timezone.utc)
        keep_tables = self._load_keys(connection, tables)
        step = "load"
        try:
            step = "detach"
            self._detach_missing_references(connection, keep_tables)
            for name in reversed(PURGE_TABLES):
                step = name
                self._delete_missing(connection, name, keep_tables)
            for name in KNOWLEDGE_TABLES:
                step = name
                self._upsert(connection, name, tables[name])
            for name in TOMBSTONE_TABLES:
                step = name
                self._retire_missing(connection, name, keep_tables, now)
            step = "delivery"
            self._withdraw_missing_deliveries(connection, keep_tables, now)
        except IntegrityError as exc:
            raise ImportBlockedError(step, str(exc.orig).splitlines()[0]) from exc
        self._write_record(record)
        # The caller owns the transaction, so ON COMMIT DROP alone would leave
        # the temp tables in place for a second call in the same transaction.
        for keep in keep_tables.values():
            keep.drop(connection)

    def _load_keys(self, connection, tables: Mapping[str, RowBatches]) -> dict[str, sa.Table]:
        keep_tables: dict[str, sa.Table] = {}
        for name in KNOWLEDGE_TABLES:
            sa_table = Base.metadata.tables[name]
            key_columns = _primary_key(sa_table)
            keep = sa.Table(
                f"_kb_keep_{name}", sa.MetaData(),
                *[sa.Column(c.name, c.type) for c in key_columns],
                prefixes=["TEMPORARY"], postgresql_on_commit="DROP",
            )
            keep.drop(connection, checkfirst=True)
            keep.create(connection)
            for batch in tables[name]():
                rows = [
                    {c.name: _from_exchange(c, row[c.name]) for c in key_columns}
                    for row in batch
                ]
                for start in range(0, len(rows), _WRITE_BATCH):
                    connection.execute(sa.insert(keep), rows[start:start + _WRITE_BATCH])
            keep_tables[name] = keep
        return keep_tables

    @staticmethod
    def _missing(sa_table: sa.Table, keep: sa.Table):
        match = sa.and_(*[keep.c[c.name] == c for c in _primary_key(sa_table)])
        return ~sa.exists().where(match)

    def _delete_missing(
        self, connection, name: str, keep_tables: Mapping[str, sa.Table]
    ) -> None:
        sa_table = Base.metadata.tables[name]
        connection.execute(
            sa.delete(sa_table).where(self._missing(sa_table, keep_tables[name]))
        )

    def _detach_missing_references(
        self, connection, keep_tables: Mapping[str, sa.Table]
    ) -> None:
        for (child_name, column_name), parent_name in DETACHED_REFERENCES.items():
            child = Base.metadata.tables[child_name]
            parent = Base.metadata.tables[parent_name]
            keep = keep_tables[parent_name]
            (parent_key,) = _primary_key(parent)
            referenced = child.c[column_name]
            connection.execute(
                sa.update(child)
                .where(
                    referenced.is_not(None),
                    ~sa.exists().where(keep.c[parent_key.name] == referenced),
                )
                .values({column_name: None})
            )

    def _retire_missing(
        self, connection, name: str, keep_tables: Mapping[str, sa.Table], now: datetime
    ) -> None:
        sa_table = Base.metadata.tables[name]
        connection.execute(
            sa.update(sa_table)
            .where(
                sa_table.c.retired_at.is_(None),
                self._missing(sa_table, keep_tables[name]),
            )
            .values(retired_at=now)
        )

    def _withdraw_missing_deliveries(
        self, connection, keep_tables: Mapping[str, sa.Table], now: datetime
    ) -> None:
        delivery = Base.metadata.tables["delivery"]
        connection.execute(
            sa.update(delivery)
            .where(
                delivery.c.withdrawn_at.is_(None),
                self._missing(delivery, keep_tables["delivery"]),
            )
            .values(withdrawn_at=now)
        )

    def _upsert(self, connection, name: str, batches: RowBatches) -> None:
        sa_table = Base.metadata.tables[name]
        key_names = [c.name for c in _primary_key(sa_table)]
        exchange_columns = _exchange_columns(sa_table)
        # retired_at is not in the dump; a row that is present again is alive.
        retired_at = sa_table.c.retired_at if name in TOMBSTONE_TABLES else None
        value_columns = [c for c in exchange_columns if c.name not in key_names]
        if retired_at is not None:
            value_columns.append(retired_at)
        self_reference = "merged_into_work_id" if name == "work" else None
        deferred: list[dict[str, Any]] = []
        for batch in batches():
            rows = [
                {c.name: _from_exchange(c, row[c.name]) for c in exchange_columns}
                for row in batch
            ]
            if retired_at is not None:
                for row in rows:
                    row["retired_at"] = None
            if self_reference:
                for row in rows:
                    if row[self_reference] is not None:
                        deferred.append(
                            {"id": row["id"], self_reference: row[self_reference]}
                        )
                        row[self_reference] = None
            for start in range(0, len(rows), _WRITE_BATCH):
                chunk = rows[start:start + _WRITE_BATCH]
                insert = pg_insert(sa_table)
                if value_columns:
                    insert = insert.on_conflict_do_update(
                        index_elements=key_names,
                        set_={c.name: insert.excluded[c.name] for c in value_columns},
                    )
                else:
                    insert = insert.on_conflict_do_nothing(index_elements=key_names)
                connection.execute(insert, chunk)
        for item in deferred:
            connection.execute(
                sa.update(sa_table).where(sa_table.c.id == item["id"]).values(
                    {self_reference: item[self_reference]}
                )
            )

    def _write_record(self, record: ImportRecord) -> None:
        insert = pg_insert(KnowledgeBaseImportORM.__table__).values(
            id=1, dump_version=record.dump_version,
            exchange_schema_version=record.exchange_schema_version,
            embedding_model_revision=record.embedding_model_revision,
            imported_at=record.imported_at or datetime.now(timezone.utc),
        )
        self._session.connection().execute(
            insert.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "dump_version": insert.excluded.dump_version,
                    "exchange_schema_version": insert.excluded.exchange_schema_version,
                    "embedding_model_revision": insert.excluded.embedding_model_revision,
                    "imported_at": insert.excluded.imported_at,
                },
            )
        )
