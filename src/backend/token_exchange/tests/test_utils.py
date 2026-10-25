"""Menshen: utils tests for the token_exchange application."""

import string

import pytest

from token_exchange.utils import generate_client_secret, hash_token


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


def test_hash_token(settings):
    """Test the hash_token utility."""
    settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY = "a-key"
    hashed = hash_token("some-token")
    assert isinstance(hashed, str)
    assert len(hashed) == 64
    assert hashed != "some-token"
    # Deterministic: hashing the same value twice returns the same hash
    assert hash_token("some-token") == hashed
    # Sensitive to the value
    assert hash_token("another-token") != hashed
    # Sensitive to the key (pepper)
    settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY = "another-key"
    assert hash_token("some-token") != hashed


def test_hash_token_falls_back_to_secret_key(settings):
    """Test the hash_token utility falls back to the SECRET_KEY setting."""
    settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY = None
    settings.SECRET_KEY = "secret-key"
    hashed = hash_token("some-token")
    settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY = "secret-key"
    assert hash_token("some-token") == hashed
