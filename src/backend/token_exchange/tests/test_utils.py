"""Menshen: utils tests for the token_exchange application."""

import pytest

from token_exchange.utils import generate_client_secret


def test_generate_client_secret_default_length():
    """Test the generate_client_secret utility default length."""
    secret = generate_client_secret()
    assert isinstance(secret, str)
    assert len(secret) == 64


@pytest.mark.parametrize("length", [32, 48, 64, 128])
def test_generate_client_secret_length(length):
    """Test the generate_client_secret utility expected length."""
    assert len(generate_client_secret(length)) == length
