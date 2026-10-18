# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import uuid

import httpx
import pytest

from normly_chat import api_client as api_client_module
from normly_chat.api_client import ApiClient

BASE_URL = "http://api.test"


@pytest.fixture()
def stub_http(monkeypatch):
    """Route ApiClient's httpx.Client through a MockTransport; record requests."""
    requests: list[httpx.Request] = []
    responses: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses["next"]

    real_client = httpx.Client

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(api_client_module.httpx, "Client", factory)
    return requests, responses


def test_get_document_returns_the_json_body_and_requests_the_document(stub_http):
    requests, responses = stub_http
    document_id = uuid.uuid4()
    body = {"id": str(document_id), "origin_issuer": "DIN", "origin_number": "1"}
    responses["next"] = httpx.Response(200, json=body)

    result = ApiClient(BASE_URL).get_document(document_id, "DE")

    assert result == body
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == f"{BASE_URL}/v1/documents/{document_id}?jurisdiction=DE"


def test_get_document_returns_none_for_404(stub_http):
    _, responses = stub_http
    responses["next"] = httpx.Response(404, json={"detail": "not found"})

    assert ApiClient(BASE_URL).get_document(uuid.uuid4(), "DE") is None


def test_get_document_raises_for_500(stub_http):
    _, responses = stub_http
    responses["next"] = httpx.Response(500, json={"detail": "boom"})

    with pytest.raises(httpx.HTTPStatusError):
        ApiClient(BASE_URL).get_document(uuid.uuid4(), "DE")
