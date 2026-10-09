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
from sqlalchemy.orm import Session, aliased

from normly_core.exchange.tables import KNOWLEDGE_TABLES
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
    reached = (
        select(DocumentORM.work_id.label("id"))
        .where(DocumentORM.id.in_(_eligible_documents()))
        .cte("exportable_work", recursive=True)
    )
    parent = select(WorkORM.merged_into_work_id).join(reached, WorkORM.id == reached.c.id).where(
        WorkORM.merged_into_work_id.is_not(None)
    )
    reached = reached.union(parent)
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
        left = aliased(RightsClassificationORM, name="left_rights")
        right = aliased(RightsClassificationORM, name="right_rights")
        shared = (
            select(sa.literal(1))
            .select_from(left)
            .join(right, right.jurisdiction == left.jurisdiction)
            .where(
                left.document_id == EdgeORM.from_document_id,
                right.document_id == EdgeORM.to_document_id,
                left.may_process.is_(True), left.may_export_free.is_(True),
                left.revoked_at.is_(None),
                right.may_process.is_(True), right.may_export_free.is_(True),
                right.revoked_at.is_(None),
                sa.or_(EdgeORM.jurisdiction.is_(None), EdgeORM.jurisdiction == left.jurisdiction),
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


def _primary_key(table: sa.Table) -> list[sa.Column]:
    return list(table.primary_key.columns)


class PostgresKnowledgeExchangeRepository:
    def __init__(self, session: Session):
        self._session = session

    def exchange_columns(self, table: str) -> list[ExchangeColumn]:
        return [ExchangeColumn(c.name, _kind(c)) for c in Base.metadata.tables[table].columns]

    def iter_exportable_rows(
        self, table: str, *, batch_size: int = 5000
    ) -> Iterator[list[dict[str, Any]]]:
        sa_table = Base.metadata.tables[table]
        statement = _statement(table).order_by(*_primary_key(sa_table))
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
        connection = self._session.connection()
        keep_tables = self._load_keys(connection, tables)
        try:
            for name in reversed(KNOWLEDGE_TABLES):
                self._delete_missing(connection, name, keep_tables[name])
        except IntegrityError as exc:
            raise ImportBlockedError(name, str(exc.orig).splitlines()[0]) from exc
        for name in KNOWLEDGE_TABLES:
            self._upsert(connection, name, tables[name])
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

    def _delete_missing(self, connection, name: str, keep: sa.Table) -> None:
        sa_table = Base.metadata.tables[name]
        match = sa.and_(*[keep.c[c.name] == c for c in _primary_key(sa_table)])
        connection.execute(sa.delete(sa_table).where(~sa.exists().where(match)))

    def _upsert(self, connection, name: str, batches: RowBatches) -> None:
        sa_table = Base.metadata.tables[name]
        key_names = [c.name for c in _primary_key(sa_table)]
        value_columns = [c for c in sa_table.columns if c.name not in key_names]
        self_reference = "merged_into_work_id" if name == "work" else None
        deferred: list[dict[str, Any]] = []
        for batch in batches():
            rows = [
                {c.name: _from_exchange(c, row[c.name]) for c in sa_table.columns}
                for row in batch
            ]
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
