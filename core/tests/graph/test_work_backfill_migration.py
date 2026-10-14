# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

CORE_DIR = Path(__file__).parents[2]


def test_backfill_groups_documents_by_replaces_and_adopted_from_edges(db_url, migrated_engine):
    # Drives Alembic directly against the shared, session-scoped
    # `migrated_engine`, like test_migration_determinism.py -- mutates
    # schema state in place and relies on non-parallel test ordering to
    # leave the database at "head" again before any other test runs.
    alembic_cfg = Config(str(CORE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(CORE_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.downgrade(alembic_cfg, "0021")

    source_id = uuid.uuid4()
    delivery_id = uuid.uuid4()
    doc_2015, doc_2018, doc_bs, doc_unrelated = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    )

    # This test writes fixture rows through `migrated_engine.begin()`, which
    # commits -- unlike the transactional `db_session` fixture most other
    # tests use, nothing rolls this back. The `try/finally` below cleans up
    # those rows even if an assertion fails, so they don't leak into the
    # shared test database for the rest of the session -- same pattern as
    # `test_cli.py`'s `committed_db` fixture (plus `work`, which that
    # fixture's table list predates).
    try:
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO source (id, publisher, retrieval_path, legal_basis_category, "
                    "jurisdiction, reviewed_at, responsible_person, commercial_catalog) "
                    "VALUES (:id, 'Test', 'file:///dev/null', 'A', 'DE', CURRENT_DATE, 'Test Reviewer', false)"
                ),
                {"id": source_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO delivery (id, source_id, content_hash, ingested_at) "
                    "VALUES (:id, :source_id, 'sha256:backfill-fixture', now())"
                ),
                {"id": delivery_id, "source_id": source_id},
            )
            for doc_id, issuer, number, edition in [
                (doc_2015, "DIN", "EN ISO 9001", "2015"),
                (doc_2018, "DIN", "EN ISO 9001", "2018"),
                (doc_bs, "BS", "EN ISO 9001", "2018"),
                (doc_unrelated, "DGUV", "Vorschrift 1", "2020"),
            ]:
                connection.execute(
                    sa.text(
                        "INSERT INTO document (id, origin_issuer, origin_number, edition, "
                        "created_via_delivery_id) VALUES (:id, :issuer, :number, :edition, :delivery_id)"
                    ),
                    {
                        "id": doc_id, "issuer": issuer, "number": number, "edition": edition,
                        "delivery_id": delivery_id,
                    },
                )
            # doc_2018 REPLACES doc_2015; doc_bs is ADOPTED_FROM doc_2018 --
            # all three must end up in one Work. doc_unrelated shares no edge
            # with them and must get its own.
            for from_id, to_id, edge_type in [
                (doc_2018, doc_2015, "replaces"),
                (doc_bs, doc_2018, "adopted_from"),
            ]:
                connection.execute(
                    sa.text(
                        "INSERT INTO edge (id, from_document_id, to_document_id, edge_type, layer, "
                        "delivery_id) VALUES (:id, :from_id, :to_id, :edge_type, 'free', :delivery_id)"
                    ),
                    {
                        "id": uuid.uuid4(), "from_id": from_id, "to_id": to_id,
                        "edge_type": edge_type, "delivery_id": delivery_id,
                    },
                )

        command.upgrade(alembic_cfg, "0022")

        with migrated_engine.connect() as connection:
            rows = connection.execute(
                sa.text("SELECT id, work_id FROM document WHERE id IN :ids").bindparams(
                    sa.bindparam("ids", expanding=True)
                ),
                {"ids": [doc_2015, doc_2018, doc_bs, doc_unrelated]},
            ).all()

        work_id_by_doc = {row.id: row.work_id for row in rows}
        assert work_id_by_doc[doc_2015] == work_id_by_doc[doc_2018] == work_id_by_doc[doc_bs]
        assert work_id_by_doc[doc_unrelated] != work_id_by_doc[doc_2015]
        assert all(work_id is not None for work_id in work_id_by_doc.values())
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(
                sa.text("TRUNCATE edge, document, delivery, source, work CASCADE")
            )
        command.upgrade(alembic_cfg, "head")
