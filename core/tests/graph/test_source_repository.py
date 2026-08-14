# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from datetime import date

import pytest

from normly_core.graph.domain import LegalBasisCategory
from normly_core.graph.postgres.repositories import PostgresSourceRepository


def test_create_and_get_source(db_session):
    repo = PostgresSourceRepository(db_session)

    source = repo.create_source(
        publisher="EUR-Lex",
        retrieval_path="https://eur-lex.europa.eu/oj/direct-access.html",
        legal_basis_category=LegalBasisCategory.A,
        jurisdiction="EU",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
    )

    fetched = repo.get_source(source.id)
    assert fetched == source


def test_category_d_source_cannot_be_marked_as_commercial_catalog(db_session):
    repo = PostgresSourceRepository(db_session)

    with pytest.raises(Exception):
        repo.create_source(
            publisher="DIN Media",
            retrieval_path="https://nautos.de",
            legal_basis_category=LegalBasisCategory.D,
            jurisdiction="DE",
            reviewed_at=date(2026, 1, 15),
            responsible_person="J. Weber",
            commercial_catalog=True,
        )


def test_category_c_source_without_contract_reference_is_rejected(db_session):
    repo = PostgresSourceRepository(db_session)

    with pytest.raises(Exception):
        repo.create_source(
            publisher="Austrian Standards",
            retrieval_path="sftp://delivery.austrian-standards.at",
            legal_basis_category=LegalBasisCategory.C,
            jurisdiction="AT",
            reviewed_at=date(2026, 1, 15),
            responsible_person="J. Weber",
            contract_reference=None,
        )


def test_category_c_source_with_contract_reference_succeeds(db_session):
    repo = PostgresSourceRepository(db_session)

    source = repo.create_source(
        publisher="Austrian Standards",
        retrieval_path="sftp://delivery.austrian-standards.at",
        legal_basis_category=LegalBasisCategory.C,
        jurisdiction="AT",
        reviewed_at=date(2026, 1, 15),
        responsible_person="J. Weber",
        contract_reference="CONTRACT-2026-001",
    )

    assert source.contract_reference == "CONTRACT-2026-001"
