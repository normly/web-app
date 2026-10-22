# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Request
from sqlalchemy.orm import Session

from normly_core.graph.postgres.repositories import PostgresLlmUsageRepository

from normly_chat.accounts_client import AccountsClient
from normly_chat.api_client import ApiClient
from normly_chat.budget_guard import BudgetGuard
from normly_chat.budget_settings import BudgetSettings
from normly_chat.llm_client import LlmClient


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()


def get_embedding_model(request: Request):
    return request.app.state.embedding_model


def get_api_client(request: Request) -> ApiClient:
    return request.app.state.api_client


def get_accounts_client(request: Request) -> AccountsClient:
    return request.app.state.accounts_client


def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client


@contextmanager
def usage_repository_scope(engine) -> Iterator[PostgresLlmUsageRepository]:
    # Its own session, committed at once, never the request's: see BudgetGuard.
    # Committed only on a clean exit; on an exception the session closes
    # without commit (rollback).
    with Session(engine) as session:
        yield PostgresLlmUsageRepository(session)
        session.commit()


def get_budget_guard(request: Request) -> BudgetGuard:
    return request.app.state.budget_guard


def get_budget_settings(request: Request) -> BudgetSettings:
    return request.app.state.budget_settings
