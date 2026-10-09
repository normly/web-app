# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest

from normly_core.exchange.signing import SignatureError, generate_keypair, sign, verify


def test_sign_and_verify_roundtrip():
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, b"manifest")
    assert len(signature) == 64
    verify(public_pem, b"manifest", signature)


def test_verify_rejects_tampered_data():
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, b"manifest")
    with pytest.raises(SignatureError):
        verify(public_pem, b"manifesT", signature)


def test_verify_rejects_other_key():
    private_pem, _ = generate_keypair()
    _, other_public = generate_keypair()
    with pytest.raises(SignatureError):
        verify(other_public, b"m", sign(private_pem, b"m"))
