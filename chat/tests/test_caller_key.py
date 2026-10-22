# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from starlette.requests import Request

from normly_chat.caller_key import anonymous_caller_key


def _request(headers: dict[str, str], client=("10.0.0.9", 1234)) -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/v1/chat",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": client,
    })


def test_the_key_combines_anon_id_and_the_rightmost_forwarded_address():
    request = _request({"X-Normly-Anon-Id": "abc", "X-Forwarded-For": "6.6.6.6, 1.2.3.4"})
    assert anonymous_caller_key(request) == "anon:abc:1.2.3.4"


def test_without_headers_the_connection_address_is_used():
    assert anonymous_caller_key(_request({})) == "anon:10.0.0.9"
