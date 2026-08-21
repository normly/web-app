# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os

import pytest

from normly_chat.api_client import ApiClient

pytestmark = pytest.mark.skipif(
    "NORMLY_TEST_API_BASE_URL" not in os.environ,
    reason="requires a running api/ process; set NORMLY_TEST_API_BASE_URL",
)


@pytest.fixture()
def api_client():
    return ApiClient(base_url=os.environ["NORMLY_TEST_API_BASE_URL"])


def test_search_document_returns_none_for_an_unknown_designation(api_client):
    assert api_client.search_document("DIN", "no such designation", "DE") is None
