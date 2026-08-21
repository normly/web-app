# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_accounts.security import generate_token, hash_password, verify_password


def test_hash_password_produces_a_verifiable_but_different_string():
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("correct horse battery staple")

    assert verify_password("wrong password", hashed) is False


def test_hash_password_is_salted_differently_each_time():
    first = hash_password("same password")
    second = hash_password("same password")

    assert first != second
    assert verify_password("same password", first) is True
    assert verify_password("same password", second) is True


def test_generate_token_produces_url_safe_unique_values():
    a = generate_token()
    b = generate_token()

    assert a != b
    assert len(a) >= 32
    assert all(c.isalnum() or c in "-_" for c in a)
