# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import create_engine

from normly_core.pipeline.embeddings import EmbeddingModel


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ["NORMLY_DATABASE_URL"]
    engine = create_engine(database_url)
    app.state.engine = engine

    # Loaded once at startup, not per-request: this is the same real,
    # multi-hundred-MB model the ingestion pipeline uses -- reusing the
    # single already-established EmbeddingModel class, not a second one.
    app.state.embedding_model = EmbeddingModel()

    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="normly Chat",
        version="1.0.0",
        description="Natural-language chat over the reference graph.",
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        lifespan=lifespan,
    )
    return app


app = create_app()
