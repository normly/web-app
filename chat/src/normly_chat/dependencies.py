# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from normly_chat.accounts_client import AccountsClient
from normly_chat.api_client import ApiClient
from normly_chat.ollama_client import OllamaClient


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


def get_ollama_client(request: Request) -> "OllamaClient":
    return request.app.state.ollama_client
