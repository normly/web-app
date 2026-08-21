# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import os

import pytest

from normly_chat.accounts_client import AccountsClient

pytestmark = pytest.mark.skipif(
    "NORMLY_TEST_ACCOUNTS_BASE_URL" not in os.environ,
    reason="requires a running accounts/ process; set NORMLY_TEST_ACCOUNTS_BASE_URL",
)


@pytest.fixture()
def accounts_client():
    return AccountsClient(base_url=os.environ["NORMLY_TEST_ACCOUNTS_BASE_URL"])


def test_validate_session_returns_none_for_an_unknown_token(accounts_client):
    assert accounts_client.validate_session("not-a-real-token") is None
