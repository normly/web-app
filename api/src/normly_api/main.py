# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import create_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ["NORMLY_DATABASE_URL"]
    engine = create_engine(database_url)
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    return FastAPI(
        title="normly API",
        version="1.0.0",
        description=(
            "Deterministic reference-graph queries over normly's free content. "
            "No authentication required for free-tier jurisdictions."
        ),
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        lifespan=lifespan,
    )


app = create_app()
