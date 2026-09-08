# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import ast
import inspect
from pathlib import Path

from normly_core.graph import domain as graph_domain
from normly_core.graph.domain import DocumentRepository, EmbeddingRepository
from normly_core.graph.postgres.repositories import (
    PostgresDocumentRepository,
    PostgresEmbeddingRepository,
)


def test_domain_module_does_not_import_sqlalchemy():
    domain_path = (
        Path(__file__).parents[2] / "src" / "normly_core" / "graph" / "domain.py"
    )
    tree = ast.parse(domain_path.read_text())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "sqlalchemy" not in imported_names


UNGATED_READS = ("get_document_unchecked", "list_designations", "list_titles")


def test_document_repository_protocol_exposes_no_ungated_read():
    """
    The design spec: "Es gibt keine Methode, die Dokumente ungefiltert
    zurückgibt." The ungated reads remain available on the concrete
    implementation for pipeline and identity-resolution use, but they are not
    part of the public Protocol any API layer programs against.
    """
    protocol_methods = {
        name for name in vars(DocumentRepository) if not name.startswith("_")
    }

    assert protocol_methods.isdisjoint(UNGATED_READS)
    assert {"get_document_for_jurisdiction", "list_documents_for_jurisdiction"} <= (
        protocol_methods
    )


def _repository_protocols():
    """
    Every repository Protocol in `graph.domain`, discovered rather than listed.

    A Protocol added later is caught by the guard below without anyone
    remembering to register it here — which is exactly how the pipeline's three
    new Protocols slipped past the earlier version of this test.
    """
    for name, obj in vars(graph_domain).items():
        if not inspect.isclass(obj) or not name.endswith("Repository"):
            continue
        if getattr(obj, "_is_protocol", False):
            yield name, obj


# Reads that serve no document content and therefore need no jurisdiction.
# Every entry carries its reason; nothing belongs here for convenience.
JURISDICTION_EXEMPT_READS = {
    # Registry metadata (publisher, legal basis, review date) — the entry that
    # licenses the ingestion, not the content it produced.
    "SourceRepository.get_source",
    # Delivery bookkeeping: what lineage and revocation are anchored on.
    "DeliveryRepository.get_delivery",
    # Work is a logical identity spanning document editions/national
    # adoptions -- lifecycle bookkeeping (status, merge target), not
    # rights-gated document content.
    "WorkRepository.get_work",
    # Review-queue listing for staff, not rights-gated content.
    "IdentityResolutionRepository.list_pending_cases",
    # Backfill bookkeeping for the embeddings pipeline -- decides what still
    # needs an embedding, serves no document content to a public caller.
    "DocumentEmbeddingRepository.list_documents_without_embedding",
    # Account identity and session/token lookups: authentication state, not
    # rights-gated document content. Accounts are not jurisdiction-scoped.
    "AccountRepository.get_account_by_id",
    "AccountRepository.get_account_by_email",
    "AccountGoogleIdentityRepository.get_account_by_google_subject",
    "AccountSessionRepository.get_session_by_token",
    "AccountSessionRepository.list_sessions_for_account",
    "ChatRepository.get_session_by_token",
    "ChatRepository.list_sessions_for_account",
    "ChatRepository.list_messages_for_session",
    # Watchlist and notification listings: account-scoped bookkeeping (this
    # account's watches, this account's notifications), not rights-gated
    # document content. Accounts are not jurisdiction-scoped.
    "WatchlistRepository.list_watches_for_account",
    "WatchlistRepository.list_all_watches",
    "NotificationRepository.list_for_account",
    # Internal RIGHTS_CHANGE detector bookkeeping, keyed by
    # trigger_jurisdiction (not "jurisdiction") -- never exposed via any
    # HTTP-reachable method, serves no document content to a public caller.
    "RightsNotificationBaselineRepository.get_baseline",
}


def test_every_protocol_read_takes_a_jurisdiction():
    discovered = {name for name, _ in _repository_protocols()}
    assert {
        "DocumentRepository",
        "SegmentRepository",
        "EmbeddingRepository",
        "IdentityResolutionRepository",
    } <= discovered

    for protocol_name, protocol in _repository_protocols():
        for name in vars(protocol):
            if not name.startswith("list_") and not name.startswith("get_"):
                continue
            qualified = f"{protocol_name}.{name}"
            if qualified in JURISDICTION_EXEMPT_READS:
                continue
            parameters = inspect.signature(getattr(protocol, name)).parameters
            assert "jurisdiction" in parameters, qualified


def test_embedding_repository_protocol_exposes_no_ungated_read():
    """
    `get_embedding_unchecked` is the same split as `get_document_unchecked`: it
    joins no classification, so it stays off the Protocol an API layer programs
    against and keeps a name that says so.
    """
    protocol_methods = {
        name for name in vars(EmbeddingRepository) if not name.startswith("_")
    }

    assert protocol_methods == {"add_embedding"}


def test_ungated_reads_stay_available_on_the_concrete_repository():
    for name in UNGATED_READS:
        assert callable(getattr(PostgresDocumentRepository, name))
    assert callable(PostgresEmbeddingRepository.get_embedding_unchecked)
