# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    with Session(engine) as session:
        yield session
        session.commit()


def get_embedding_model(request: Request):
    return request.app.state.embedding_model
