# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from __future__ import annotations

import uuid

import httpx


# api/ is a sibling service on the same network, not an LLM generation call:
# a request that has not answered in ten seconds is a failure worth surfacing
# as a 503, not something to keep waiting on. Set explicitly rather than
# inheriting httpx's implicit 5s default.
_TIMEOUT_SECONDS = 10.0


class ApiClient:
    """
    Thin httpx wrapper over api/'s public HTTP interface -- chat/ never
    imports api/'s routers or touches its database tables directly, exactly
    like an external third-party consumer of the same public API.
    """

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def search_document(
        self, issuer: str, designation: str, jurisdiction: str,
    ) -> dict | None:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
            response = http.get(
                f"{self._base_url}/v1/documents",
                params={"issuer": issuer, "designation": designation, "jurisdiction": jurisdiction},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_validity(self, document_id: uuid.UUID, jurisdiction: str) -> dict | None:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
            response = http.get(
                f"{self._base_url}/v1/documents/{document_id}/validity",
                params={"jurisdiction": jurisdiction},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_edges(self, document_id: uuid.UUID, jurisdiction: str) -> list[dict] | None:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
            response = http.get(
                f"{self._base_url}/v1/documents/{document_id}/edges",
                params={"jurisdiction": jurisdiction},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
