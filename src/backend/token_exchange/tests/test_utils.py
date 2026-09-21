"""Menshen: utils tests for the token_exchange application."""

import string

import pytest

from token_exchange.utils import generate_client_secret


def test_generate_client_secret_defaults():
    """Test the generate_client_secret utility default length and content."""
    secret = generate_client_secret()
    assert isinstance(secret, str)
    assert len(secret) == 64
    assert all(c in (string.ascii_letters + string.digits) for c in secret)


def test_generate_client_secret_with_special_chars():
    """Test the generate_client_secret utility default length."""
    secret = generate_client_secret(use_special_chars=True)
    assert isinstance(secret, str)
    # This test may be flaky
    assert any(c not in (string.ascii_letters + string.digits) for c in secret)


@pytest.mark.parametrize("length", [32, 48, 64, 128])
def test_generate_client_secret_length(length):
    """Test the generate_client_secret utility expected length."""
    assert len(generate_client_secret(length)) == length
